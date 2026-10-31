"""Persistent feedback storage for local use and the public Streamlit app."""
from __future__ import annotations

import base64
import json
import re
import sqlite3
import threading
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .feedback_data import DIMENSIONS, validate_feedback

_SUBMISSION_LOCK = threading.Lock()


class FeedbackStoreError(RuntimeError):
    def __init__(self, reason='unavailable'):
        self.reason = reason
        super().__init__(reason)


def encode_issue_body(record: dict) -> str:
    validate_feedback(record)
    raw = json.dumps(record, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    encoded = base64.b64encode(raw).decode('ascii')
    rows = ['| Dimension | Current | Suggested |', '| --- | --- | --- |']
    for code in DIMENSIONS:
        before = record.get('original_classification', {}).get(code, '')
        after = record.get('suggested_classification', {}).get(code, '')
        rows.append(f'| {code} | {before} | {after} |')
    description = record['description']
    fence = '`' * max(3, max((len(x) + 1 for x in re.findall(r'`+', description)), default=3))
    # Literal blocks prevent visitor prose from creating mentions or active Markdown.
    title = record['subject_title'].replace('@', '@\u200b').replace('\n', ' ')
    return (f'Paper: {title}\n\nID: {record["subject_id"]}\n\n'
            + '\n'.join(rows) + f'\n\nDescription:\n{fence}\n{description}\n{fence}\n\n'
            + f'<!-- am-dashboard-feedback-v1:{encoded} -->')


def _decode_issue(issue: dict) -> dict | None:
    if not isinstance(issue, dict) or 'pull_request' in issue:
        return None
    markers = re.findall(r'<!-- am-dashboard-feedback-v1:([A-Za-z0-9+/=]+) -->',
                         issue.get('body') or '')
    if not markers:
        return None
    try:
        item = json.loads(base64.b64decode(markers[-1], validate=True))
        validate_feedback(item)
    except (ValueError, TypeError, UnicodeError):
        return None
    item['status'] = 'resolved' if issue.get('state') == 'closed' else 'pending'
    item['source_url'] = issue.get('html_url', '')
    item['source_number'] = issue.get('number')
    return item


class SQLiteFeedbackStore:
    writable = True

    def __init__(self, path: Path):
        self.path = Path(path)

    def _connect(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path, timeout=15)
        connection.execute('CREATE TABLE IF NOT EXISTS feedback '
                           '(id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)')
        return connection

    def submit(self, record: dict) -> dict:
        validate_feedback(record)
        try:
            with self._connect() as connection:
                connection.execute('INSERT OR IGNORE INTO feedback VALUES (?, ?, ?)',
                                   (record['feedback_id'], record['submitted_at'],
                                    json.dumps(record, ensure_ascii=False)))
                raw = connection.execute('SELECT payload FROM feedback WHERE id = ?',
                                         (record['feedback_id'],)).fetchone()[0]
        except sqlite3.Error as error:
            raise FeedbackStoreError() from error
        return {**json.loads(raw), 'status': 'pending', 'source_url': ''}

    def list_feedback(self) -> list[dict]:
        try:
            with self._connect() as connection:
                rows = connection.execute('SELECT payload FROM feedback ORDER BY created_at DESC').fetchall()
        except sqlite3.Error as error:
            raise FeedbackStoreError() from error
        result = []
        for (raw,) in rows:
            item = json.loads(raw)
            validate_feedback(item)
            result.append({**item, 'status': 'pending', 'source_url': ''})
        return result


class GitHubFeedbackStore:
    def __init__(self, repository: str, token: str = '', *, opener=None):
        if not re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', repository) or '..' in repository:
            raise ValueError('Invalid GitHub repository')
        self.repository = repository
        self._token = token
        self.writable = bool(token)
        self._opener = opener or urlopen

    def _request(self, method: str, query='', payload=None):
        headers = {'Accept': 'application/vnd.github+json',
                   'User-Agent': 'medical-am-dashboard-feedback',
                   'X-GitHub-Api-Version': '2022-11-28'}
        if self._token:
            headers['Authorization'] = 'Bearer ' + self._token
        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
            headers['Content-Type'] = 'application/json'
        url = f'https://api.github.com/repos/{self.repository}/issues{query}'
        request = Request(url, data=data, headers=headers, method=method)
        try:
            with self._opener(request, timeout=15) as response:
                return json.load(response), response.headers
        except HTTPError as error:
            reason = 'permission' if error.code in (401, 403) else 'unavailable'
            raise FeedbackStoreError(reason) from None
        except (URLError, OSError, ValueError) as error:
            raise FeedbackStoreError('unavailable') from None

    def list_feedback(self) -> list[dict]:
        result, page = [], 1
        while True:
            payload, headers = self._request('GET', '?' + urlencode(
                {'state': 'all', 'per_page': 100, 'page': page, 'sort': 'created', 'direction': 'desc'}))
            if not isinstance(payload, list):
                raise FeedbackStoreError()
            result.extend(item for raw in payload if (item := _decode_issue(raw)) is not None)
            if 'rel="next"' not in headers.get('Link', ''):
                break
            page += 1
        return result

    def submit(self, record: dict) -> dict:
        if not self.writable:
            raise FeedbackStoreError('not_configured')
        validate_feedback(record)
        # Streamlit reruns can overlap while an earlier HTTP request finishes.
        with _SUBMISSION_LOCK:
            for existing in self.list_feedback():
                if existing['feedback_id'] == record['feedback_id']:
                    return existing
            payload = {'title': f'[AM feedback] {record["feedback_type"]}: {record["subject_id"]}',
                       'body': encode_issue_body(record)}
            created, _ = self._request('POST', payload=payload)
            receipt = _decode_issue(created)
            if receipt is None:
                raise FeedbackStoreError()
            return receipt

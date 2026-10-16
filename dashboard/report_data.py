"""Static research reports: contracts, safe references and checked corpus counts."""
from __future__ import annotations

import json
import re
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

REPORT_FIELDS = frozenset(('question_id', 'p', 'direction', 'title', 'version', 'updated_at', 'evidence_cutoff', 'core_finding', 'sections', 'references', 'related_paper_ids', 'related_company_ids'))
SECTION_FIELDS = frozenset(('id', 'title', 'markdown', 'reference_ids'))
REFERENCE_FIELDS = frozenset(('id', 'title', 'publisher', 'year', 'url', 'kind'))
SECTION_IDS = ('scope', 'academic_chain', 'academic_trends', 'industry', 'intersection', 'outlook')
REF_PATTERN = re.compile(r'\[([^\]\n]+)\]\(ref:([A-Za-z0-9_-]+)\)')
PRIVATE_PATH = re.compile(r'(?i)(?<![a-z])[a-z]:[\\/]|file://|\\\\[^\\]')
RAW_HTML = re.compile(r'</?[A-Za-z][^>]*>')


def safe_source_url(value: str) -> bool:
    if not isinstance(value, str) or any(ord(char) <= 32 for char in value):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme in ('https', 'http') and bool(parsed.hostname)
                and parsed.username is None and parsed.password is None
                and not any(char in value for char in ('<', '>', '"', '\\')))
    except ValueError:
        return False


def load_question_reports(root: Path) -> dict:
    path = Path(root) / 'data/question_reports.json'
    if not path.exists():
        return {'schema_version': 1, 'reports': {}}
    return json.loads(path.read_text(encoding='utf-8'))


def validate_question_reports(data: dict, questions: list[dict], *, require_complete: bool) -> list[str]:
    errors = []
    if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('reports'), dict):
        return ['Invalid report library schema']
    if set(data) != {'schema_version', 'reports'}:
        errors.append('Unknown library fields')
    expected = {q['question_id']: q for q in questions}
    reports = data['reports']
    if require_complete and set(reports) != set(expected):
        errors.append(f'Report coverage mismatch: missing={sorted(set(expected)-set(reports))}, extra={sorted(set(reports)-set(expected))}')
    for qid, report in reports.items():
        def error(message):
            errors.append(f'{qid}: {message}')
        if qid not in expected or not isinstance(report, dict):
            error('Unknown question or invalid report')
            continue
        if set(report) != REPORT_FIELDS:
            error('Unknown or missing public report fields')
        q = expected[qid]
        for field, value in [('question_id', qid), ('p', q['p']), ('direction', q['direction']), ('title', q['question'])]:
            if report.get(field) != value:
                error(f'Mismatched {field}')
        if not isinstance(report.get('version'), int) or report['version'] < 1:
            error('Invalid version')
        for key in ('updated_at', 'evidence_cutoff'):
            try:
                date.fromisoformat(report[key])
            except (KeyError, TypeError, ValueError):
                error(f'Invalid {key}')
        if not isinstance(report.get('core_finding'), str) or not report['core_finding'].strip():
            error('Missing core finding')
        for key in ('related_paper_ids', 'related_company_ids'):
            if not isinstance(report.get(key), list) or not all(isinstance(x, str) and x for x in report.get(key, [])):
                error(f'Invalid {key}')
        refs = report.get('references', [])
        if not isinstance(refs, list) or not refs or not all(isinstance(r, dict) for r in refs):
            error('Missing references')
            refs = []
        ref_ids = [r.get('id') for r in refs]
        if any(not isinstance(x, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', x) for x in ref_ids) or len(set(ref_ids)) != len(ref_ids):
            error('Duplicate or invalid reference ID')
        valid_ref_ids = {x for x in ref_ids if isinstance(x, str)}
        for ref in refs:
            if set(ref) != REFERENCE_FIELDS:
                error('Unknown or missing reference fields')
            if not safe_source_url(ref.get('url', '')):
                error('Unsafe reference URL')
            if not all(isinstance(ref.get(k), str) and ref[k].strip() for k in ('title', 'publisher', 'kind')):
                error('Incomplete reference metadata')
        sections = report.get('sections', [])
        if not isinstance(sections, list) or not all(isinstance(s, dict) for s in sections):
            error('Invalid sections')
            sections = []
        if [s.get('id') for s in sections] != list(SECTION_IDS):
            error('Incomplete or unordered sections')
        for section in sections:
            if set(section) != SECTION_FIELDS:
                error('Unknown or missing section fields')
            body = section.get('markdown', '')
            declared = section.get('reference_ids', [])
            if not isinstance(body, str) or not body.strip() or not section.get('title'):
                error('Empty section')
                continue
            used = {match[1] for match in REF_PATTERN.findall(body)}
            if (not isinstance(declared, list) or not all(isinstance(x, str) for x in declared)
                    or set(declared) != used or not used.issubset(valid_ref_ids)):
                error('Unresolved or mismatched citation')
            remainder = REF_PATTERN.sub('', body)
            if ('ref:' in remainder or re.search(r'\]\s*[\[(]|(?m:^\s*\[[^\]]+\]:)|https?://|<[^>]+@[^>]+>', remainder)):
                error('Unregistered body link')
        serialized = json.dumps(report, ensure_ascii=False)
        if PRIVATE_PATH.search(serialized) or RAW_HTML.search(serialized):
            error('Private path or raw HTML in report')
    return errors


def count_checked_papers(papers: list[dict], cutoff: str) -> list[dict]:
    cutoff_date = date.fromisoformat(cutoff)
    years = {}
    for paper in papers:
        year = int(paper['year'])
        if year > cutoff_date.year or year < 1000:
            raise ValueError('Paper year outside cutoff')
        if paper['id'] in years and years[paper['id']] != year:
            raise ValueError('Conflicting publication years')
        years[paper['id']] = year
    counts = Counter(years.values())
    return [{'year': year, 'count': counts[year],
             'partial': year == cutoff_date.year and (cutoff_date.month, cutoff_date.day) != (12, 31)}
            for year in sorted(counts)]

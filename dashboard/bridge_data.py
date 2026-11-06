"""Validated portable evidence graph and shared intersecting resource filters."""
from __future__ import annotations

import gzip
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

SCHEMA_VERSION = 1
METHOD_VERSION = 'medical-object-and-question-facet-1.0'
PRIVATE_PATH = re.compile(r'(?i)(?<![A-Z])[A-Z]:[\\/]|file://|\\\\[^\\]')


def source_digest(path):
    """Git text checkout portability without weakening content integrity."""
    path = Path(path)
    payload = path.read_bytes()
    if path.suffix.casefold() in {'.json','.jsonl','.csv','.py'}:
        payload = payload.replace(b'\r\n', b'\n')
    return hashlib.sha256(payload).hexdigest()


def _safe_url(value, optional=False):
    if optional and not value:
        return True
    part = urlsplit(str(value))
    return part.scheme in {'http', 'https'} and bool(part.netloc) and not part.username and not part.password


def validate_bridge(graph):
    """Fail closed on stale IDs, unsafe provenance and malformed graph selections."""
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def private(value):
        if isinstance(value, dict):
            return any(private(v) for v in value.values())
        if isinstance(value, list):
            return any(private(v) for v in value)
        return isinstance(value, str) and bool(PRIVATE_PATH.search(value))

    require(graph.get('schema_version') == SCHEMA_VERSION and graph.get('method_version') == METHOD_VERSION,
            'Unsupported bridge schema or matching method')
    require(not private(graph), 'Bridge contains a private path')
    indexes = {}
    for key in ('applications', 'topics', 'papers', 'patents', 'companies'):
        rows = graph.get(key)
        require(isinstance(rows, list), 'Missing bridge collection: '+key)
        require(all(isinstance(r.get('id'), str) and r['id'] for r in rows), 'Invalid '+key+' identity')
        indexes[key] = {r['id']: r for r in rows}
        require(len(indexes[key]) == len(rows), 'Duplicate '+key+' identity')
    apps, topics = set(indexes['applications']), set(indexes['topics'])
    for row in graph['topics']:
        require(set(row['applications']) <= apps, 'Unknown topic application')
    for key in ('papers', 'patents', 'companies'):
        for row in graph[key]:
            require(set(row['applications']) <= apps and set(row['topics']) <= topics, 'Unknown entity topic/application')
            if key == 'companies':
                require(_safe_url(row.get('website',''), optional=True), 'Unsafe company website')
                require(all(_safe_url(v) for v in row.get('source_urls',[])), 'Unsafe company evidence URL')
            else:
                require(_safe_url(row['source_url'], optional=key == 'papers'), 'Unsafe source URL')
            if key == 'patents':
                require(len(row['abstract_excerpt']) <= 360, 'Patent excerpt exceeds public limit')
                require(set(row.get('source_medical_categories',[])) <= apps, 'Unknown original patent application')
                if row.get('association_status') == 'excluded_nonmedical_context':
                    require(not row['applications'] and not row['topics'] and not row.get('topic_evidence'),
                            'Excluded nonmedical patent cannot have medical associations')
            for evidence in row.get('topic_evidence',[]):
                require(evidence['topic_id'] in row['topics'] and evidence['matched_terms'], 'Invalid topic evidence')
                require(len(evidence.get('excerpt','')) <= 360, 'Topic excerpt exceeds public limit')
            for feature in row.get('technical_features',[]):
                require(isinstance(feature.get('id'),str) and feature['id'] and feature.get('group') in {'material','process','design','focus'}, 'Invalid technical feature identity')
                require(feature.get('matched_terms') and len(feature.get('excerpt','')) <= 280, 'Invalid technical feature evidence')
    for edge in graph.get('company_patent_links',[]):
        require(edge['company_id'] in indexes['companies'] and edge['patent_id'] in indexes['patents'], 'Dangling applicant edge')
        require(edge['type'] == 'applicant_name_match' and edge['applicant_name'] in indexes['patents'][edge['patent_id']]['applicants'], 'Invalid applicant evidence')
        from dashboard.bridge_matching import applicant_name_matches
        require(applicant_name_matches(indexes['companies'][edge['company_id']]['name'],edge['applicant_name']), 'Unverified company/applicant identity')
    require(isinstance(graph.get('reports'), dict), 'Missing report scopes')
    for ident, report in graph['reports'].items():
        require(ident == report['id'] and report['scope'] in {'question','direction'}, 'Invalid report identity')
        require(set(report['applications']) <= apps and set(report['topic_ids']) <= topics, 'Invalid report topics')
        require(set(report['paper_ids']) <= set(indexes['papers']) and set(report['company_ids']) <= set(indexes['companies']), 'Dangling report resource')
        for link in report['patent_links']:
            require(link['patent_id'] in indexes['patents'] and set(link['topic_ids']) <= set(report['topic_ids']), 'Dangling report patent/topic')
            require(link['matched_terms'] and (report['scope'] != 'question' or link.get('facet_terms')), 'Missing report matching evidence')
            require(len(link.get('evidence_excerpt','')) <= 360, 'Report excerpt exceeds public limit')
            require(set(link['topic_ids']) <= set(indexes['patents'][link['patent_id']]['topics']), 'Report topic not supported by patent')
        require(len({v['patent_id'] for v in report['patent_links']}) == len(report['patent_links']), 'Duplicate scoped patent links')
    return graph


def load_bridge(root):
    root = Path(root)
    manifest = json.loads((root/'data/patent_bridge_manifest.json').read_text(encoding='utf8'))
    compressed = (root/'data/patent_bridge.json.gz').read_bytes()
    if manifest.get('snapshot_sha256') != hashlib.sha256(compressed).hexdigest():
        raise ValueError('Bridge snapshot integrity check failed')
    for source, expected in manifest.get('public_source_sha256',{}).items():
        if not re.fullmatch(r'data/[\w./-]+', source) or '..' in Path(source).parts:
            raise ValueError('Unsafe bridge source identifier')
        if source_digest(root/source) != expected:
            raise ValueError('Bridge source integrity check failed: '+source)
    for field, name in [('rules_sha256','bridge_matching.py'),('technical_features_sha256','technical_features.py')]:
        if manifest.get(field) and source_digest(root/'dashboard'/name) != manifest[field]:
            raise ValueError('Bridge source method integrity check failed: '+name)
    graph = validate_bridge(json.loads(gzip.decompress(compressed)))
    for key, count in manifest.get('counts',{}).items():
        if len(graph[key]) != count:
            raise ValueError('Bridge collection count integrity check failed: '+key)
    return graph


def select_bridge(graph, *, application=None, topic=None, scope_id=None, query=''):
    """AND between dimensions; invalid scopes are empty, never unscoped fallbacks."""
    scope = graph.get('reports',{}).get(scope_id) if scope_id else None
    needle = str(query or '').strip().casefold()
    result = {}
    for key in ('papers','patents','companies'):
        allowed = None
        if scope_id:
            if scope is None:
                allowed = set()
            elif key == 'patents':
                allowed = {v['patent_id'] for v in scope['patent_links']}
            else:
                allowed = set(scope['paper_ids' if key == 'papers' else 'company_ids'])
        result[key] = [row for row in graph[key]
                       if (allowed is None or row['id'] in allowed)
                       and (not application or application in row['applications'])
                       and (not topic or topic in row['topics'])
                       and (not needle or needle in json.dumps(row, ensure_ascii=False).casefold())]
    companies = {r['id'] for r in result['companies']}
    patents = {r['id'] for r in result['patents']}
    result['company_patent_links'] = [e for e in graph.get('company_patent_links',[])
                                      if e['company_id'] in companies and e['patent_id'] in patents]
    return result

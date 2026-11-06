"""Portable, credential-free display data for strictly selected patents."""
from __future__ import annotations

import gzip
import hashlib
import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pandas as pd

MEDICAL_APPLICATIONS = (
    'dental', 'implants_and_prostheses', 'tissue_engineering_and_bioprinting',
    'pharmaceuticals_and_drug_delivery', 'surgical_tools_and_anatomical_models',
    'medical_devices_and_rehabilitation',
)
PUBLIC_PATENT_FIELDS = (
    'publication_id', 'family_id', 'country', 'kind', 'publication_date',
    'publication_year', 'title', 'abstract_excerpt', 'applicants',
    'medical_categories', 'source_url',
)
SCREENING_VERSION = 'strict-medical-am-1.2'


def _validate_row(row):
    if set(row) != set(PUBLIC_PATENT_FIELDS):
        raise ValueError('Unexpected patent display fields')
    ident = row['publication_id']
    # OPS includes regional formats such as TWI608928B and SG11201910191RA.
    if not isinstance(ident, str) or not re.fullmatch(r'[A-Z]{2}[A-Z0-9]*\d[A-Z0-9]*', ident):
        raise ValueError('Invalid publication number')
    url = urlsplit(row['source_url'])
    if (url.scheme != 'https' or url.netloc != 'worldwide.espacenet.com'
            or url.path != '/patent/search' or url.fragment
            or parse_qs(url.query) != {'q': ['pn=' + ident]}):
        raise ValueError('Patent link must match its exact publication number')
    categories = row['medical_categories']
    if not isinstance(categories, list) or not categories or not set(categories) <= set(MEDICAL_APPLICATIONS):
        raise ValueError('Missing or invalid medical applications')
    if not isinstance(row['applicants'], list) or not all(isinstance(v, str) and v.strip() for v in row['applicants']):
        raise ValueError('Applicants must be individual names')
    if row['publication_date']:
        year = date.fromisoformat(row['publication_date']).year
        if row['publication_year'] != year:
            raise ValueError('Publication year does not match publication date')
    elif row['publication_year'] is not None:
        raise ValueError('Unknown publication date must have an unknown year')
    if len(row['abstract_excerpt']) > 361:
        raise ValueError('Public patent excerpt is too long')


def _original_text(values):
    preferred = next((v for v in values if v.get('lang') == 'en' and v.get('text')), None)
    return (preferred or next((v for v in values if v.get('text')), {})).get('text', '').strip()


def project_patent(record):
    strict = record.get('strict_screening', {})
    if strict.get('decision') != 'included_direct' or strict.get('version') != SCREENING_VERSION:
        raise ValueError('Only the final strictly selected patent set may be published')
    published = record.get('publication_date') or None
    excerpt = _original_text(record.get('abstracts', []))
    row = {
        'publication_id': record['publication_id'],
        'family_id': str(record.get('family_id') or ''),
        'country': record.get('country', ''), 'kind': record.get('kind', ''),
        'publication_date': published,
        'publication_year': date.fromisoformat(published).year if published else None,
        'title': _original_text(record.get('titles', [])),
        'abstract_excerpt': excerpt[:360].rstrip() + '…' if len(excerpt) > 360 else excerpt,
        'applicants': list(dict.fromkeys(v['name'].strip() for v in record.get('applicants', []) if v.get('name', '').strip())),
        'medical_categories': list(dict.fromkeys(strict.get('medical_categories', []))),
        'source_url': record['source_url'],
    }
    _validate_row(row)
    return row


def build_snapshot(source, root, expected_count=None):
    """Project only allowlisted fields; never copy source files or credentials."""
    original = Path(source).read_bytes()
    rows = [project_patent(json.loads(line)) for line in original.decode('utf-8-sig').splitlines() if line.strip()]
    if expected_count is not None and len(rows) != expected_count:
        raise ValueError(f'Expected {expected_count} patents, got {len(rows)}')
    if len({r['publication_id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate patent publication numbers')
    rows.sort(key=lambda r: (r['publication_date'] or '', r['publication_id']), reverse=True)
    payload = ''.join(json.dumps(r, ensure_ascii=False, separators=(',', ':'))+'\n' for r in rows).encode('utf-8')
    compressed = gzip.compress(payload, mtime=0)
    years = [r['publication_year'] for r in rows if r['publication_year'] is not None]
    manifest = {
        'schema_version': 1, 'screening_version': SCREENING_VERSION,
        'publications': len(rows), 'observed_families': len({r['family_id'] for r in rows if r['family_id']}),
        'year_min': min(years) if years else None, 'year_max': max(years) if years else None,
        'source_sha256': hashlib.sha256(original).hexdigest(),
        'snapshot_sha256': hashlib.sha256(compressed).hexdigest(),
        'fields': list(PUBLIC_PATENT_FIELDS), 'full_text_included': False,
    }
    destination = Path(root)/'data'
    destination.mkdir(parents=True, exist_ok=True)
    (destination/'patents.jsonl.gz').write_bytes(compressed)
    (destination/'patents_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return manifest


def load_patents(root):
    data = Path(root)/'data'
    manifest = json.loads((data/'patents_manifest.json').read_text(encoding='utf-8'))
    compressed = (data/'patents.jsonl.gz').read_bytes()
    if (manifest.get('schema_version') != 1 or manifest.get('screening_version') != SCREENING_VERSION
            or manifest.get('snapshot_sha256') != hashlib.sha256(compressed).hexdigest()):
        raise ValueError('Patent snapshot integrity check failed')
    rows = [json.loads(line) for line in gzip.decompress(compressed).decode('utf-8').splitlines() if line.strip()]
    for row in rows:
        _validate_row(row)
    if len(rows) != manifest['publications'] or len({r['publication_id'] for r in rows}) != len(rows):
        raise ValueError('Patent publication count mismatch')
    if len({r['family_id'] for r in rows if r['family_id']}) != manifest['observed_families']:
        raise ValueError('Patent family count mismatch')
    frame = pd.DataFrame(rows, columns=PUBLIC_PATENT_FIELDS)
    frame['publication_year'] = pd.array(frame.publication_year, dtype='Int64')
    return frame


def filter_patents(frame, *, applications=None, applicants=None, years=None,
                   include_unknown_year=True, query=''):
    """OR within a selection, AND between dimensions; applicant names are exact."""
    mask = pd.Series(True, index=frame.index)
    if applications is not None:
        selected = set(applications)
        mask &= frame.medical_categories.map(lambda values: bool(selected.intersection(values)))
    if applicants:
        selected = set(applicants)
        mask &= frame.applicants.map(lambda values: bool(selected.intersection(values)))
    if years is not None:
        numeric = pd.to_numeric(frame.publication_year, errors='coerce')
        mask &= numeric.between(*years).fillna(False) | (numeric.isna() & include_unknown_year)
    elif not include_unknown_year:
        mask &= frame.publication_year.notna()
    if query.strip():
        text = frame.apply(lambda r: ' '.join([r.publication_id, r.title, r.abstract_excerpt, *r.applicants]), axis=1)
        mask &= text.str.contains(query.strip(), case=False, regex=False, na=False)
    return frame.loc[mask].copy()

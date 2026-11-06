"""Real-source acceptance checks for patent-led direction report bodies."""
import gzip
import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from dashboard.direction_reports import load_reports
from scripts.export_direction_reports import report_html

ROOT = Path(__file__).resolve().parents[1]


def _patent_id(reference):
    url = urlparse(reference['url'])
    if url.hostname != 'worldwide.espacenet.com':
        return None
    query = parse_qs(url.query).get('q', [''])[0]
    return query.removeprefix('pn=') if query.startswith('pn=') else None


def test_rewritten_main_chapters_use_held_patents_and_resolvable_citations():
    patents = {row['publication_id']: row for row in
               map(json.loads, gzip.decompress((ROOT/'data/patents.jsonl.gz').read_bytes()).decode('utf8').splitlines())}
    for code in ('zh', 'en', 'de'):
        for rid, report in load_reports(str(ROOT), code).items():
            refs = {ref['id']: ref for ref in report['references']}
            patent_refs = {ref['id']: _patent_id(ref) for ref in refs.values() if _patent_id(ref)}
            for refid, patent_id in patent_refs.items():
                assert patent_id in patents, (rid, refid, patent_id)
                assert refs[refid]['url'] == patents[patent_id]['source_url']
            indices = (4, 5, 6) if rid.startswith('P7-') else (3, 4, 5)
            for index in indices:
                chapter = report['sections'][index]
                prose = json.dumps(chapter, ensure_ascii=False)
                citations = set(re.findall(r'\[(R\d+)\]', prose))
                assert citations <= set(refs), (rid, code, index)
                if rid != 'P5-02':
                    assert citations & set(patent_refs), (rid, code, index)
            outlook = json.dumps(report['sections'][indices[-1]], ensure_ascii=False)
            assert all(str(year) in outlook for year in (2027, 2028, 2029)), (rid, code)


def test_complete_html_exports_include_updated_chapters_and_all_source_links():
    for code in ('zh', 'en', 'de'):
        reports = load_reports(str(ROOT), code)
        for rid in ('P1-01', 'P3-01', 'P5-02', 'P7-01'):
            report = reports[rid]
            content = report_html(report, code)
            assert f'<html lang="{code}">' in content
            assert '2026-11-07' in content or '07.11.2026' in content
            assert '<section id="sources">' in content
            assert 'rel="noopener noreferrer"' in content
            for ref in report['references']:
                assert ref['url'].replace('&', '&amp;') in content

"""Reproducible offline association build; strict source is an explicit CLI input.

No network clients, full-text fetching, credential reads or local source paths
are included in the released graph. Original records remain unmodified.
"""
from __future__ import annotations
import argparse
from collections import Counter, defaultdict
import csv
import gzip
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dashboard.bridge_data import validate_bridge, source_digest
from dashboard.bridge_matching import (APPLICATIONS, TOPICS, METHOD_VERSION,
    D, I, T, P, S, M, applicant_name_matches, normalize_applicant,
    match_topics, match_report, question_profiles, excerpt, entity_applications, association_eligibility)
from dashboard.patent_data import project_patent
from dashboard.technical_features import extract_technical_features

COMPARISON_GUIDANCE = {
    'zh': '题名与摘要仅表明技术方案线索；不能证明临床优效、专利授权、现行权属、实施、论文引用或许可关系。比较临床结局仍需匹配对照、随访和终点。',
    'en': 'Titles and abstracts identify technical scheme candidates; they establish neither clinical superiority, grant status, current ownership, implementation, paper citation nor licensing. Clinical comparisons require appropriate controls, follow-up and outcomes.',
    'de': 'Titel und Abstracts liefern Hinweise auf technische Ansätze; sie belegen weder klinische Überlegenheit, Erteilung, aktuelle Inhaberschaft, Umsetzung, Publikationszitate noch Lizenzierung. Klinische Vergleiche erfordern geeignete Kontrollen, Nachbeobachtung und Endpunkte.',
}


def _read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def _read_lines(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8-sig').splitlines() if line.strip()]


def _source_url(row):
    doi = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi\s*:\s*)', '', str(row.get('doi') or ''), flags=re.I).strip()
    if re.match(r'^10\.\d{4,9}/\S+$', doi):
        return 'https://doi.org/'+quote(doi, safe='/():;._-')
    pmid = str(row.get('pmid') or '').strip()
    if pmid.isdigit():
        return 'https://pubmed.ncbi.nlm.nih.gov/'+pmid+'/'
    pmcid = str(row.get('pmcid') or '').strip()
    if re.fullmatch(r'PMC\d+', pmcid):
        return 'https://pmc.ncbi.nlm.nih.gov/articles/'+pmcid+'/'
    return ''


def _entity_topics(text, p_codes, *, disease='', bioprinting=False):
    evidence = match_topics(text)
    ids = [e['topic_id'] for e in evidence]
    apps = entity_applications(text, p_codes, disease=disease, bioprinting=bioprinting, topic_ids=ids)
    return {'applications': apps, 'topics': ids, 'topic_evidence': evidence}


def project_bridge_patent(original):
    row = project_patent(original)
    abstract = next((v['text'] for v in original.get('abstracts',[]) if v.get('lang') == 'en' and v.get('text')), None)
    abstract = abstract or next((v['text'] for v in original.get('abstracts',[]) if v.get('text')), '')
    text = row['title']+'\n'+abstract
    status, reason = association_eligibility(text)
    evidence = match_topics(text) if status == 'eligible' else []
    topics = [e['topic_id'] for e in evidence]
    apps = sorted(set(row['medical_categories']) | set(entity_applications(text, [], topic_ids=topics))) if status == 'eligible' else []
    patent = {'id': row['publication_id'], 'title': row['title'], 'year': row['publication_year'],
              'source_url': row['source_url'], 'applicants': row['applicants'],
              'family_id': row['family_id'], 'applications': apps, 'topics': topics, 'topic_evidence': evidence,
              'source_medical_categories': row['medical_categories'],
              'abstract_excerpt': excerpt(abstract), 'publication_date': row['publication_date'],
              'country': row['country'], 'kind': row['kind'],
              'association_status': status, 'association_reason': reason,
              'technical_features': extract_technical_features(text) if status == 'eligible' else [],
              'application_basis': 'existing_strict_screening_plus_explicit_object_terms'}
    return patent, text


def build_bridge(root, strict_source, *, expected_counts=(7169,5516,352,148)):
    root, strict_source = Path(root), Path(strict_source)
    public_sources = ['data/papers_pre2026.csv','data/additions.jsonl','data/enterprises.csv',
                      'data/enterprise_events.jsonl','data/enterprise_observations.jsonl',
                      'data/cross_analysis.json','data/patents.jsonl.gz','data/patents_manifest.json']
    public_sources += [f'data/direction_reports/{lang}.json' for lang in ('zh','en','de')]
    public_sources += sorted(p.relative_to(root).as_posix() for p in (root/'data/academic_questions').glob('P*.json'))
    source_hashes = {name: source_digest(root/name) for name in public_sources}
    raw = strict_source.read_bytes()
    strict_sha256 = hashlib.sha256(raw).hexdigest()
    public_manifest = _read_json(root/'data/patents_manifest.json')
    if strict_sha256 != public_manifest['source_sha256']:
        raise ValueError('Strict source differs from the already released patent snapshot')
    source_records = [json.loads(line) for line in raw.decode('utf-8-sig').splitlines() if line.strip()]
    full_texts = {}
    patents = []
    for original in source_records:
        patent, text = project_bridge_patent(original)
        full_texts[patent['id']] = text
        patents.append(patent)
    released_ids = {r['publication_id'] for r in [json.loads(v) for v in gzip.decompress((root/'data/patents.jsonl.gz').read_bytes()).decode().splitlines()]}
    if {p['id'] for p in patents} != released_ids:
        raise ValueError('Strict source publication IDs differ from public snapshot')
    with (root/'data/papers_pre2026.csv').open(encoding='utf-8-sig', newline='') as handle:
        paper_rows = list(csv.DictReader(handle))
    paper_rows += _read_lines(root/'data/additions.jsonl')
    papers = []
    for row in paper_rows:
        evidence_fields = [str(row.get(k) or '') for k in ('p_layer_evidence_text','disease_evidence_text',
                           'process_evidence_text','material_evidence_text','bioprinting_evidence_text')]
        text = row['title']+'\n'+'\n'.join(dict.fromkeys(evidence_fields))
        paper = {'id': row['document_id'], 'title': row['title'], 'year': int(row['publication_year']),
                 'source_url': _source_url(row),
                 **_entity_topics(text, [row.get('analysis_primary_p_layer','')],
                                  disease=row.get('disease_primary_code',''),
                                  bioprinting=str(row.get('bioprinting_flag','')).casefold() in {'true','1'}),
                 'application_basis': 'existing_p_layer_plus_explicit_object_terms',
                 'source_journal': row.get('source_journal',''), 'doi': row.get('doi',''),
                 'technical_features': extract_technical_features(text)}
        papers.append(paper)
    observations = _read_lines(root/'data/enterprise_observations.jsonl')
    events = _read_lines(root/'data/enterprise_events.jsonl')
    source_urls = defaultdict(set)
    for row in observations+events:
        if row.get('source_url'):
            source_urls[row['company_id']].add(row['source_url'])
    with (root/'data/enterprises.csv').open(encoding='utf-8-sig', newline='') as handle:
        company_rows = list(csv.DictReader(handle))
    companies = []
    for row in company_rows:
        text = row.get('product_summary','')+'\n'+row.get('technology_summary','')
        p_codes = re.findall(r'P[1-7]',row.get('p_codes',''))
        companies.append({'id': row['company_id'], 'name': row['name'], 'website': row['website'],
                          **_entity_topics(text, p_codes), 'summary': excerpt(text),
                          'technical_features': extract_technical_features(text),
                          'source_urls': sorted(source_urls[row['company_id']]),
                          'application_basis': 'existing_p_codes_plus_explicit_object_terms'})
    company_index = defaultdict(list)
    for company in companies:
        company_index[normalize_applicant(company['name'])].append(company)
    edges = []
    for patent in patents:
        if patent['association_status'] != 'eligible':
            continue
        for applicant in patent['applicants']:
            for company in company_index.get(normalize_applicant(applicant),[]):
                if applicant_name_matches(company['name'], applicant):
                    edges.append({'company_id': company['id'], 'patent_id': patent['id'],
                                  'type': 'applicant_name_match', 'applicant_name': applicant,
                                  'normalized_name': normalize_applicant(applicant)})
    profiles = question_profiles(root)
    cross = _read_json(root/'data/cross_analysis.json')
    assigned_companies = defaultdict(set)
    known_companies = {r['id'] for r in companies}
    for row in cross['enterprise_evidence']:
        if row.get('existing_company_id') in known_companies:
            assigned_companies[row['question_id']].add(row['existing_company_id'])
    known_papers = {r['id'] for r in papers}
    applicant_companies = defaultdict(set)
    for edge in edges:
        applicant_companies[edge['patent_id']].add(edge['company_id'])
    for qid, profile in profiles.items():
        original_report = _read_json(root/'data/academic_questions'/f'{qid}.json')
        profile['labels'] = {lang: original_report['locales'][lang]['title'] for lang in ('zh','en','de')}
        profile['paper_ids'] = sorted(set(original_report['related_paper_ids']) & known_papers)
        # Only established reference IDs are used; missing IDs are explicit
        # build errors, never silently invented paper records.
        if set(original_report['related_paper_ids']) - known_papers:
            raise ValueError('Unresolved released report paper IDs: '+qid)
        profile['company_ids'] = sorted(assigned_companies[qid])
    dirs = {lang: _read_json(root/'data/direction_reports'/f'{lang}.json') for lang in ('zh','en','de')}
    for did, direction in dirs['zh'].items():
        questions = [profiles[q['id']] for q in direction['questions']]
        profiles[did] = {'id': did, 'scope': 'direction', 'title': direction['title'],
                         'labels': {lang: dirs[lang][did]['title'] for lang in dirs},
                         'focus': {lang: dirs[lang][did]['thesis'] for lang in dirs},
                         'question_ids': [q['id'] for q in direction['questions']],
                         'topic_ids': sorted({t for q in questions for t in q['topic_ids']}),
                         'facets': sorted({t for q in questions for t in q['facets']}),
                         'clinical_comparison': any(q['clinical_comparison'] for q in questions),
                         'paper_ids': sorted({v for q in questions for v in q['paper_ids']}),
                         'company_ids': sorted({v for q in questions for v in q['company_ids']})}
    for profile in profiles.values():
        profile['applications'] = sorted({a for topic in TOPICS if topic['id'] in profile['topic_ids'] for a in topic['applications']})
        links = []
        for patent in patents:
            link = match_report(profile, full_texts[patent['id']], patent['topic_evidence'])
            if link:
                links.append({'patent_id': patent['id'], **link})
        links.sort(key=lambda v: (-v['score'],v['patent_id']))
        profile['patent_links'] = links
        registered = set(profile['company_ids'])
        named = {cid for link in links for cid in applicant_companies[link['patent_id']]}
        profile['company_ids'] = sorted(registered | named)
        profile['company_bases'] = {cid: (['registered_report_evidence'] if cid in registered else []) +
                                   (['applicant_name_match'] if cid in named else []) for cid in profile['company_ids']}
        profile['comparison_guidance'] = COMPARISON_GUIDANCE
    graph = {'schema_version': 1, 'method_version': METHOD_VERSION, 'applications': APPLICATIONS,
             'topics': TOPICS, 'papers': papers, 'patents': patents, 'companies': companies,
             'company_patent_links': edges, 'reports': profiles}
    validate_bridge(graph)
    counts = {key: len(graph[key]) for key in ('papers','patents','companies','reports')}
    if tuple(counts.values()) != expected_counts:
        raise ValueError('Unexpected bridge source counts: '+str(counts))
    compressed = gzip.compress(json.dumps(graph, ensure_ascii=False, separators=(',',':')).encode('utf8'), mtime=0)
    patent_families = {p['id']: p['family_id'] for p in patents}
    coverage = {ident: {'patents': len(profile['patent_links']),
                        'families': len({patent_families[v['patent_id']] for v in profile['patent_links'] if patent_families[v['patent_id']]}),
                        'papers': len(profile['paper_ids']), 'companies': len(profile['company_ids'])}
                for ident,profile in profiles.items()}
    manifest = {'schema_version': 1, 'method_version': METHOD_VERSION, 'counts': counts,
                'snapshot_sha256': hashlib.sha256(compressed).hexdigest(),
                'strict_source_sha256': strict_sha256, 'public_source_sha256': source_hashes,
                'source_hash_normalization': 'newline-lf-v1',
                'topic_count': len(TOPICS), 'applicant_name_links': len(edges),
                'excluded_nonmedical_context': sum(p['association_status'] != 'eligible' for p in patents),
                'applicant_matched_companies': len({e['company_id'] for e in edges}),
                'topic_matched': {k: sum(bool(r['topics']) for r in graph[k]) for k in ('papers','patents','companies')},
                'reports_with_patents': sum(bool(p['patent_links']) for p in profiles.values()),
                'coverage': coverage, 'full_text_included': False, 'excerpt_character_limit': 360,
                'rules_sha256': source_digest(root/'dashboard/bridge_matching.py'),
                'technical_features_sha256': source_digest(root/'dashboard/technical_features.py')}
    (root/'data/patent_bridge.json.gz').write_bytes(compressed)
    (root/'data/patent_bridge_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--strict-source', type=Path, required=True)
    args = parser.parse_args()
    manifest = build_bridge(args.root, args.strict_source)
    print(json.dumps({k:v for k,v in manifest.items() if k not in {'coverage','public_source_sha256'}}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

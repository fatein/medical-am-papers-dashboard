"""Behavior checks for explicit evidence matches and the portable bridge graph."""
from copy import deepcopy
from pathlib import Path
import gzip
import json

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_application_alone_never_creates_a_report_match():
    from dashboard.bridge_matching import match_topics, match_report, question_profiles
    profile = question_profiles(ROOT)['P1-001']
    text = 'A medical implant manufactured by additive manufacturing.'
    topics = match_topics(text, ['implants_and_prostheses'])
    assert match_report(profile, text, topics) is None


def test_porous_implant_question_requires_its_specific_facet():
    from dashboard.bridge_matching import match_topics, match_report, question_profiles
    profile = question_profiles(ROOT)['P1-001']
    text = 'A porous titanium bone implant with interconnected pores for bone ingrowth.'
    topics = match_topics(text, ['implants_and_prostheses'])
    link = match_report(profile, text, topics)
    assert link and 'pore' in ' '.join(link['facet_terms'])
    fatigue = question_profiles(ROOT)['P1-010']
    assert match_report(fatigue, text, topics) is None


def test_socket_polysemy_requires_prosthetic_limb_context():
    from dashboard.bridge_matching import match_topics
    assert not match_topics('A dental implant socket with a removable connector.', ['dental'])
    topics = match_topics('A prosthetic socket fitting the residual limb.', ['medical_devices_and_rehabilitation'])
    assert 'prosthetic_socket' in {t['topic_id'] for t in topics}


def test_generic_printer_is_not_a_direct_medical_topic():
    from dashboard.bridge_matching import match_topics
    assert match_topics('Industrial platform for high resolution 3D printing and polymer curing.', []) == []


def test_application_mapping_does_not_equate_p_layers_with_dental_or_tissue():
    from dashboard.bridge_matching import entity_applications
    assert entity_applications('An orthopaedic osteotomy guide for knee surgery.', ['P4']) == ['surgical_tools_and_anatomical_models']
    assert entity_applications('A printed microscope for optical imaging.', ['P7']) == ['medical_devices_and_rehabilitation']
    assert entity_applications('A titanium spinal implant.', ['P1']) == ['implants_and_prostheses']
    assert entity_applications('A patient-specific prosthetic hand.', ['P2']) == ['implants_and_prostheses']
    assert 'dental' in entity_applications('A surgical guide for dental implant placement.', ['P4'])
    assert 'tissue_engineering_and_bioprinting' in entity_applications('A bioprinted cell-laden hydrogel.', ['P1'])


def test_applicant_identity_is_normalized_exact_and_conservative():
    from dashboard.bridge_matching import applicant_name_matches
    assert applicant_name_matches('3D Systems Corporation', '3D SYSTEMS CORP.')
    assert not applicant_name_matches('3D Systems Corporation', '3D SYSTEMS INC')
    assert applicant_name_matches('Materialise NV', 'MATERIALISE N.V.')
    assert not applicant_name_matches('EOS GmbH', 'EOS')
    assert not applicant_name_matches('Acme Medical', 'Acme Medical Devices Inc')
    assert not applicant_name_matches('3D Systems Corporation', 'NEXTDENT BV')
    assert not applicant_name_matches('Aesculap, Inc.', 'AESCULAP AG')
    assert not applicant_name_matches('Kumovis GmbH', 'KUMOVIS CO LTD')
    assert not applicant_name_matches('Envisiontec GmbH', 'ENVISIONTEC INC')


def test_anatomical_fractures_defects_and_microscopic_surfaces_are_not_topic_facets():
    from dashboard.bridge_matching import match_topics, match_report, question_profiles
    profiles = question_profiles(ROOT)
    text = 'A patient-specific spinal implant for a bone fracture and a bone defect, having a microscopic surface structure.'
    topics = match_topics(text, ['implants_and_prostheses','medical_devices_and_rehabilitation'])
    assert 'microscopy' not in {t['topic_id'] for t in topics}
    assert match_report(profiles['P1-010'], text, topics) is None
    assert match_report(profiles['P1-012'], text, topics) is None


def test_dental_guide_requires_dental_rather_than_mandibular_reconstruction():
    from dashboard.bridge_matching import match_topics
    topics = match_topics('A surgical guide and cutting guide for mandibular reconstruction after tumor resection.', ['surgical_tools_and_anatomical_models'])
    assert 'dental_guide' not in {t['topic_id'] for t in topics}


def test_cell_culture_alone_does_not_make_a_disease_model():
    from dashboard.bridge_matching import match_topics
    topics = match_topics('Cell culture on a vascular scaffold before implantation to replace a diseased blood vessel.', ['tissue_engineering_and_bioprinting'])
    assert 'cell_model' not in {t['topic_id'] for t in topics}


def test_direction_match_also_requires_a_relevant_direction_facet():
    from dashboard.bridge_matching import match_topics, match_report
    profile = dict(scope='direction', topic_ids=['custom_implant'], facets=['fatigue','cleaning'])
    text = 'A patient-specific cranial implant for covering a defect.'
    assert match_report(profile, text, match_topics(text, ['implants_and_prostheses'])) is None


def _held_patent(title, abstract, categories):
    return dict(publication_id='RO139161A1', family_id='1', country='RO', kind='A1',
                publication_date='2026-01-01', titles=[dict(lang='en',text=title)],
                abstracts=[dict(lang='en',text=abstract)], applicants=[],
                source_url='https://worldwide.espacenet.com/patent/search?q=pn%3DRO139161A1',
                strict_screening=dict(decision='included_direct', version='strict-medical-am-1.2', medical_categories=categories))


def test_explicit_patent_objects_override_legacy_category_noise():
    from scripts.build_patent_bridge import project_bridge_patent
    row, _ = project_bridge_patent(_held_patent('Anthropomorphic spine dosimetry phantoms using 3D printing',
                  'A patient-specific phantom reproduces density for radiotherapy dose verification.', ['implants_and_prostheses']))
    assert 'medical_phantom' in row['topics']
    assert 'surgical_tools_and_anatomical_models' in row['applications']
    assert row['source_medical_categories'] == ['implants_and_prostheses']
    row, _ = project_bridge_patent(_held_patent('3D printed microfluidic chip', 'Channels control droplets.', ['tissue_engineering_and_bioprinting']))
    assert 'microfluidic' in row['topics']
    assert 'medical_devices_and_rehabilitation' in row['applications']


def test_food_only_patent_is_retained_without_medical_associations():
    from scripts.build_patent_bridge import project_bridge_patent
    row, _ = project_bridge_patent(_held_patent('Application of algae composition in vegetable protein meat',
                     'Food processing uses algae cells, a tissue scaffold matrix, bio-ink and culture to produce cultured meat.', ['tissue_engineering_and_bioprinting']))
    assert row['id'] == 'RO139161A1'
    assert row['association_status'] == 'excluded_nonmedical_context'
    assert row['applications'] == row['topics'] == row['topic_evidence'] == []
    assert row['source_medical_categories'] == ['tissue_engineering_and_bioprinting']


def test_clinical_comparison_uses_technical_context_not_equator_lexeme():
    from dashboard.bridge_matching import match_topics, match_report, question_profiles
    profile = question_profiles(ROOT)['P2-031']
    text = 'A denture defining the clinical equator of the teeth.'
    assert match_report(profile, text, match_topics(text)) is None
    text = 'A denture base made by milling or additive resin printing.'
    result = match_report(profile, text, match_topics(text))
    assert result and result['evidence_role'] == 'technical_context_only'


def test_microscope_used_only_to_examine_an_implant_is_not_an_equipment_topic():
    from dashboard.bridge_matching import match_topics
    text = 'Titanium implant surface modification\nAn electron microscope examines the structure and surface of the sample.'
    assert 'microscopy' not in {t['topic_id'] for t in match_topics(text)}


def test_validation_blocks_promotion_of_excluded_nonmedical_records():
    from dashboard.bridge_data import validate_bridge
    graph = dict(schema_version=1,method_version='medical-object-and-question-facet-1.0',
                 applications=[dict(id='a')], topics=[dict(id='t',applications=['a'])],
                 papers=[], companies=[], reports={}, company_patent_links=[],
                 patents=[dict(id='US1A1',applications=['a'],topics=['t'],applicants=[],
                               source_url='https://example.com/patent',abstract_excerpt='',
                               association_status='excluded_nonmedical_context')])
    with pytest.raises(ValueError, match='excluded|Excluded'):
        validate_bridge(graph)


def test_all_report_profiles_have_explicit_facets_and_localized_focus():
    from dashboard.bridge_matching import question_profiles
    profiles = question_profiles(ROOT)
    assert len(profiles) == 113
    assert all(p['topic_ids'] and p['facets'] for p in profiles.values())
    assert all(set(p['focus']) == {'zh', 'en', 'de'} for p in profiles.values())
    assert profiles['P2-029']['clinical_comparison'] is True
    assert profiles['P4-071']['clinical_comparison'] is True


def test_selection_intersects_scope_application_topic_and_literal_query():
    from dashboard.bridge_data import select_bridge
    graph = {'papers': [dict(id='p1', title='Pore [A]', applications=['a'], topics=['t']),
                        dict(id='p2', title='Pore B', applications=['a'], topics=['t'])],
             'patents': [dict(id='s1', title='Pore [A]', applications=['a'], topics=['t'])],
             'companies': [], 'company_patent_links': [],
             'reports': {'r': {'paper_ids': ['p1'], 'company_ids': [], 'patent_links': [{'patent_id': 's1'}]}}}
    selected = select_bridge(graph, application='a', topic='t', scope_id='r', query='[A]')
    assert [r['id'] for r in selected['papers']] == ['p1']
    assert [r['id'] for r in selected['patents']] == ['s1']
    assert select_bridge(graph, scope_id='unknown')['papers'] == []
    assert select_bridge(graph, application='other')['patents'] == []


def test_snapshot_retains_every_record_and_all_report_scopes():
    from dashboard.bridge_data import load_bridge
    graph = load_bridge(ROOT)
    assert [len(graph[k]) for k in ['papers', 'patents', 'companies', 'reports']] == [7169, 5516, 352, 148]
    assert all(len(row['abstract_excerpt']) <= 360 for row in graph['patents'])
    assert all('source_urls' in c for c in graph['companies'])
    assert all(row['facet_terms'] for p in graph['reports'].values() if p['scope'] == 'question' for row in p['patent_links'])


def test_validation_rejects_dangling_ids_unsafe_links_and_private_paths():
    from dashboard.bridge_data import load_bridge, validate_bridge
    graph = load_bridge(ROOT)
    bad = deepcopy(graph)
    next(iter(bad['reports'].values()))['paper_ids'].append('missing')
    with pytest.raises(ValueError):
        validate_bridge(bad)
    bad = deepcopy(graph)
    bad['patents'][0]['source_url'] = 'javascript:alert(1)'
    with pytest.raises(ValueError):
        validate_bridge(bad)
    bad = deepcopy(graph)
    bad['companies'][0]['summary'] = r'C:\private\source.docx'
    with pytest.raises(ValueError):
        validate_bridge(bad)


def test_loader_rejects_tampered_snapshot_and_changed_public_source(tmp_path):
    from dashboard.bridge_data import load_bridge
    from shutil import copytree
    copytree(ROOT/'data', tmp_path/'data')
    data = tmp_path/'data/patent_bridge.json.gz'
    data.write_bytes(data.read_bytes() + b'x')
    with pytest.raises(ValueError, match='integrity'):
        load_bridge(tmp_path)
    data.write_bytes((ROOT/'data/patent_bridge.json.gz').read_bytes())
    with (tmp_path/'data/enterprises.csv').open('a', encoding='utf8') as handle:
        handle.write('\n')
    with pytest.raises(ValueError, match='source'):
        load_bridge(tmp_path)


def test_source_integrity_accepts_only_line_ending_changes(tmp_path):
    import hashlib
    from dashboard.bridge_data import load_bridge
    data = tmp_path/'data'
    data.mkdir()
    graph = dict(schema_version=1, method_version='medical-object-and-question-facet-1.0',
                 applications=[], topics=[], papers=[], patents=[], companies=[], reports={}, company_patent_links=[])
    compressed = gzip.compress(json.dumps(graph).encode())
    (data/'patent_bridge.json.gz').write_bytes(compressed)
    (data/'enterprises.csv').write_bytes(b'name\r\nAcme\r\n')
    (data/'patent_bridge_manifest.json').write_text(json.dumps({
        'schema_version': 1, 'source_hash_normalization': 'newline-lf-v1',
        'snapshot_sha256': hashlib.sha256(compressed).hexdigest(),
        'public_source_sha256': {'data/enterprises.csv': hashlib.sha256(b'name\nAcme\n').hexdigest()}}))
    assert load_bridge(tmp_path)['companies'] == []
    (data/'enterprises.csv').write_bytes(b'name\nAcme\n\n')
    with pytest.raises(ValueError, match='source'):
        load_bridge(tmp_path)

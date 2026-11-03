import copy
import json
from pathlib import Path

import pytest

from dashboard import academic_questions as aq


def sample():
    section = {'id': 's1', 'title': '孔道比较',
               'markdown': '比较 350 μm 与 500 μm。[研究](ref:R01)', 'figure_ids': ['F01']}
    report = {'schema_version': 2, 'question_id': 'P1-001', 'p': 'P1', 'version': 2,
              'updated_at': '2026-11-03', 'evidence_cutoff': '2026-11-03', 'related_paper_ids': [],
              'references': [{'id': 'R01', 'title': 'Original title', 'publisher': 'Journal',
                              'year': 2025, 'url': 'https://example.org/paper', 'kind': 'paper'}],
              'figures': [{'id': 'F01', 'reference_id': 'R01', 'original_label': 'Fig. 4',
                           'image_url': 'https://example.org/figure.png',
                           'source_url': 'https://example.org/paper/figures/4', 'license': 'CC BY 4.0'}],
              'locales': {}}
    for code in ('zh', 'en', 'de'):
        s = copy.deepcopy(section)
        if code != 'zh':
            s.update(title='Pore comparison', markdown='Compare 350 μm and 500 μm. [Study](ref:R01)')
        report['locales'][code] = {'title': '孔道问题' if code == 'zh' else 'Pore question',
                                  'direction': '多孔结构' if code == 'zh' else 'Porous structures',
                                  'sections': [s], 'figure_texts': {'F01': {
                                      'caption': 'Figure caption', 'interpretation': 'Panel a compares cell depth.'}}}
    return report


def write_corpus(root, questions=None, papers=None):
    (root/'data').mkdir(exist_ok=True)
    (root/'data/cross_analysis.json').write_text(json.dumps({
        'questions': questions if questions is not None else [
            {'question_id':'P1-001','p':'P1','direction':'多孔结构','question':'孔道问题'}],
        'papers': papers or [],
    }), encoding='utf8')


def test_valid_report_keeps_shared_original_sources():
    r = sample()
    assert aq.validate_report(r) == []
    for lang in ('zh', 'en', 'de'):
        selected = aq.localize_report(r, lang)
        assert selected['references'] == r['references']
        assert selected['figures'] == r['figures']
        assert selected['title'] == r['locales'][lang]['title']
        assert 'core_finding' not in selected
        assert 'related_company_ids' not in selected


@pytest.mark.parametrize('mutation', [
    lambda r: r['locales'].pop('de'),
    lambda r: r['locales']['de']['sections'][0].update(figure_ids=[]),
    lambda r: r['locales']['en']['sections'][0].update(markdown='Uncited translation.'),
    lambda r: r['locales']['de']['figure_texts']['F01'].update(interpretation=''),
    lambda r: r['locales']['en']['sections'][0].update(title='遗漏中文'),
    lambda r: r['figures'][0].update(reference_id='R99'),
    lambda r: r['figures'][0].update(image_url='file:///E:/private.png'),
    lambda r: r['references'][0].update(url='javascript:alert(1)'),
    lambda r: r['locales']['zh']['sections'][0].update(markdown='<script>alert(1)</script>'),
    lambda r: r['locales']['zh']['sections'][0].update(id='industry'),
])
def test_rejects_incomplete_unsafe_or_divergent_reports(mutation):
    r = sample()
    mutation(r)
    assert aq.validate_report(r)


def test_citations_are_resolved_and_figure_attribution_stays_visible():
    r = aq.localize_report(sample(), 'en')
    body = aq.cited_markdown(r['sections'][0]['markdown'], r['references'])
    assert '[Study](https://example.org/paper)' in body
    assert 'ref:' not in body
    fig = aq.figure_html(r['figures'][0], r['figure_texts']['F01'], r['references'][0])
    assert 'Fig. 4' in fig and 'CC BY 4.0' in fig
    assert 'https://example.org/paper/figures/4' in fig
    assert 'Original title' in fig and 'loading="lazy"' in fig
    assert 'https://creativecommons.org/licenses/by/4.0/' in fig
    assert 'Panel a compares cell depth.' not in fig  # interpretation rendered as regular text


def test_release_is_atomic_and_never_falls_back_to_a_missing_language(tmp_path):
    folder = tmp_path / 'data' / 'academic_questions'
    folder.mkdir(parents=True)
    (folder / 'P1-001.json').write_text(json.dumps(sample()), encoding='utf8')
    assert aq.load_released_reports(tmp_path) is None
    (folder / 'release.json').write_text(json.dumps({'schema_version': 2, 'question_ids': ['P1-001', 'P1-002']}), encoding='utf8')
    with pytest.raises(ValueError, match='coverage'):
        aq.load_released_reports(tmp_path)
    (folder / 'release.json').write_text(json.dumps({'schema_version': 2, 'question_ids': ['P1-001']}), encoding='utf8')
    write_corpus(tmp_path)
    library = aq.load_released_reports(tmp_path)
    assert set(library['reports']) == {'P1-001'}
    broken = sample()
    broken['locales'].pop('de')
    (folder / 'P1-001.json').write_text(json.dumps(broken), encoding='utf8')
    with pytest.raises(ValueError, match='locales'):
        aq.load_released_reports(tmp_path)


def test_rendered_navigation_has_no_summary_or_company_section():
    r = aq.localize_report(sample(), 'de')
    hero = aq.header_html(r, 'de')
    assert 'Pore question' in hero and '#aq-s1' in hero
    assert 'core_finding' not in hero and 'Kernaussage' not in hero
    assert 'Unternehmen' not in hero


def test_numeric_fingerprint_ignores_citation_ids_and_localized_decimal_separator():
    assert aq.numeric_fingerprint('350 μm; 4.5 MPa; [x](ref:R01)') == aq.numeric_fingerprint('350 μm; 4,5 MPa; [y](ref:R01)')
    assert aq.numeric_fingerprint('350 μm; 4.5 MPa') != aq.numeric_fingerprint('350 μm; 45 MPa')


def test_licensed_local_figure_can_replace_remote_hotlink_but_cannot_escape_assets(tmp_path):
    r = sample()
    f = r['figures'][0]
    f['image_url'] = ''
    f['asset_path'] = 'assets/academic_figures/P1-001/F01.png'
    assert aq.validate_report(r) == []
    path = tmp_path / f['asset_path']
    path.parent.mkdir(parents=True)
    path.write_bytes(b'\x89PNG\r\n\x1a\n')
    rendered = aq.figure_html(f, r['locales']['en']['figure_texts']['F01'], r['references'][0], root=tmp_path)
    assert 'data:image/png;base64,' in rendered
    f['asset_path'] = 'assets/academic_figures/../../../private.png'
    assert aq.validate_report(r)
    with pytest.raises(ValueError):
        aq.figure_html(f, r['locales']['en']['figure_texts']['F01'], r['references'][0], root=tmp_path)


def test_existing_loader_switches_only_after_complete_release(tmp_path):
    from dashboard.report_data import load_question_reports
    folder = tmp_path / 'data' / 'academic_questions'
    folder.mkdir(parents=True)
    old = {'schema_version': 1, 'reports': {'P1-001': {'version': 1}}}
    (tmp_path/'data/question_reports.json').write_text(json.dumps(old), encoding='utf8')
    (folder/'P1-001.json').write_text(json.dumps(sample()), encoding='utf8')
    assert load_question_reports(tmp_path) == old
    (folder/'release.json').write_text(json.dumps({'schema_version': 2, 'question_ids': ['P1-001']}), encoding='utf8')
    write_corpus(tmp_path)
    assert load_question_reports(tmp_path)['schema_version'] == 2


def test_runtime_rejects_manifest_that_omits_real_questions(tmp_path):
    folder = tmp_path/'data/academic_questions'
    folder.mkdir(parents=True)
    (folder/'P1-001.json').write_text(json.dumps(sample()), encoding='utf8')
    (folder/'release.json').write_text(json.dumps({'schema_version':2,'question_ids':['P1-001']}), encoding='utf8')
    write_corpus(tmp_path, questions=[
        {'question_id':'P1-001','p':'P1','direction':'多孔结构','question':'孔道问题'},
        {'question_id':'P1-002','p':'P1','direction':'其他','question':'其他问题'},
    ])
    from dashboard.report_data import load_question_reports
    with pytest.raises(ValueError, match='cover all research questions'):
        load_question_reports(tmp_path)


@pytest.mark.parametrize('field', ['publisher','title'])
def test_shared_reference_metadata_cannot_expose_private_paths(field):
    r = sample()
    r['references'][0][field] = 'C:/Users/Private/Document.pdf'
    assert aq.validate_report(r)


@pytest.mark.parametrize('field', ['original_label','license'])
def test_shared_figure_metadata_cannot_expose_private_paths(field):
    r = sample()
    r['figures'][0][field] = 'E:/Private/Document.pdf'
    assert aq.validate_report(r)


@pytest.mark.parametrize('link', ['[See here](//example.org/unregistered)',
                                  '[See here](relative/route)', '[See here](mailto:a@example.org)',
                                  '[See here][missing]'])
def test_rejects_unregistered_links_even_when_translations_match(link):
    r = sample()
    for content in r['locales'].values():
        content['sections'][0]['markdown'] += link
    assert aq.validate_report(r)
    with pytest.raises(ValueError):
        aq.cited_markdown(r['locales']['en']['sections'][0]['markdown'], r['references'])


def test_public_package_includes_only_released_reports_and_referenced_assets(tmp_path):
    from dashboard import public_data
    folder = tmp_path/'data/academic_questions'
    folder.mkdir(parents=True)
    r = sample()
    r['figures'][0]['asset_path'] = 'assets/academic_figures/P1-001/F01.png'
    asset = tmp_path/r['figures'][0]['asset_path']
    asset.parent.mkdir(parents=True)
    asset.write_bytes(b'figure')
    (folder/'P1-001.json').write_text(json.dumps(r), encoding='utf8')
    write_corpus(tmp_path)
    assert 'dashboard/academic_questions.py' in public_data.PUBLIC_PACKAGE_FILES
    assert 'data/academic_questions/P1-001.json' not in public_data.public_package_files(tmp_path)
    (folder/'release.json').write_text(json.dumps({'schema_version':2,'question_ids':['P1-001']}), encoding='utf8')
    files = public_data.public_package_files(tmp_path)
    assert {'data/academic_questions/release.json','data/academic_questions/P1-001.json',
            'assets/academic_figures/P1-001/F01.png'} <= files
    assert 'outputs/academic_question_rebuild/evidence/P1-001.json' not in files
    assert 'assets/academic_figures/P1-001/unused.png' not in files


def test_existing_report_route_dispatches_academic_view_without_rendering_old_lead(monkeypatch):
    from dashboard import report_views
    calls = []
    monkeypatch.setattr(aq, 'academic_question_page', lambda *args: calls.append(args))
    r = sample()
    report_views.question_report_page(r, {'question_id': 'P1-001'}, Path('.'))
    assert calls and calls[0][0] is r


def test_figure_interpretation_citations_are_validated_and_aligned():
    r = sample()
    r['locales']['de']['figure_texts']['F01']['interpretation'] += ' [Study](ref:R99)'
    assert aq.validate_report(r)
    r['locales']['de']['figure_texts']['F01']['interpretation'] = 'See https://unregistered.org'
    assert aq.validate_report(r)
    r['locales']['de']['figure_texts']['F01']['interpretation'] = '[Study](ref:R01)'
    assert aq.validate_report(r)


def test_release_validation_requires_corpus_identity_paper_membership_and_assets(tmp_path):
    r = sample()
    questions = [{'question_id': 'P1-001', 'p': 'P1', 'direction': '多孔结构', 'question': '孔道问题'}]
    papers = [{'question_id': 'P1-001', 'id': 'paper1'}, {'question_id': 'P1-002', 'id': 'paper2'}]
    library = {'schema_version': 2, 'reports': {'P1-001': r}}
    assert aq.validate_library(library, questions, papers, tmp_path) == []
    r['related_paper_ids'] = ['paper2']
    # A paper can inform a newly researched question beyond its original tags.
    assert aq.validate_library(library, questions, papers, tmp_path) == []
    r['related_paper_ids'] = ['unknown-paper']
    assert aq.validate_library(library, questions, papers, tmp_path)
    r['related_paper_ids'] = ['paper1']
    r['figures'][0]['asset_path'] = 'assets/academic_figures/P1-001/F01.png'
    assert aq.validate_library(library, questions, papers, tmp_path)
    r['figures'][0].pop('asset_path')
    r['locales']['zh']['title'] = 'Different question'
    assert aq.validate_library(library, questions, papers, tmp_path)

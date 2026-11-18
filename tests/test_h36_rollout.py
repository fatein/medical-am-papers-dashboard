import re
from pathlib import Path

from streamlit.testing.v1 import AppTest

from dashboard.cross_data import (
    CROSS_CUTTING, H36_IDS, load_cross_analysis, load_direction_classification,
    load_questions_for_navigation, question_direction_map,
)
from dashboard.direction_reports import (
    UI, block_html, diagram_html, load_themed_report, themed_questions, validate_themed_reports,
)

ROOT = Path(__file__).resolve().parents[1]
HAN = re.compile(r'[\u3400-\u9fff]')
CITATIONS = re.compile(r'\[(R[0-9]+)\]')


def test_all_direction_reports_have_complete_locales_and_renderable_evidence():
    cross = load_cross_analysis(ROOT)
    ids = {row['question_id'] for row in cross['questions']}
    assert validate_themed_reports(ROOT, ids, 7452) == 36
    for rid in H36_IDS:
        chinese = load_themed_report(ROOT, rid, 'zh')
        expected_graph = chinese['graph']
        for code in ('zh', 'en', 'de'):
            report = load_themed_report(ROOT, rid, code)
            graph = report['graph']
            assert [(n['id'], n['stage'], n['lane'], n['refs']) for n in graph['nodes']] == [
                (n['id'], n['stage'], n['lane'], n['refs']) for n in expected_graph['nodes']]
            assert [(e['from'], e['to'], e.get('kind')) for e in graph['edges']] == [
                (e['from'], e['to'], e.get('kind')) for e in expected_graph['edges']]
            refs = {ref['id']: ref for ref in report['references']}
            body = ''.join(block_html(block, refs) for s in report['sections'] for block in s['blocks'])
            drawing = diagram_html(report, UI[code])
            assert '<svg ' in drawing and 'stroke-dasharray=' in drawing
            assert set(CITATIONS.findall(body + drawing)) <= refs.keys()
            if code != 'zh':
                assert not HAN.search(report['title'])
                assert not HAN.search(report['subtitle'])
                assert not HAN.search(report['thesis'])


def test_every_previous_question_retains_one_destination():
    original = load_cross_analysis(ROOT)
    data = load_questions_for_navigation(original, ROOT)
    classification = load_direction_classification(ROOT)
    parents = question_direction_map(classification)
    assert len(parents) == len(data['questions']) == 113
    assert sum(v != CROSS_CUTTING for v in parents.values()) == 108
    assert data['papers'] == original['papers']
    assert data['enterprise_evidence'] == original['enterprise_evidence']
    for rid in H36_IDS:
        group = next(d for d in classification['directions'] if d['id'] == rid)
        assert {q['id'] for q in themed_questions(ROOT, rid, 'de')} == set(group['questions'] + group['related'])


def test_h36_public_question_and_direction_round_trip():
    app = AppTest.from_file(str(ROOT / 'public_app.py'), default_timeout=90)
    app.query_params['lang'] = 'en'
    app.session_state['page'] = '学术与企业联系'
    app.run()
    assert not app.exception and not app.error
    app.selectbox(key='cross_direction__en').set_value('H01').run()
    assert not app.exception and not app.error
    question = app.selectbox(key='cross_question__en').value
    app.button(key='open_direction_report').click().run()
    assert not app.exception and not app.error
    assert app.query_params['direction'] == ['H01']
    assert app.get('iframe')
    app.selectbox(key='language').set_value('de').run()
    assert not app.exception and not app.error
    assert app.query_params['direction'] == ['H01']
    assert app.get('iframe')
    app.button(key='direction_report_back').click().run()
    assert app.selectbox(key='cross_direction__de').value == 'H01'
    assert app.selectbox(key='cross_question__de').value == question
    app.button(key=f'open_question_report_{question}').click().run()
    assert not app.exception and not app.error
    assert app.query_params['question'] == [question]
    app.button(key='report_back').click().run()
    assert app.selectbox(key='cross_direction__de').value == 'H01'
    assert app.selectbox(key='cross_question__de').value == question
    app.selectbox(key='cross_direction__de').set_value('H31').run()
    assert not app.exception and not app.error
    assert app.button(key='open_direction_report')
    assert len([w for w in app.selectbox if (w.key or '').startswith('cross_question__')]) == 0
    app.button(key='open_cross_cutting').click().run()
    assert not app.exception and not app.error
    assert app.selectbox(key='cross_direction__de').value == CROSS_CUTTING
    assert app.selectbox(key='cross_question__de').value in {
        'P7-105', 'P7-106', 'P7-107', 'P7-111', 'P7-113'}

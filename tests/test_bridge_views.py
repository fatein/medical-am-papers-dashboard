from pathlib import Path

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


def fixture_graph():
    return {
        'applications': [
            {'id': 'dental', 'labels': {'zh': '口腔与牙科', 'en': 'Dental', 'de': 'Zahnmedizin'}},
            {'id': 'implants', 'labels': {'zh': '植入物', 'en': 'Implants', 'de': 'Implantate'}},
        ],
        'topics': [
            {'id': 'crowns', 'applications': ['dental'], 'labels': {'zh': '牙冠', 'en': 'Crowns', 'de': 'Kronen'}},
            {'id': 'bone', 'applications': ['implants'], 'labels': {'zh': '骨', 'en': 'Bone', 'de': 'Knochen'}},
        ],
        'papers': [{'id': f'p{i}', 'title': f'原始论文 {i}', 'year': 2020,
                    'source_url': f'https://doi.org/10.1/{i}', 'applications': ['dental'],
                    'topics': ['crowns']} for i in range(30)],
        'patents': [
            {'id': 'EP1A1', 'title': '原始牙冠专利', 'year': 2021, 'source_url': 'https://example.org/EP1A1',
             'applicants': ['原始申请人'], 'family_id': 'f1', 'applications': ['dental'],
             'topics': ['crowns'], 'abstract_excerpt': '原始摘要'},
            {'id': 'EP2A1', 'title': 'Bone implant', 'year': 2022, 'source_url': 'https://example.org/EP2A1',
             'applicants': ['Other applicant'], 'family_id': 'f2', 'applications': ['implants'],
             'topics': ['bone'], 'abstract_excerpt': ''},
        ],
        'companies': [{'id': 'c1', 'name': '原始企业', 'website': 'https://example.org/company',
                       'applications': ['dental'], 'topics': ['crowns']}],
        'company_patent_links': [{'company_id': 'c1', 'patent_id': 'EP1A1',
                                  'type': 'applicant_name_match', 'applicant_name': '原始申请人'}],
        'reports': {'q1': {'id': 'q1', 'scope': 'question', 'title': '牙冠研究问题',
                            'applications': ['dental'], 'topic_ids': ['crowns'],
                            'paper_ids': ['p1'], 'company_ids': ['c1'],
                            'patent_links': [{'patent_id': 'EP1A1', 'score': 2, 'topic_ids': ['crowns'], 'matched_terms': ['crown']}]}},
    }


def fixture_app(graph=None):
    code = '''
import streamlit as st
from pathlib import Path
from dashboard.i18n import set_language, install_streamlit_translation
import dashboard.bridge_views as views
st.selectbox('Language', ['zh', 'en', 'de'], key='language')
set_language(st.session_state['language'], Path('.'))
install_streamlit_translation(st)
graph = GRAPH
original_loader = views._cached_bridge
views._cached_bridge = lambda *args: graph
if st.button('Open scoped report', key='open_scope'):
    st.query_params['view'] = 'question-report'
    st.query_params['question'] = 'q1'
    views.open_bridge_context(scope_id='q1')
if st.button('Open dental topic', key='open_topic'):
    views.open_bridge_context(application='dental', topic='crowns')
with st.sidebar:
    try:
        graph, selected = views.bridge_filters(Path('.'))
    finally:
        views._cached_bridge = original_loader
views.bridge_page(graph, selected)
'''.replace('GRAPH', repr(graph if graph is not None else fixture_graph()))
    app = AppTest.from_string(code, default_timeout=30).run()
    assert not app.exception
    return app


def test_shared_filters_pagination_and_original_source_records():
    app = fixture_app()
    assert [item.value for item in app.metric[:3]] == ['30', '2', '1']
    assert len(app.dataframe[0].value) == 25
    assert app.dataframe[0].value.iloc[0]['title'] == '原始论文 0'
    assert app.dataframe[1].value.iloc[0]['source_url'] == 'https://example.org/EP1A1'
    app.number_input(key='bridge_papers_page').set_value(2).run()
    assert len(app.dataframe[0].value) == 5
    app.selectbox(key='bridge_application__zh').set_value('dental').run()
    assert [item.value for item in app.metric[:3]] == ['30', '1', '1']
    assert app.number_input(key='bridge_papers_page').value == 1
    assert len(app.selectbox(key='bridge_topic__zh').options) == 2


def test_locale_changes_preserve_canonical_filters_and_original_titles():
    app = fixture_app()
    app.button(key='open_topic').click().run()
    for code in ('en', 'de'):
        app.selectbox(key='language').set_value(code).run()
        assert not app.exception
        assert app.selectbox(key=f'bridge_application__{code}').value == 'dental'
        assert app.selectbox(key=f'bridge_topic__{code}').value == 'crowns'
        assert app.dataframe[1].value.iloc[0]['title'] == '原始牙冠专利'
        assert any(item.value == '原始牙冠专利' for item in app.subheader)


def test_scoped_navigation_clears_report_route_and_context_can_be_reset():
    app = fixture_app()
    app.button(key='open_scope').click().run()
    assert not app.exception
    assert app.session_state['page'] == '医疗应用联动'
    assert 'view' not in app.query_params
    assert 'question' not in app.query_params
    assert app.selectbox(key='bridge_scope__zh').value == 'q1'
    assert [item.value for item in app.metric[:3]] == ['1', '1', '1']
    assert any('申请人名称对应' in item.value for item in app.caption)
    app.button(key='bridge_clear_scope').click().run()
    assert app.selectbox(key='bridge_scope__zh').value == ''
    assert app.metric[0].value == '30'
    app.text_input(key='bridge_query').set_value('nonexistent-record-keyword').run()
    assert [item.value for item in app.metric[:3]] == ['0', '0', '0']
    assert not app.dataframe
    app.button(key='bridge_reset').click().run()
    assert [item.value for item in app.metric[:3]] == ['30', '2', '1']


def test_company_without_website_uses_its_original_evidence_source():
    graph = fixture_graph()
    graph['companies'][0]['website'] = ''
    graph['companies'][0]['source_urls'] = ['https://example.org/original-company-evidence']
    app = fixture_app(graph)
    assert app.dataframe[2].value.iloc[0]['source_url'] == graph['companies'][0]['source_urls'][0]
    assert any(element.proto.url == graph['companies'][0]['source_urls'][0]
               for element in app.get('link_button'))

def test_public_navigation_loads_complete_snapshot_and_all_report_scopes():
    from dashboard.bridge_data import load_bridge, select_bridge

    graph = load_bridge(ROOT)
    app = AppTest.from_file(str(ROOT/'public_app.py'), default_timeout=60).run()
    app.selectbox(key='language').set_value('zh').run()
    app.radio(key='page__zh').set_value('医疗应用联动').run()
    assert not app.exception
    assert [item.value for item in app.metric[:3]] == ['7,169', '5,516', '352']
    assert len(app.selectbox(key='bridge_scope__zh').options) == 149
    scope = next(key for key, row in graph['reports'].items() if row['patent_links'])
    app.selectbox(key='bridge_scope__zh').set_value(scope).run()
    expected = select_bridge(graph, scope_id=scope)
    assert not app.exception
    assert [item.value for item in app.metric[:3]] == [
        f'{len(expected[kind]):,}' for kind in ('papers', 'patents', 'companies')]
    for code, nav in [('en', 'Linked evidence'), ('de', 'Verknüpfte Evidenz')]:
        app.selectbox(key='language').set_value(code).run()
        assert not app.exception
        assert nav in app.radio(key=f'page__{code}').options
        assert app.selectbox(key=f'bridge_scope__{code}').value == scope
        expected_title = graph['reports'][scope]['labels'][code]
        assert any(expected_title in option for option in app.selectbox(key=f'bridge_scope__{code}').options)
        assert any(expected_title in item.value for item in app.caption)
    app.button(key='bridge_clear_scope').click().run()
    assert not app.exception
    assert [item.value for item in app.metric[:3]] == ['7,169', '5,516', '352']
    excluded = next(row for row in graph['patents']
                    if row.get('association_status') == 'excluded_nonmedical_context')
    app.text_input(key='bridge_query').set_value(excluded['id']).run()
    assert not app.exception
    assert app.metric[1].value == '1'
    assert any('eindeutig nichtmedizinischen Kontext' in item.value for item in app.caption)
    assert any(item.value == excluded['association_reason'] for item in app.text)
    app.selectbox(key='bridge_application__de').set_value('dental').run()
    assert app.metric[1].value == '0'
    app.button(key='bridge_reset').click().run()
    assert not app.exception
    assert [item.value for item in app.metric[:3]] == ['7,169', '5,516', '352']


def test_record_details_expose_original_topic_matching_evidence_in_every_locale():
    graph = fixture_graph()
    graph['patents'][0]['topic_evidence'] = [
        {'topic_id': 'crowns', 'matched_terms': ['crown'], 'excerpt': '原始细分主题证据'}]
    app = fixture_app(graph)
    for code in ('zh', 'en', 'de'):
        app.selectbox(key='language').set_value(code).run()
        assert not app.exception
        assert any(item.value == '原始细分主题证据' for item in app.text)
        assert any(item.value == 'crown' for item in app.text)

def test_unknown_report_context_stays_empty_until_explicitly_cleared():
    app = fixture_app()
    app.session_state['bridge_scope'] = 'removed-report-scope'
    app.run()
    assert not app.exception
    assert [item.value for item in app.metric[:3]] == ['0', '0', '0']
    assert app.selectbox(key='bridge_scope__zh').value == 'removed-report-scope'
    app.button(key='bridge_clear_scope').click().run()
    assert [item.value for item in app.metric[:3]] == ['30', '2', '1']

def test_report_scope_labels_follow_locale_and_keep_scope_id():
    graph = fixture_graph()
    graph['reports']['q1']['labels'] = {'zh': '牙冠研究问题', 'en': 'Crown research question',
                                       'de': 'Forschungsfrage Kronen'}
    app = fixture_app(graph)
    app.button(key='open_scope').click().run()
    for code, title in [('en', 'Crown research question'), ('de', 'Forschungsfrage Kronen')]:
        app.selectbox(key='language').set_value(code).run()
        assert not app.exception
        assert app.selectbox(key=f'bridge_scope__{code}').value == 'q1'
        assert any(title in option for option in app.selectbox(key=f'bridge_scope__{code}').options)
        assert any(title in item.value for item in app.caption)

def test_excluded_nonmedical_patent_explains_why_its_original_record_is_retained():
    graph = fixture_graph()
    graph['patents'][0].update(association_status='excluded_nonmedical_context',
                               association_reason='原始非医疗语境依据', applications=[], topics=[])
    app = fixture_app(graph)
    for code, phrase in [('zh', '明确非医疗语境'), ('en', 'explicit nonmedical context'),
                         ('de', 'eindeutig nichtmedizinischen Kontext')]:
        app.selectbox(key='language').set_value(code).run()
        assert not app.exception
        assert app.metric[1].value == '2'
        assert any(phrase in item.value for item in app.caption)
        assert any(item.value == '原始非医疗语境依据' for item in app.text)

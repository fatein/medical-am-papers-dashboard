from pathlib import Path
import pytest
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('code,removed_label', [
    ('zh', '医疗应用联动'), ('en', 'Linked evidence'), ('de', 'Verknüpfte Evidenz'),
])
def test_removed_page_is_absent_and_stale_session_recovers_to_papers(code, removed_label):
    app = AppTest.from_file(str(ROOT/'public_app.py'), default_timeout=90)
    app.query_params['lang'] = code
    # Simulate a browser session restored from the previous release.
    for key in ('page', '_am_selected_page', f'page__{code}'):
        app.session_state[key] = '医疗应用联动'
    app.run()
    assert not app.exception
    navigation = app.radio(key=f'page__{code}')
    assert removed_label not in navigation.options
    assert navigation.value == '论文总览'
    assert app.session_state['page'] == '论文总览'
    assert app.metric and app.get('plotly_chart')
    assert not any((button.key or '').startswith('bridge_') for button in app.button)


@pytest.mark.parametrize('page,expected_widget', [
    ('论文检索', 'query'), ('专利检索', 'patent_query'), ('企业检索', 'enterprise_query'),
])
def test_remaining_search_pages_render_real_records(page, expected_widget):
    app = AppTest.from_file(str(ROOT/'public_app.py'), default_timeout=90)
    app.query_params['lang'] = 'zh'
    app.run()
    app.radio(key='page__zh').set_value(page).run()
    assert not app.exception
    assert app.session_state['page'] == page
    assert app.text_input(key=expected_widget)
    assert any(not frame.value.empty for frame in app.dataframe)

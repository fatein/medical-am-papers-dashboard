from pathlib import Path

from streamlit.testing.v1 import AppTest

from dashboard.patent_data import filter_patents, load_patents

ROOT = Path(__file__).resolve().parents[1]


def open_patents():
    app = AppTest.from_file(str(ROOT/'public_app.py'), default_timeout=60).run()
    app.selectbox(key='language').set_value('zh').run()
    app.radio(key='page__zh').set_value('专利检索').run()
    assert not app.exception
    return app


def test_public_patents_show_strict_count_and_exact_original_links():
    app = open_patents()
    assert app.metric[0].value == '5,516'
    assert app.metric[1].value == '4,862'
    assert len(app.dataframe[0].value) == 25
    ident = app.selectbox(key='patent_record').value
    links = app.get('link_button')
    assert any('pn%3D'+ident in element.proto.url for element in links)
    assert not any(w.key == 'years' for w in app.slider)


def test_patent_filters_combine_and_empty_results_reset_cleanly():
    app = open_patents()
    source = load_patents(ROOT)
    sample = source[source.medical_categories.map(lambda v:'dental' in v)].iloc[0]
    name = sample.applicants[0]
    year = int(sample.publication_year)
    app.number_input(key='patent_page').set_value(2).run()
    app.multiselect(key='patent_applications__zh').set_value(['dental']).run()
    app.multiselect(key='patent_applicants').set_value([name]).run()
    app.slider(key='patent_years').set_value((year,year)).run()
    expected = filter_patents(source, applications=['dental'], applicants=[name], years=(year,year))
    assert not app.exception
    assert app.metric[0].value == f'{len(expected):,}'
    assert app.number_input(key='patent_page').value == 1
    assert set(app.selectbox(key='patent_record').options) <= set(expected.publication_id)
    app.text_input(key='patent_query').set_value('nonexistent-unique-patent-query').run()
    assert not app.exception
    assert app.metric[0].value == '0'
    assert not app.dataframe
    app.button(key='patent_reset').click().run()
    assert not app.exception
    assert app.metric[0].value == '5,516'


def test_patent_locale_switch_keeps_filter_and_original_metadata():
    app = open_patents()
    app.multiselect(key='patent_applications__zh').set_value(['dental']).run()
    count = app.metric[0].value
    for code, nav in [('en','Search patents'),('de','Patente suchen')]:
        app.selectbox(key='language').set_value(code).run()
        assert not app.exception
        assert nav in app.radio(key=f'page__{code}').options
        assert app.multiselect(key=f'patent_applications__{code}').value == ['dental']
        assert app.metric[0].value == count
        ident = app.selectbox(key='patent_record').value
        original = load_patents(ROOT).set_index('publication_id').loc[ident]
        assert any(value.value == original.title for value in app.subheader)

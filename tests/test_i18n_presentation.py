"""Regression checks for translated chart and table presentation contracts."""
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import plotly.graph_objects as go
import pytest

from dashboard.i18n import (install_streamlit_translation, set_language, tr,
                            _translate_figure)

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('code', ['en', 'de'])
def test_heatmap_colorbar_and_scalar_hover_text(code):
    chart = go.Figure(go.Heatmap(z=[[3]], colorbar={'title': '篇数'}))
    chart.add_trace(go.Scatter(x=[1], y=[3], hovertext='论文数量'))
    try:
        set_language(code, ROOT)
        translated = _translate_figure(chart)
        assert translated.data[0].colorbar.title.text == tr('篇数')
        assert translated.data[1].hovertext == tr('论文数量')
        assert chart.data[0].colorbar.title.text == '篇数'
    finally:
        set_language('zh', ROOT)


def test_table_configuration_keeps_translated_column_identity():
    def capture(*args, **kwargs):
        return args, kwargs
    fake = SimpleNamespace(dataframe=capture)
    try:
        set_language('en', ROOT)
        install_streamlit_translation(fake)
        (frame,), config = fake.dataframe(
            pd.DataFrame({'企业': ['Example'], '产品／技术概况': ['产品发布']}),
            column_config={'企业': {'label': '企业', 'help': '选择企业'},
                           '产品／技术概况': {'label': '产品／技术概况'}},
            column_order=['企业', '产品／技术概况'])
        assert list(config['column_config']) == list(frame.columns)
        assert config['column_order'] == list(frame.columns)
        assert config['column_config'][tr('企业')]['label'] == tr('企业')
    finally:
        set_language('zh', ROOT)


def test_nested_option_formatter_retains_its_locale_outside_render_context():
    fake = SimpleNamespace(selectbox=lambda *args, **kwargs: kwargs['format_func'])
    try:
        set_language('de', ROOT)
        install_streamlit_translation(fake)
        fmt = fake.selectbox('选择一条事件', [0], format_func=lambda _: tr('研究问题'))
        set_language('en', ROOT)
        assert fmt(0) == 'Forschungsfrage'
        assert tr('研究问题') == 'Research question'
    finally:
        set_language('zh', ROOT)


def test_translated_category_positions_keep_their_order():
    chart = go.Figure(go.Scatter(x=['2025', '现状'], y=[1, 2]))
    chart.update_xaxes(categoryorder='array', categoryarray=['2025', '现状'])
    try:
        set_language('de', ROOT)
        result = _translate_figure(chart)
        assert list(result.layout.xaxis.categoryarray) == list(result.data[0].x)
    finally:
        set_language('zh', ROOT)


@pytest.mark.parametrize('code,unit,page', [('en','papers','Page'), ('de','Publikationen','Seite')])
def test_count_and_pagination_sentences_use_contextual_units(code,unit,page):
    from dashboard.i18n import ui_format
    try:
        set_language(code, ROOT)
        result = ui_format('paper_pages',count=7169,page=1,pages=144)
        assert f'7,169 {unit}' in result
        assert f'{page} 1/144' in result
        assert 'Chapter' not in result
    finally:
        set_language('zh', ROOT)


def test_dynamic_labels_preserve_a_protected_company_name(monkeypatch):
    import dashboard.i18n as i18n
    source_name = '测试医疗科技有限公司'
    i18n.protect_names([source_name])
    monkeypatch.setattr(i18n, '_catalogue', lambda *_: {source_name: 'Incorrect renamed company'})
    try:
        set_language('en', ROOT)
        assert tr(f'2025 · {source_name} · 产品发布') == f'2025 · {source_name} · Product launch'
    finally:
        set_language('zh', ROOT)


def test_german_country_labels_localize_english_source_values():
    assert tr('Czech Republic',code='de',root=ROOT) == 'Tschechien'
    assert tr('Bulgaria',code='de',root=ROOT) == 'Bulgarien'
    assert tr('LT',code='de',root=ROOT) == 'Litauen'
    assert tr('LT',code='en',root=ROOT) == 'Lithuania'
    assert tr('Example Company Ltd.',code='de',root=ROOT) == 'Example Company Ltd.'


def test_runtime_catalogue_is_not_overridden_by_old_development_files(tmp_path):
    import json
    from dashboard.i18n import _catalogue
    (tmp_path/'data/i18n').mkdir(parents=True)
    (tmp_path/'scripts').mkdir()
    (tmp_path/'data/i18n/en.json').write_text(json.dumps({'问题': 'Reviewed question'}),'utf8')
    (tmp_path/'scripts/question_titles_en.json').write_text(json.dumps({'P1-001':'Obsolete translation'}),'utf8')
    (tmp_path/'data/cross_analysis.json').write_text(json.dumps({'questions':[{'question_id':'P1-001','question':'问题'}]}),'utf8')
    assert _catalogue(str(tmp_path),'en')['问题'] == 'Reviewed question'


def test_localized_selectbox_respects_navigation_and_changed_options():
    from dashboard.i18n import localized_selectbox
    state={}
    def selectbox(label,options,key,**kwargs):
        return state.setdefault(key,options[0])
    fake=SimpleNamespace(session_state=state,selectbox=selectbox)
    try:
        set_language('en',ROOT)
        assert localized_selectbox(fake,'方向',['A','B'],key='direction')=='A'
        state['direction']='B'  # A table or report-return callback chooses B.
        assert localized_selectbox(fake,'方向',['A','B'],key='direction')=='B'
        assert localized_selectbox(fake,'方向',['C'],key='direction')=='C'
        assert state['direction']=='C'
        set_language('de',ROOT)
        assert localized_selectbox(fake,'方向',['C'],key='direction')=='C'
        assert 'direction__de' in state
    finally:
        set_language('zh',ROOT)

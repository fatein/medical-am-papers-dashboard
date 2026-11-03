import csv
import json
import re
from types import SimpleNamespace
from pathlib import Path

import pytest
import pandas as pd
import plotly.express as px
from streamlit.testing.v1 import AppTest

from dashboard.i18n import (hero_metadata, preserve_original_text,
                            protect_names, set_language, tr, year_papers_label,
                            install_streamlit_translation,
                            _translate_figure)
from dashboard.report_views import render_cited_markdown

ROOT = Path(__file__).resolve().parents[1]


def test_language_lookup_and_original_names():
    protect_names(['测试医疗科技有限公司', '个体化植入物研究'])
    try:
        set_language('en', ROOT)
        assert tr('论文总览') == 'Paper overview'
        assert tr('P2 · 假体与修复体') == 'P2 · Prostheses and restorations'
        assert tr('T3 · 粉床熔融') == 'T3 · Powder bed fusion'
        assert tr('材料挤出') == 'Material extrusion'
        assert year_papers_label(2026) == 'Papers in 2026'
        assert '7,169 papers selected' in hero_metadata(2010, 2026, 7169, True)
        assert tr('测试医疗科技有限公司') == '测试医疗科技有限公司'
        assert tr('个体化植入物研究') == '个体化植入物研究'
        with preserve_original_text():
            assert tr('骨整合与抗感染') == '骨整合与抗感染'
        assert tr('骨整合与抗感染') == 'Osseointegration and infection control'
        set_language('de', ROOT)
        assert tr('研究问题') == 'Forschungsfrage'
        assert tr('T1 · 槽式光聚合') == 'T1 · Badbasierte Photopolymerisation'
        assert tr('假肢接受腔') == 'Prothesenschäfte'
        assert year_papers_label(2026) == 'Publikationen 2026'
        assert '7,169 Publikationen ausgewählt' in hero_metadata(2010, 2026, 7169, True)
    finally:
        set_language('zh', ROOT)


def test_browser_language_value_stays_valid_after_switching_back_and_navigating():
    """A browser may resend the previous locale's displayed selection on its next event."""
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60).run()
    app.selectbox(key='language').set_value('de').run()
    browser_chinese_label = app.selectbox(key='language').options[0]
    app.selectbox(key='language').set_value('zh').run()
    assert not app.exception
    states = app._tree.get_widget_states()
    language_id = app.selectbox(key='language').id
    for widget in states.widgets:
        if widget.id == language_id:
            widget.string_value = browser_chinese_label
    app._run(states)
    assert not app.exception
    assert app.selectbox(key='language').value == 'zh'
    assert app.selectbox(key='language').options == ['中文', 'English', 'Deutsch']


def test_report_citation_survives_localization():
    report = json.loads((ROOT/'data/question_reports.json').read_text(encoding='utf-8'))['reports']['P1-004']
    try:
        for language in ('en', 'de'):
            set_language(language, ROOT)
            rendered = render_cited_markdown(report['sections'][0], report['references'])
            assert 'ref:' not in rendered
            assert 'href="https://' in rendered
            assert 'target="_blank"' in rendered
            assert '。' not in rendered
    finally:
        set_language('zh', ROOT)


def test_english_navigation_keeps_internal_pages_and_filters():
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60).run()
    app.selectbox(key='language').set_value('en').run()
    assert not app.exception
    pages = app.radio(key='page')
    assert 'Paper overview' in pages.options
    pages.set_value('学术与企业联系').run()
    assert not app.exception
    assert app.radio(key='page').value == '学术与企业联系'
    assert app.selectbox(key='language').value == 'en'
    app.selectbox(key='language').set_value('de').run()
    assert not app.exception
    assert 'Forschung und Industrie' in app.radio(key='page').options


def test_language_switch_remounts_selected_filters_without_losing_values():
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60).run()
    app.multiselect(key='p_layers__zh').set_value(['P1']).run()
    assert app.multiselect(key='p_layers__zh').value == ['P1']
    app.selectbox(key='language').set_value('en').run()
    english = app.multiselect(key='p_layers__en')
    assert english.value == ['P1']
    assert any('Surgical and dental implants' in item for item in english.options)
    app.selectbox(key='language').set_value('de').run()
    german = app.multiselect(key='p_layers__de')
    assert german.value == ['P1']
    assert any('Chirurgische und dentale Implantate' in item for item in german.options)


def test_enterprise_observation_with_trailing_newline_is_translated():
    observations = [json.loads(line) for line in
                    (ROOT/'data/enterprise_observations.jsonl').read_text(encoding='utf-8').splitlines()
                    if line.strip()]
    record = next(row for row in observations
                  if '3D-Skull' in row['title'] and row['title'].endswith('\n'))
    title = record['title']
    for code in ('en', 'de'):
        rendered = tr(title, code=code, root=ROOT)
        assert not re.search(r'[\u3400-\u9fff]', rendered)
        assert 'will' not in rendered.lower() if code == 'en' else 'wird' not in rendered.lower()
        assert 'Customize' in tr(record['product_summary'], code=code, root=ROOT)


def test_german_catalogue_preserves_trabecular_titanium_brand():
    catalogue = json.loads((ROOT/'data/i18n/de.json').read_text(encoding='utf-8'))
    assert not any('Titaniumium' in translated for translated in catalogue.values())


@pytest.mark.parametrize('code', ['en', 'de'])
def test_chart_legend_title_is_translated(code):
    chart = px.scatter([{'year': 2025, '节点类型': '产品发布'}],
                       x='year', color='节点类型')
    try:
        set_language(code, ROOT)
        translated = _translate_figure(chart)
        assert translated.layout.legend.title.text == tr('节点类型')
    finally:
        set_language('zh', ROOT)


def test_streamlit_translation_rebinds_after_module_hot_reload(monkeypatch):
    import streamlit.delta_generator as generator

    def original(value):
        return value

    def translated(value):
        return original(value)  # A wrapper left by a previous module version.

    translated.__wrapped__ = original
    fake_streamlit = SimpleNamespace(markdown=translated, _am_i18n_installed=True)

    def class_original(self, value):
        return value

    def class_translated(self, value):
        return class_original(self, value)

    class_translated.__wrapped__ = class_original

    class FakeDeltaGenerator:
        markdown = class_translated

    monkeypatch.setattr(generator, 'DeltaGenerator', FakeDeltaGenerator)
    try:
        set_language('en', ROOT)
        install_streamlit_translation(fake_streamlit)
        assert fake_streamlit.markdown('研究问题') == 'Research question'
        assert FakeDeltaGenerator().markdown('研究问题') == 'Research question'
    finally:
        set_language('zh', ROOT)


@pytest.mark.parametrize('code', ['en', 'de'])
def test_company_event_headers_translate_the_complete_title(code):
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60).run()
    app.selectbox(key='language').set_value(code).run()
    app.session_state['page'] = '企业检索'
    app.session_state['enterprise_selected_company'] = '3D Industrial Imaging Co., Ltd.'
    app.run()
    assert not app.exception
    event_headers = [item.label for item in app.expander]
    assert event_headers
    assert not any(re.search(r'[\u3400-\u9fff]', title) for title in event_headers)


@pytest.mark.parametrize('code', ['en', 'de'])
def test_company_timeline_preview_translates_newline_terminated_record(code):
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60).run()
    app.selectbox(key='language').set_value(code).run()
    app.radio(key='page').set_value('技术路线图').run()
    assert not app.exception
    table = next(item.value for item in app.dataframe
                 if item.key == 'enterprise_timeline_brief')
    row = table.loc[table.iloc[:, 0].eq('3D-Side S.A.')]
    assert len(row) == 1
    assert not re.search(r'[\u3400-\u9fff]', row.iloc[0, 1])


def test_western_named_company_content_has_no_chinese_after_translation():
    with (ROOT/'data/enterprises.csv').open(encoding='utf-8-sig', newline='') as file:
        names = {row['company_id']: row['name'] for row in csv.DictReader(file)}
    sources = (
        ('enterprise_observations.jsonl', ('title', 'product_summary', 'technology_summary')),
        ('enterprise_events.jsonl', ('title', 'detail', 'technology', 'material')),
    )
    for file_name, fields in sources:
        for line in (ROOT/'data'/file_name).read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if re.search(r'[\u3400-\u9fff]', names[row['company_id']]):
                continue  # Chinese company names remain as supplied.
            for field in fields:
                for code in ('en', 'de'):
                    rendered = tr(row.get(field, ''), code=code, root=ROOT)
                    # Literal Chinese company names/aliases and registration
                    # prefixes remain original even in an English-named record.
                    inspected = re.sub(r'上海三友医疗|三迭纪|国械注准', '', rendered)
                    assert not re.search(r'[\u3400-\u9fff]', inspected), (
                        code, names[row['company_id']], file_name, field)


def test_all_enterprise_country_filters_are_translated():
    source_countries = set(pd.read_csv(ROOT/'data/enterprises.csv')['country'].dropna())
    additions_path = ROOT/'data/enterprise_cross_additions.json'
    additions = json.loads(additions_path.read_text(encoding='utf-8')) if additions_path.exists() else []
    source_countries.update(row['country'] for row in additions)
    for code in ('en', 'de'):
        untranslated = [country for country in source_countries
                        if re.search(r'[\u3400-\u9fff]', tr(str(country), code=code, root=ROOT))]
        assert not untranslated, (code, untranslated)


@pytest.mark.parametrize('code', ('en', 'de'))
def test_timeline_company_selector_refreshes_after_language_change(code):
    app = AppTest.from_file(str(ROOT/'app.py'), default_timeout=60).run()
    app.radio(key='page').set_value('技术路线图').run()
    app.selectbox(key='enterprise_timeline_company__zh').set_value('3D-Side S.A.').run()
    app.selectbox(key='language').set_value(code).run()
    assert not app.exception
    assert app.selectbox(key=f'enterprise_timeline_company__{code}').value == '3D-Side S.A.'

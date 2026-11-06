"""Shared medical-application exploration of papers, patents and company evidence."""
from __future__ import annotations

import html
import json
import math
from pathlib import Path

import pandas as pd
import streamlit as st

from dashboard.i18n import (clear_localized_selection, language, localized_selectbox,
                            preserve_original_text)
from dashboard.report_navigation import clear_report_route

_COPY = {
    'title': ('医疗应用联动', 'Linked evidence', 'Verknüpfte Evidenz'),
    'intro': ('在同一医疗应用与细分主题下浏览论文、专利公开记录和企业档案。', 'Explore papers, patent publications and company profiles under a shared medical application and specific topic.', 'Publikationen, Patentveröffentlichungen und Unternehmensprofile nach gemeinsamer medizinischer Anwendung und konkretem Thema erkunden.'),
    'application': ('医疗应用', 'Medical application', 'Medizinische Anwendung'),
    'topic': ('细分主题', 'Specific topic', 'Konkretes Thema'),
    'all_applications': ('全部医疗应用', 'All medical applications', 'Alle medizinischen Anwendungen'),
    'all_topics': ('全部细分主题', 'All specific topics', 'Alle konkreten Themen'),
    'scope_options': ('报告范围（可选）', 'Report scope (optional)', 'Berichtsbereich (optional)'),
    'scope': ('报告范围', 'Report scope', 'Berichtsbereich'),
    'all_reports': ('不限报告范围', 'All report scopes', 'Alle Berichtsbereiche'),
    'unknown_scope': ('无法识别的报告范围：{scope}', 'Unknown report scope: {scope}', 'Unbekannter Berichtsbereich: {scope}'),
    'active_scope': ('当前报告范围：{title}', 'Current report scope: {title}', 'Aktueller Berichtsbereich: {title}'),
    'clear_scope': ('清除报告范围', 'Clear report scope', 'Berichtsbereich löschen'),
    'query': ('题名／公开号／企业检索', 'Search titles / publication numbers / companies', 'Titel / Publikationsnummern / Unternehmen suchen'),
    'reset': ('重置联动筛选', 'Reset linked filters', 'Verknüpfte Filter zurücksetzen'),
    'papers': ('论文', 'Papers', 'Publikationen'),
    'patents': ('专利公开记录', 'Patent publications', 'Patentveröffentlichungen'),
    'companies': ('企业档案', 'Company profiles', 'Unternehmensprofile'),
    'empty': ('当前条件没有匹配记录。请调整筛选或重置联动筛选。', 'No records match these filters. Adjust or reset the linked filters.', 'Keine Einträge für diese Filter. Filter anpassen oder zurücksetzen.'),
    'empty_type': ('此范围内没有此类记录。', 'No records of this type in the current scope.', 'Keine Einträge dieser Art im aktuellen Bereich.'),
    'page': ('结果页', 'Results page', 'Ergebnisseite'),
    'range': ('第 {start:,}–{end:,} 条，共 {total:,} 条 · {pages:,} 页', 'Records {start:,}–{end:,} of {total:,} · {pages:,} pages', 'Einträge {start:,}–{end:,} von {total:,} · {pages:,} Seiten'),
    'id': ('记录编号', 'Record ID', 'Datensatz-ID'),
    'original_title': ('原始题名', 'Original title', 'Originaltitel'),
    'original_name': ('原始企业名称', 'Original company name', 'Originaler Unternehmensname'),
    'year': ('发表／公开年份', 'Publication year', 'Veröffentlichungsjahr'),
    'applicants': ('原始申请人', 'Original applicants', 'Originalanmelder'),
    'source': ('原始来源', 'Original source', 'Originalquelle'),
    'open': ('打开原始来源 ↗', 'Open original source ↗', 'Originalquelle öffnen ↗'),
    'details': ('查看本页记录详情', 'View details for a record on this page', 'Details zu einem Eintrag dieser Seite ansehen'),
    'topics': ('主题对应', 'Topic alignment', 'Thematische Zuordnung'),
    'no_topic': ('未识别细分主题', 'No specific topic identified', 'Kein konkretes Thema erkannt'),
    'topic_evidence': ('主题匹配依据', 'Topic matching evidence', 'Belege der thematischen Zuordnung'),
    'family': ('已知同族编号', 'Observed family ID', 'Bekannte Familien-ID'),
    'missing': ('未提供', 'Not provided', 'Nicht angegeben'),
    'excerpt': ('原始摘要节选', 'Original abstract excerpt', 'Auszug aus der Originalzusammenfassung'),
    'name_matches': ('申请人名称对应', 'Applicant-name correspondences', 'Anmeldernamensentsprechungen'),
    'no_name_matches': ('暂无申请人名称对应。', 'No applicant-name correspondence.', 'Keine Anmeldernamensentsprechung.'),
    'load_error': ('联动数据暂时无法读取，请稍后重试。', 'Linked evidence could not be loaded. Please try again later.', 'Verknüpfte Evidenz konnte nicht geladen werden. Bitte später erneut versuchen.'),
}


def text(key):
    return _COPY[key][{'zh': 0, 'en': 1, 'de': 2}.get(language(), 0)]


def _label(row):
    labels = row.get('labels', {})
    return labels.get(language()) or labels.get('en') or row['id']


def _report_title(row):
    return row.get('labels', {}).get(language()) or row.get('title') or row.get('id', '')


@st.cache_data(show_spinner=False)
def _cached_bridge(root, signature):
    from dashboard.bridge_data import load_bridge
    return load_bridge(Path(root))


def _clear_results():
    for kind in ('papers', 'patents', 'companies'):
        st.session_state.pop(f'bridge_{kind}_page', None)
        clear_localized_selection(st.session_state, f'bridge_{kind}_record')
    st.session_state.pop('_bridge_filter_signature', None)


def reset_bridge_filters():
    for key in ('bridge_application', 'bridge_topic', 'bridge_scope'):
        clear_localized_selection(st.session_state, key)
    st.session_state.pop('bridge_query', None)
    _clear_results()


def clear_bridge_scope():
    clear_localized_selection(st.session_state, 'bridge_scope')
    _clear_results()


def open_bridge_context(scope_id='', application='', topic=''):
    """Navigate from a report while preserving IDs independent of visitor locale."""
    clear_report_route()
    reset_bridge_filters()
    st.session_state['page'] = '医疗应用联动'
    st.session_state['bridge_scope'] = str(scope_id or '')
    st.session_state['bridge_application'] = str(application or '')
    st.session_state['bridge_topic'] = str(topic or '')


def _valid_choice(key, options):
    saved = st.session_state.get(key, st.session_state.get(f'_am_selected_{key}', ''))
    if saved not in options:
        clear_localized_selection(st.session_state, key)


def bridge_filters(root):
    root = Path(root)
    try:
        paths = [root/'data'/name for name in ('patent_bridge.json.gz', 'patent_bridge_manifest.json')]
        signature = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in paths if p.exists())
        graph = _cached_bridge(str(root), signature)
    except (OSError, ValueError, KeyError):
        st.error(text('load_error'))
        st.stop()
    applications = {row['id']: _label(row) for row in graph['applications']}
    _valid_choice('bridge_application', ['', *applications])
    application = localized_selectbox(st, text('application'), ['', *applications],
        key='bridge_application', format_func=lambda value: applications.get(value, text('all_applications')))
    topics = {row['id']: _label(row) for row in graph['topics']
              if not application or application in row.get('applications', [])}
    _valid_choice('bridge_topic', ['', *topics])
    topic = localized_selectbox(st, text('topic'), ['', *topics], key='bridge_topic',
                               format_func=lambda value: topics.get(value, text('all_topics')))
    reports = graph.get('reports', {})
    scope_options = ['', *reports]
    saved_scope = st.session_state.get('bridge_scope', st.session_state.get('_am_selected_bridge_scope', ''))
    if saved_scope and saved_scope not in reports:
        scope_options.append(saved_scope)
    with st.expander(text('scope_options'), expanded=bool(st.session_state.get('bridge_scope'))):
        scope = localized_selectbox(st, text('scope'), scope_options, key='bridge_scope',
            format_func=lambda value: (f"{value} · {_report_title(reports[value])}"
                                       if value in reports else text('unknown_scope').format(scope=value)
                                       if value else text('all_reports')))
        if scope:
            st.button(text('clear_scope'), key='bridge_clear_scope', on_click=clear_bridge_scope,
                      width='stretch')
    query = st.text_input(text('query'), key='bridge_query')
    st.button(text('reset'), key='bridge_reset', on_click=reset_bridge_filters, width='stretch')
    selection = dict(application=application or None, topic=topic or None, scope_id=scope or None, query=query)
    current = json.dumps(selection, sort_keys=True, ensure_ascii=False)
    if st.session_state.get('_bridge_filter_signature') != current:
        _clear_results()
        st.session_state['_bridge_filter_signature'] = current
    return graph, selection


def _source_url(row):
    return (row.get('source_url') or row.get('website')
            or next(iter(row.get('source_urls', [])), ''))


def _source_button(row):
    url = _source_url(row)
    if url:
        st.link_button(text('open'), url)


def _applicant_correspondences(graph, row, kind):
    if kind not in ('patents', 'companies'):
        return
    st.caption(text('name_matches'))
    key = 'patent_id' if kind == 'patents' else 'company_id'
    matches = [edge for edge in graph.get('company_patent_links', [])
               if edge.get('type') == 'applicant_name_match' and edge.get(key) == row['id']]
    if not matches:
        st.caption(text('no_name_matches'))
        return
    companies = {item['id']: item for item in graph['companies']}
    patents = {item['id']: item for item in graph['patents']}
    for edge in matches:
        other = (companies.get(edge['company_id']) if kind == 'patents'
                 else patents.get(edge['patent_id']))
        if not other:
            continue
        with preserve_original_text():
            st.text(f"{other.get('name') or other.get('title') or other['id']} · {edge['applicant_name']}")
        _source_button(other)


def _entity_tab(graph, records, kind):
    if not records:
        st.info(text('empty_type'))
        return
    pages = math.ceil(len(records)/25)
    page_key = f'bridge_{kind}_page'
    if not 1 <= int(st.session_state.get(page_key, 1)) <= pages:
        st.session_state[page_key] = 1
    page = int(st.number_input(text('page'), min_value=1, max_value=pages,
                               value=1, step=1, key=page_key))
    start = (page-1)*25
    shown = records[start:start+25]
    st.caption(text('range').format(start=start+1, end=start+len(shown), total=len(records), pages=pages))
    name_field = 'name' if kind == 'companies' else 'title'
    fields = ['id', name_field]
    if kind != 'companies':
        fields.append('year')
    if kind == 'patents':
        fields.append('applicants')
    table = pd.DataFrame([{**{field: record.get(field, '') for field in fields},
                            'source_url': _source_url(record)}
                           for record in shown])
    if 'applicants' in table:
        table['applicants'] = table.applicants.map(lambda values: '; '.join(values))
    config = {'id': st.column_config.TextColumn(text('id')),
              name_field: st.column_config.TextColumn(text('original_name' if kind == 'companies' else 'original_title')),
              'source_url': st.column_config.LinkColumn(text('source'), display_text=text('open'))}
    if 'year' in table:
        config['year'] = st.column_config.NumberColumn(text('year'), format='%d')
    if 'applicants' in table:
        config['applicants'] = st.column_config.TextColumn(text('applicants'))
    with preserve_original_text():
        st.dataframe(table, hide_index=True, width='stretch', column_config=config)
    choices = {row['id']: row for row in shown}
    key = f'bridge_{kind}_record'
    _valid_choice(key, choices)
    selected = localized_selectbox(st, text('details'), list(choices), key=key)
    row = choices[selected]
    topic_labels = {item['id']: _label(item) for item in graph['topics']}
    with st.container(border=True):
        with preserve_original_text():
            st.subheader(row.get(name_field) or row['id'])
            if kind == 'patents':
                st.text('; '.join(row.get('applicants', [])))
        st.caption(f"{text('topics')}: " + ('; '.join(topic_labels.get(value, value) for value in row.get('topics', []))
                                           or text('no_topic')))
        if kind == 'patents':
            st.caption(f"{text('family')}: {row.get('family_id') or text('missing')}")
            if row.get('abstract_excerpt'):
                st.caption(text('excerpt'))
                with preserve_original_text():
                    st.text(row['abstract_excerpt'])
        if row.get('topic_evidence'):
            with st.expander(text('topic_evidence')):
                for evidence in row['topic_evidence']:
                    st.caption(topic_labels.get(evidence.get('topic_id'), evidence.get('topic_id', '')))
                    with preserve_original_text():
                        st.text('; '.join(evidence.get('matched_terms', [])))
                        if evidence.get('excerpt'):
                            st.text(evidence['excerpt'])
        _source_button(row)
        _applicant_correspondences(graph, row, kind)


def bridge_page(graph, selection):
    from dashboard.bridge_data import select_bridge
    selected = select_bridge(graph, **selection)
    st.markdown('<div class="hero"><div class="eyebrow">MEDICAL ADDITIVE MANUFACTURING</div>'
                f'<h1>{html.escape(text("title"))}</h1><p>{html.escape(text("intro"))}</p></div>',
                unsafe_allow_html=True)
    for column, kind in zip(st.columns(3), ('papers', 'patents', 'companies')):
        column.metric(text(kind), f'{len(selected[kind]):,}')
    scope = graph.get('reports', {}).get(selection.get('scope_id'))
    if scope:
        caption = text('active_scope').format(title=_report_title(scope))
        with preserve_original_text():
            st.caption(caption)
    if not any(selected[kind] for kind in ('papers', 'patents', 'companies')):
        st.info(text('empty'))
        return
    tabs=st.tabs([text('papers'),text('patents'),text('companies')])
    for tab, kind in zip(tabs,
                         ('papers', 'patents', 'companies')):
        with tab:
            _entity_tab(graph, selected[kind], kind)

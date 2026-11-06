"""Patent search with independent filters and links to the original publications."""
from __future__ import annotations

import html
import json
import math
from pathlib import Path

import streamlit as st

from dashboard.i18n import (clear_localized_selection, language,
                            localized_multiselect, preserve_original_text)
from dashboard.patent_data import MEDICAL_APPLICATIONS, filter_patents, load_patents

_COPY = {
    'title': ('医疗增材制造 · 专利检索', 'Medical additive manufacturing · Patents', 'Additive Fertigung in der Medizin · Patente'),
    'intro': ('严格筛选的直接相关专利；按医疗应用、申请人和公开年份探索。', 'Strictly selected, directly relevant patents. Explore by medical application, applicant and publication year.', 'Streng ausgewählte, direkt relevante Patente. Nach medizinischer Anwendung, Anmelder und Veröffentlichungsjahr filtern.'),
    'applications': ('医疗应用', 'Medical application', 'Medizinische Anwendung'),
    'applicants': ('申请人（留空表示全部）', 'Applicants (empty = all)', 'Anmelder (leer = alle)'),
    'years': ('公开年份', 'Publication year', 'Veröffentlichungsjahr'),
    'unknown': ('包含公开年份未知的记录', 'Include records with unknown publication year', 'Einträge ohne bekanntes Veröffentlichungsjahr einschließen'),
    'query': ('公开号／题名／申请人检索', 'Search publication number / title / applicant', 'Publikationsnummer / Titel / Anmelder suchen'),
    'reset': ('重置专利筛选', 'Reset patent filters', 'Patentfilter zurücksetzen'),
    'logic': ('同一条件内满足任一选项，不同条件同时满足。申请人按原始名称精确筛选。', 'OR within each selection; AND between filters. Applicants use exact original names.', 'ODER innerhalb einer Auswahl; UND zwischen Filtern. Anmelder werden nach dem exakten Originalnamen gefiltert.'),
    'records': ('匹配公开记录', 'Matching publications', 'Passende Veröffentlichungen'),
    'families': ('已知同族组', 'Observed patent families', 'Bekannte Patentfamilien'),
    'applicant_count': ('申请人名称', 'Applicant names', 'Anmeldernamen'),
    'countries': ('公开国家／地区', 'Publication authorities', 'Veröffentlichungsbehörden'),
    'scope': ('当前严格快照共 {total:,} 条公开记录；同一发明可能有多个国家或公开阶段的记录。', 'The strict snapshot contains {total:,} publication records. An invention may have records from multiple jurisdictions or publication stages.', 'Der strenge Datenstand enthält {total:,} Veröffentlichungen. Eine Erfindung kann Einträge aus mehreren Ländern oder Veröffentlichungsstufen haben.'),
    'empty': ('没有匹配的专利，请调整筛选或点击“重置专利筛选”。', 'No patents match. Adjust the filters or reset them.', 'Keine passenden Patente. Filter anpassen oder zurücksetzen.'),
    'page': ('结果页', 'Results page', 'Ergebnisseite'),
    'range': ('第 {start:,}–{end:,} 条，共 {total:,} 条 · {pages:,} 页', 'Records {start:,}–{end:,} of {total:,} · {pages:,} pages', 'Einträge {start:,}–{end:,} von {total:,} · {pages:,} Seiten'),
    'number': ('公开号', 'Publication number', 'Publikationsnummer'),
    'patent_title': ('原始题名', 'Original title', 'Originaltitel'),
    'applicant_column': ('原始申请人', 'Original applicants', 'Originalanmelder'),
    'original': ('专利原文', 'Original patent', 'Originalpatent'),
    'open': ('查看专利原文 ↗', 'View original patent ↗', 'Originalpatent ansehen ↗'),
    'details': ('查看本页专利详情', 'View details for a patent on this page', 'Patentdetails auf dieser Seite ansehen'),
    'published': ('公开日期', 'Publication date', 'Veröffentlichungsdatum'),
    'family': ('已知同族编号', 'Observed family ID', 'Bekannte Familien-ID'),
    'missing': ('未提供', 'Not provided', 'Nicht angegeben'),
    'excerpt': ('原始摘要节选', 'Original abstract excerpt', 'Auszug aus der Originalzusammenfassung'),
    'method': ('纳入依据：现有题名、摘要与分类中的直接医疗增材制造证据。医疗应用可多选归类；题名和申请人保留原文。年份指公开年份，不代表首次申请年份。', 'Included using direct medical additive manufacturing evidence in the available titles, abstracts and classifications. Applications may have multiple labels. Titles and applicants retain their original wording. Years refer to publication, not first filing.', 'Aufgenommen aufgrund direkter Belege für medizinische additive Fertigung in vorhandenen Titeln, Zusammenfassungen und Klassifikationen. Mehrere Anwendungslabels sind möglich. Titel und Anmelder bleiben im Original. Jahre beziehen sich auf die Veröffentlichung, nicht die Erstanmeldung.'),
    'link_note': ('原文在 Espacenet 新页面打开。本模块不保存专利全文；具体可用内容以来源网站为准。', 'Original publications open on Espacenet in a new tab. Patent full texts are not stored here; available content depends on the source website.', 'Originalveröffentlichungen öffnen auf Espacenet in einem neuen Tab. Hier werden keine Patentvolltexte gespeichert; verfügbare Inhalte hängen von der Quellwebsite ab.'),
    'load_error': ('专利数据暂时无法读取，请稍后重试。', 'Patent data could not be loaded. Please try again later.', 'Patentdaten konnten nicht geladen werden. Bitte später erneut versuchen.'),
}
_APPLICATION_LABELS = {
    'dental': ('口腔与牙科', 'Dental', 'Zahnmedizin'),
    'implants_and_prostheses': ('植入物与假体', 'Implants and prostheses', 'Implantate und Prothesen'),
    'tissue_engineering_and_bioprinting': ('组织工程与生物打印', 'Tissue engineering and bioprinting', 'Gewebeengineering und Bioprinting'),
    'pharmaceuticals_and_drug_delivery': ('药物与递送', 'Pharmaceuticals and drug delivery', 'Arzneimittel und Wirkstofffreisetzung'),
    'surgical_tools_and_anatomical_models': ('手术工具与解剖模型', 'Surgical tools and anatomical models', 'Chirurgische Instrumente und anatomische Modelle'),
    'medical_devices_and_rehabilitation': ('医疗器械与康复', 'Medical devices and rehabilitation', 'Medizinprodukte und Rehabilitation'),
}


def _localized(values):
    return values[{'zh': 0, 'en': 1, 'de': 2}.get(language(), 0)]


def text(key):
    return _localized(_COPY[key])


def application_label(code):
    return _localized(_APPLICATION_LABELS[code])


@st.cache_data(show_spinner=False)
def _cached_patents(root, signature):
    return load_patents(Path(root))


def reset_patent_filters():
    clear_localized_selection(st.session_state, 'patent_applications')
    for key in ('patent_applicants', 'patent_years', 'patent_unknown_year',
                'patent_query', 'patent_page', 'patent_record', '_patent_filter_signature'):
        st.session_state.pop(key, None)


def patent_filters(root):
    paths = [Path(root)/'data'/name for name in ('patents.jsonl.gz', 'patents_manifest.json')]
    try:
        signature = tuple((p.stat().st_mtime_ns, p.stat().st_size) for p in paths)
        source = _cached_patents(str(root), signature)
    except (OSError, ValueError, KeyError):
        st.error(text('load_error'))
        st.stop()
    applications = localized_multiselect(st, text('applications'), MEDICAL_APPLICATIONS,
                                         default=list(MEDICAL_APPLICATIONS), key='patent_applications',
                                         format_func=application_label)
    names = sorted({name for values in source.applicants for name in values}, key=str.casefold)
    applicant_label = text('applicants')
    with preserve_original_text():
        applicants = st.multiselect(applicant_label, names, default=[], key='patent_applicants')
    known = source.publication_year.dropna()
    years = None
    if not known.empty:
        first, last = int(known.min()), int(known.max())
        years = st.slider(text('years'), first, last, (first, last), key='patent_years') if first < last else (first, last)
    unknown = (st.checkbox(text('unknown'), value=True, key='patent_unknown_year')
               if source.publication_year.isna().any() else False)
    query = st.text_input(text('query'), key='patent_query')
    st.button(text('reset'), key='patent_reset', on_click=reset_patent_filters, width='stretch')
    st.caption(text('logic'))
    current = json.dumps([sorted(applications), sorted(applicants), years, unknown, query], ensure_ascii=False)
    if st.session_state.get('_patent_filter_signature') != current:
        st.session_state.pop('patent_page', None)
        st.session_state.pop('patent_record', None)
        st.session_state['_patent_filter_signature'] = current
    filtered = filter_patents(source, applications=applications, applicants=applicants,
                              years=years, include_unknown_year=unknown, query=query)
    return source, filtered


def patent_explorer(source, filtered):
    st.markdown('<div class="hero"><div class="eyebrow">MEDICAL ADDITIVE MANUFACTURING · PATENTS</div>'
                f'<h1>{html.escape(text("title"))}</h1><p>{html.escape(text("intro"))}</p></div>',
                unsafe_allow_html=True)
    counts = [len(filtered), filtered.family_id.replace('', None).nunique(),
              len({v for names in filtered.applicants for v in names}), filtered.country.nunique()]
    for column, key, value in zip(st.columns(4), ('records', 'families', 'applicant_count', 'countries'), counts):
        column.metric(text(key), f'{value:,}')
    st.caption(text('scope').format(total=len(source)))
    if filtered.empty:
        st.info(text('empty'))
        return
    pages = math.ceil(len(filtered)/25)
    if int(st.session_state.get('patent_page', 1)) > pages:
        st.session_state['patent_page'] = 1
    page = int(st.number_input(text('page'), min_value=1, max_value=pages, value=1, step=1, key='patent_page'))
    start = (page-1)*25
    records = filtered.iloc[start:start+25]
    st.caption(text('range').format(start=start+1, end=start+len(records), total=len(filtered), pages=pages))
    columns = {k: text(v) for k, v in [('publication_id', 'number'), ('title', 'patent_title'),
                ('publication_year', 'years'), ('applicants', 'applicant_column'),
                ('medical_categories', 'applications'), ('source_url', 'original')]}
    table = records[list(columns)].copy()
    table['applicants'] = table.applicants.map(lambda v: '; '.join(v))
    table['medical_categories'] = table.medical_categories.map(lambda values: '; '.join(application_label(v) for v in values))
    config = {key: st.column_config.TextColumn(label) for key, label in columns.items()}
    config['publication_year'] = st.column_config.NumberColumn(columns['publication_year'], format='%d')
    config['source_url'] = st.column_config.LinkColumn(columns['source_url'], display_text=text('open'))
    detail_label = text('details')
    with preserve_original_text():
        st.dataframe(table, hide_index=True, width='stretch', column_config=config)
        ids = records.publication_id.tolist()
        if st.session_state.get('patent_record') not in ids:
            st.session_state.pop('patent_record', None)
        selected = st.selectbox(detail_label, ids, key='patent_record')
    row = records.set_index('publication_id').loc[selected]
    with st.container(border=True):
        with preserve_original_text():
            st.subheader(row.title or selected)
            st.text('; '.join(row.applicants))
        st.caption(f'{selected} · {text("published")}: {row.publication_date or text("missing")} · '
                   f'{text("family")}: {row.family_id or text("missing")}')
        st.caption(' · '.join(application_label(v) for v in row.medical_categories))
        if row.abstract_excerpt:
            st.caption(text('excerpt'))
            with preserve_original_text():
                st.text(row.abstract_excerpt)
        st.link_button(text('open'), row.source_url, type='primary')
    st.caption(text('method'))
    st.caption(text('link_note'))

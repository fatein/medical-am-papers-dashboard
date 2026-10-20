from pathlib import Path
import json
import csv
import pandas as pd
import streamlit as st
from dashboard.data import load_data,filter_papers
from dashboard.labels import P,D,T,M,TIERS,WORK_TYPES,label
from dashboard.views import overview,trends,explorer,updates,header
from dashboard.filter_state import sync_year_range
from dashboard.enterprise_data import load_enterprises,load_enterprise_events,load_enterprise_observations,filter_enterprises
from dashboard.enterprise_views import enterprise_overview,enterprise_timeline,enterprise_explorer
from dashboard.cross_data import load_cross_analysis
from dashboard.cross_views import cross_analysis_page
from dashboard.report_data import load_question_reports
from dashboard.report_navigation import resolve_report_id, clear_report_route
from dashboard.report_views import question_report_page
from dashboard.i18n import (LANGUAGE_OPTIONS, LOCALIZED_SELECTION_KEYS,
                            clear_localized_selection, install_streamlit_translation,
                            localized_multiselect, protect_names, set_language)

ROOT=Path(__file__).resolve().parent
PUBLIC_MODE=globals().get('DASHBOARD_PUBLIC_MODE',False) is True
language_code = st.session_state.get('language', 'zh')
browser_titles = {
    'zh': '医疗增材制造 · 学术趋势',
    'en': 'Medical additive manufacturing · Research trends',
    'de': 'Additive Fertigung in der Medizin · Forschungstrends',
}
st.set_page_config(page_title=browser_titles.get(language_code, browser_titles['zh']),
                   page_icon='◈',layout='wide',initial_sidebar_state='expanded')
set_language(language_code, ROOT)
@st.cache_data(show_spinner=False)
def original_names(project_root: str) -> tuple[str, ...]:
    root = Path(project_root)
    names = set()
    for filename, field in (('enterprises.csv', 'name'), ('papers_pre2026.csv', 'title')):
        path = root/'data'/filename
        if path.exists():
            with path.open(encoding='utf-8-sig', newline='') as handle:
                names.update(row[field] for row in csv.DictReader(handle)
                             if any('\u3400' <= char <= '\u9fff' for char in row.get(field, '')))
    for filename, field in (('additions.jsonl', 'title'), ('enterprise_events.jsonl', 'company')):
        path = root/'data'/filename
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                if line.strip():
                    value = json.loads(line).get(field, '')
                    if isinstance(value, str) and any('\u3400' <= char <= '\u9fff' for char in value):
                        names.add(value)
    cross_path = root/'data'/'cross_analysis.json'
    if cross_path.exists():
        cross_records = json.loads(cross_path.read_text(encoding='utf-8'))
        for collection, field in (('papers', 'title'), ('enterprise_evidence', 'company')):
            names.update(row[field] for row in cross_records.get(collection, [])
                         if any('\u3400' <= char <= '\u9fff' for char in row.get(field, '')))
    return tuple(names)
protect_names(original_names(str(ROOT)))
install_streamlit_translation(st)
language_space, language_column = st.columns([8, 2])
with language_column:
    picker_labels = {'zh': '🌐 语言', 'en': '🌐 Language', 'de': '🌐 Sprache'}
    def refresh_selected_filter_labels():
        selected_language = st.session_state['language']
        for base in LOCALIZED_SELECTION_KEYS:
            st.session_state.pop(f'{base}__{selected_language}', None)
    st.selectbox(picker_labels[language_code], list(LANGUAGE_OPTIONS),
                 format_func=lambda code: LANGUAGE_OPTIONS[code], key='language',
                 label_visibility='visible', on_change=refresh_selected_filter_labels)
if st.session_state['language'] != language_code:
    st.rerun()
st.markdown('''<style>
.stApp{background:#F7F9FC}
[data-testid="stSidebar"]{background:#fff;border-right:1px solid #e2e9ef}
.block-container{padding-top:2rem;max-width:1500px;padding-bottom:3rem}
h1,h2,h3{letter-spacing:-.025em;color:#183049}
[data-testid="stMetric"]{background:#fff;border:1px solid #e2e9ef;border-radius:14px;padding:17px 20px}
[data-testid="stMetricLabel"]{color:#75869b;font-size:13px}
[data-testid="stMetricValue"]{color:#183049;font-size:30px;font-weight:650}
[data-testid="stVerticalBlockBorderWrapper"]{border-radius:14px}
.hero{padding:25px 28px;border:1px solid #dce8e7;border-radius:18px;
background:linear-gradient(115deg,#eaf5f1,#f0f4fb);margin-bottom:22px}
.hero .eyebrow{font-size:11px;font-weight:700;letter-spacing:2px;color:#137f75}
.hero h1{font-size:30px;margin:8px 0 6px;padding:0;font-weight:700}
.hero p{font-size:14px;color:#597184;margin:0;line-height:1.7}
.brand{font-weight:750;font-size:20px;color:#183049;line-height:1.5;margin-bottom:4px}
.tag{display:inline-block;font-size:11px;border-radius:12px;padding:4px 10px;background:#dceee7;color:#137f75}
@media(max-width:1100px){
 [data-testid="stHorizontalBlock"]{flex-wrap:wrap;gap:1rem}
 [data-testid="stColumn"]{flex:1 1 100%!important;min-width:0!important;width:100%!important}
 [data-testid="stColumn"]:has([data-testid="stMetric"]){flex:1 1 calc(50% - 1rem)!important;width:calc(50% - 1rem)!important}
 [data-testid="stMetricValue"]{font-size:25px}
 h3{font-size:22px!important}
}
</style>''',unsafe_allow_html=True)


@st.cache_data(show_spinner=False)
def cached_data(project_root,signature,include_future):
    return load_data(project_root,include_future)


def signature():
    paths=[ROOT/'data/papers_pre2026.csv',ROOT/'data/additions.jsonl']
    return tuple((p.name,p.stat().st_mtime_ns,p.stat().st_size) for p in paths if p.exists())


if not (ROOT/'data/papers_pre2026.csv').exists():
    st.error('历史快照尚未构建。请先运行 scripts/build_dataset.py。')
    st.stop()
manifest=json.loads((ROOT/'data/manifest.json').read_text(encoding='utf-8'))
report_id=resolve_report_id(st.query_params, [])
if report_id is not None:
    st.session_state['page']='学术与企业联系'
with st.sidebar:
    st.markdown('<div class="brand">◈ AM Research<br>学术趋势观察台</div><span class="tag">公开 · 开源 · 免费</span>' if PUBLIC_MODE else
                '<div class="brand">◈ AM Research<br>学术趋势观察台</div><span class="tag">本地 · 开源 · 无订阅</span>',unsafe_allow_html=True)
    st.caption('医疗增材制造 / 论文研究项目')
    st.divider()
    pages=['论文总览','研究结构与趋势','论文检索','学术与企业联系','企业格局','技术路线图','企业检索']
    if not PUBLIC_MODE: pages.append('数据更新')
    page=st.radio('浏览页面',pages,key='page',label_visibility='collapsed',on_change=clear_report_route)
    st.divider()
    if page in ('企业格局','技术路线图','企业检索'):
        try:
            companies=load_enterprises(ROOT)
            events=load_enterprise_events(ROOT)
            observations=load_enterprise_observations(ROOT)
        except (OSError,ValueError) as error:
            st.error(f'企业数据读取失败：{error}')
            st.stop()
        countries=sorted(companies.country.unique())
        chosen_countries=localized_multiselect(st,'国家／地区',countries,default=countries,
                                                key='enterprise_countries')
        p_options=[f'P{i}' for i in range(1,8)]
        chosen_ps=localized_multiselect(st,'医疗对象 P 类别',p_options,default=p_options,
                                        format_func=lambda code:label(code,P),key='enterprise_p_codes')
        enterprise_query=st.text_input('企业／产品／技术检索',key='enterprise_query')
        statuses=sorted(companies.status.unique())
        with st.expander('更多企业筛选'):
            chosen_statuses=localized_multiselect(st,'企业状态',statuses,default=statuses,
                                                   key='enterprise_statuses')
        if st.button('重置企业筛选',width='stretch'):
            for key in ['enterprise_countries','enterprise_p_codes','enterprise_query','enterprise_statuses',
                        'enterprise_years','enterprise_types','enterprise_timeline_company',
                        'enterprise_event_choice','enterprise_timeline_page']:
                (clear_localized_selection(st.session_state,key) if key in LOCALIZED_SELECTION_KEYS
                 else st.session_state.pop(key,None))
            st.rerun()
        st.divider()
        filtered_companies=filter_enterprises(companies,countries=chosen_countries,p_codes=chosen_ps,
                                               query=enterprise_query,statuses=chosen_statuses)
    elif page=='学术与企业联系':
        st.caption('本页可按 P 层、研究方向和研究问题逐级查看。')
    else:
        future=st.checkbox('包含后续补充数据（2026+）',key='include_future',
                           value=(ROOT/'data/additions.jsonl').exists())
        try:
            df=cached_data(str(ROOT),signature(),future)
        except (ValueError,OSError) as error:
            st.error(f'数据读取失败：{error}')
            st.stop()
        first,last=int(df.publication_year.min()),int(df.publication_year.max())
        sync_year_range(st.session_state,(first,last))
        years=st.slider('发表年份',first,last,(first,last),key='years') if first<last else (first,last)
        options=sorted(df.analysis_primary_p_layer.unique())
        ps=localized_multiselect(st,'医疗对象（主 P 类别）',options,default=options,
                                format_func=lambda c:label(c,P),key='p_layers')
        query=st.text_input('检索关键词',placeholder='题名、作者、期刊、DOI…' if PUBLIC_MODE else
                            '题名、作者、DOI、摘要…',key='query')
        with st.expander('更多筛选'):
            values={}
            for key,col,mapping,title in [('tiers','analysis_corpus_tier',TIERS,'语料层级'),
                                         ('diseases','disease_primary_code',D,'疾病／应用'),
                                         ('processes','am_process_primary_code',T,'制造工艺'),
                                         ('materials','material_primary_code',M,'材料'),
                                         ('work_types','normalized_work_type',WORK_TYPES,'论文类型')]:
                opts=sorted(df[col].unique())
                values[key]=localized_multiselect(st,title,opts,default=opts,
                                                   format_func=lambda c,m=mapping:label(c,m),key=key)
        if st.button('重置筛选',width='stretch'):
            for key in ['years','p_layers','query','tiers','diseases','processes','materials','work_types']:
                (clear_localized_selection(st.session_state,key) if key in LOCALIZED_SELECTION_KEYS
                 else st.session_state.pop(key,None))
            st.rerun()
        st.divider()

if page=='学术与企业联系':
    try:
        cross_data=load_cross_analysis(ROOT)
        reports=load_question_reports(ROOT)['reports']
        if report_id is not None:
            question=next((q for q in cross_data['questions'] if q['question_id']==report_id),None)
            question_report_page(reports.get(report_id),question,ROOT)
        else:
            cross_analysis_page(cross_data,set(reports))
    except (OSError,ValueError,KeyError) as error:
        st.error(f'交叉分析数据读取失败：{error}')
elif page=='企业格局':
    enterprise_overview(filtered_companies,events,observations)
elif page=='技术路线图':
    enterprise_timeline(filtered_companies,events,observations,chosen_ps)
elif page=='企业检索':
    enterprise_explorer(filtered_companies,events,observations)
else:
    filtered=filter_papers(df,include_future=future,years=years,p_layers=ps,query=query,
                           **values)
    header(page,years,len(filtered),future,public_mode=PUBLIC_MODE)
    if page=='数据更新':
        updates(ROOT,manifest)
    elif filtered.empty:
        st.info('没有匹配的论文。请调整年份、类别或检索关键词，或点击“重置筛选”。')
    elif page=='论文总览': overview(filtered,years)
    elif page=='研究结构与趋势': trends(filtered,years)
    elif page=='论文检索': explorer(filtered,public_mode=PUBLIC_MODE)

from pathlib import Path
import json
import pandas as pd
import streamlit as st
from dashboard.data import load_data,filter_papers
from dashboard.labels import P,D,T,M,TIERS,WORK_TYPES,label
from dashboard.views import overview,trends,explorer,updates,header
from dashboard.filter_state import sync_options,sync_year_range

ROOT=Path(__file__).resolve().parent
PUBLIC_MODE=globals().get('DASHBOARD_PUBLIC_MODE',False) is True
st.set_page_config(page_title='医疗增材制造 · 学术趋势',page_icon='◈',layout='wide',initial_sidebar_state='expanded')
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
with st.sidebar:
    st.markdown('<div class="brand">◈ AM Research<br>学术趋势观察台</div><span class="tag">公开 · 开源 · 免费</span>' if PUBLIC_MODE else
                '<div class="brand">◈ AM Research<br>学术趋势观察台</div><span class="tag">本地 · 开源 · 无订阅</span>',unsafe_allow_html=True)
    st.caption('医疗增材制造 / 论文研究项目')
    st.divider()
    pages=['论文总览','研究结构与趋势','论文检索']
    if not PUBLIC_MODE: pages.append('数据更新')
    page=st.radio('浏览页面',pages,key='page',label_visibility='collapsed')
    st.divider()
    future=st.checkbox('包含后续补充数据（2026+）',key='include_future',
                       value=(ROOT/'data/additions.jsonl').exists())
    bibliometric_only=st.checkbox('2026 仅显示建议纳入文献计量',key='bibliometric_only',value=False) if future else False
    try:
        df=cached_data(str(ROOT),signature(),future)
    except (ValueError,OSError) as error:
        st.error(f'数据读取失败：{error}')
        st.stop()
    first,last=int(df.publication_year.min()),int(df.publication_year.max())
    sync_year_range(st.session_state,(first,last))
    years=st.slider('发表年份',first,last,(first,last),key='years') if first<last else (first,last)
    options=sorted(df.analysis_primary_p_layer.unique())
    sync_options(st.session_state,'p_layers',options)
    ps=st.multiselect('医疗对象（主 P 类别）',options,default=options,format_func=lambda c:label(c,P),key='p_layers')
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
            sync_options(st.session_state,key,opts)
            values[key]=st.multiselect(title,opts,default=opts,format_func=lambda c,m=mapping:label(c,m),key=key)
    if st.button('重置筛选',width='stretch'):
        for key in ['years','p_layers','query','tiers','diseases','processes','materials','work_types']:
            st.session_state.pop(key,None)
        st.rerun()
    st.divider()

filtered=filter_papers(df,include_future=future,years=years,p_layers=ps,query=query,
                       bibliometric_only=bibliometric_only,**values)
header(page,years,len(filtered),future,public_mode=PUBLIC_MODE)
if page=='数据更新':
    updates(ROOT,manifest)
elif filtered.empty:
    st.info('没有匹配的论文。请调整年份、类别或检索关键词，或点击“重置筛选”。')
elif page=='论文总览': overview(filtered,years)
elif page=='研究结构与趋势': trends(filtered,years)
elif page=='论文检索': explorer(filtered,public_mode=PUBLIC_MODE)

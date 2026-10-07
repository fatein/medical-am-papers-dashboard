"""Chinese dashboard pages; all charts share the current document filter."""
from __future__ import annotations
import html
import io
import json
import math
from urllib.parse import quote
import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from .analytics import yearly_counts,period_comparison,cross_counts
from .charts import annual_chart,distribution_chart,composition_chart,comparison_chart,heatmap_chart,style
from .data import read_upload,validate_additions,save_additions,safe_csv,load_data,deduplicate
from .public_data import public_download_frame
from .labels import P,D,T,M,THEMES,DIMENSIONS,TIERS,WORK_TYPES,label

CONFIG={'displaylogo':False,'scrollZoom':False,
        'toImageButtonOptions':{'format':'png','scale':2,'filename':'am_research_chart'}}
EVIDENCE_SCOPES={'pdf_excerpt':'原文片段','abstract':'摘要／元数据','title_only':'仅题名／元数据'}


def evidence_field(record, key):
    value = record.get(key, '')
    return '' if value is None or pd.isna(value) else str(value).strip()


def chart(fig,key):
    st.plotly_chart(fig,width='stretch',theme=None,key=key,config=CONFIG)


def header(page,years,count,future,public_mode=False):
    subtitles={'论文总览':'从研究产出到研究结构，观察医疗增材制造的学术演变。',
               '研究结构与趋势':'把研究规模与类别占比分开，比较技术路线的结构变化。',
               '论文检索':'让每一个趋势，都能回到具体论文与标注证据。',
               '数据更新':'保留历史基线，逐批补充新论文，并追踪数据来源。'}
    st.markdown(f'<div class="hero"><div class="eyebrow">MEDICAL ADDITIVE MANUFACTURING · RESEARCH OBSERVATORY</div>'
                f'<h1>{page}</h1><p>{subtitles[page]}</p>'
                f'<p style="margin-top:10px;font-size:12px">{years[0]}–{years[1]} · 当前筛选 {count:,} 篇 · '
                f'{"历史 + 补充数据" if future else "2026 年之前的历史基线"}</p></div>',unsafe_allow_html=True)


def overview(df,years):
    annual=yearly_counts(df,years)
    end=annual.iloc[-1]
    growth=None if pd.isna(end.yoy_pct) else f'{end.yoy_pct:+.1f}% 较上一年'
    columns=st.columns(4)
    columns[0].metric('筛选后的论文',f'{len(df):,}',help='单篇论文计数；同题名同年或相同 DOI/ID 的版本不重复计入。')
    columns[1].metric('选择的时间范围',f'{years[0]}–{years[1]}')
    columns[2].metric(f'{years[1]} 年论文',f'{int(end.n):,}',delta=growth,
                      help='同比只比较相邻日历年。筛选首年、前一年为零及持续补充的 2026+ 年份不显示同比。')
    columns[3].metric('生物打印相关',f'{int(df.bioprinting_flag.sum()):,}',
                      help='沿用既有标注的 bioprinting_flag，不等同于独立工艺分类。')
    left,right=st.columns([1.7,1])
    with left,st.container(border=True):
        st.subheader('研究产出的时间轨迹')
        st.caption('绿色柱：年度数量 · 蓝色线：所选范围内累计；来源为当前项目语料。')
        chart(annual_chart(df,years),'annual')
    with right,st.container(border=True):
        st.subheader('主要医疗对象')
        st.caption('每篇归入一个主医疗对象类别，合计等于当前论文数。')
        chart(distribution_chart(df,'analysis_primary_p_layer',P),'p_distribution')
    with st.container(border=True):
        st.subheader('研究对象的年度结构')
        st.caption('各年份分别计算占比。')
        chart(composition_chart(df,'analysis_primary_p_layer',P,years,True),'p_yearly')
    st.download_button('下载当前年度统计 CSV',safe_csv(annual),file_name='年度论文统计.csv',mime='text/csv')


def trends(df,years):
    dimension=st.selectbox('分析维度',list(DIMENSIONS),key='dimension')
    column,mapping=DIMENSIONS[dimension]
    left,right=st.columns([1,1])
    with left: measure=st.radio('展示方式',['年度占比','年度数量'],horizontal=True,key='measure')
    with right:
        exclude=st.checkbox('排除未明确／未分配标签',value=False,key='exclude_unknown')
    working=df
    if exclude: working=df.loc[~df[column].isin(['T0','M0','unassigned','U','NA'])]
    st.caption(f'本维度分母：{len(working):,} 篇；当前筛选共 {len(df):,} 篇。使用单一主标签。')
    if working.empty:
        st.info('所选维度没有明确标签，请保留未明确标签或调整筛选。')
        return
    if column=='lexical_theme_id':
        st.info('词汇主题沿用既有分析的八组主题及其解释性名称。')
    with st.container(border=True):
        st.subheader(f'{dimension} · 时间演变')
        chart(composition_chart(working,column,mapping,years,measure=='年度占比'),'dimension_time')
    if years[0]<years[1]:
        with st.container(border=True):
            st.subheader('早期与近期：结构变化')
            boundary=max(years[0],min(2019,years[1]-1))
            c1,c2=st.columns(2)
            with c1: early=st.slider('较早区间',years[0],years[1],(years[0],boundary),key='early')
            with c2: late=st.slider('较晚区间',years[0],years[1],(boundary+1,years[1]),key='late')
            if early[1]>=late[0]:
                st.warning('请使用不重叠的区间，并让较早区间位于较晚区间之前。')
            else:
                comparison=period_comparison(working,column,early,late)
                a=int(working.publication_year.between(*early).sum())
                b=int(working.publication_year.between(*late).sum())
                st.caption(f'较早区间 {early[0]}–{early[1]}：{a:,} 篇 · 较晚区间 {late[0]}–{late[1]}：{b:,} 篇。横轴为占比差的百分点，不是增长率。')
                if a and b:
                    chart(comparison_chart(comparison,mapping),'period_compare')
                    table=comparison.copy()
                    table['code']=table.code.map(lambda c:label(c,mapping))
                    st.download_button('下载区间比较 CSV',safe_csv(table),file_name='区间结构比较.csv',mime='text/csv')
                else: st.info('至少一个比较区间没有论文，请调整区间。')
    with st.container(border=True):
        st.subheader('研究维度的交叉分布')
        relation=st.selectbox('交叉组合',['工艺 × 材料','医疗对象 × 疾病／应用'],key='relation')
        specified=st.checkbox('交叉图仅包含工艺和材料均明确的论文',value=False,key='cross_specified',disabled=relation!='工艺 × 材料')
        cross_df=df
        if relation=='工艺 × 材料':
            r,c,rmap,cmap='am_process_primary_code','material_primary_code',T,M
            if specified: cross_df=df.loc[df[r].ne('T0')&df[c].ne('M0')]
        else: r,c,rmap,cmap='analysis_primary_p_layer','disease_primary_code',P,D
        table=cross_counts(cross_df,r,c)
        st.caption(f'交叉图样本量：{len(cross_df):,} 篇；数值为论文数。仅表示语料分布，不表示临床效果或因果关系。')
        if table.empty: st.info('当前筛选下没有可用于交叉分析的论文。')
        else:
            chart(heatmap_chart(table,rmap,cmap),'cross')
            st.download_button('下载交叉统计 CSV',safe_csv(table.reset_index()),file_name='交叉统计.csv',mime='text/csv')


def display_table(df):
    result=pd.DataFrame({'发表年份':df.publication_year,'论文题名':df.title,'期刊':df.source_journal,
                         '医疗对象':df.analysis_primary_p_layer.map(lambda c:label(c,P)),
                         '疾病／应用':df.disease_primary_code.map(lambda c:label(c,D)),
                         '工艺':df.am_process_primary_code.map(lambda c:label(c,T)),
                         '材料':df.material_primary_code.map(lambda c:label(c,M)),
                         'DOI':df.doi})
    if df.publication_year.ge(2026).any():
        result['内容依据']=[EVIDENCE_SCOPES.get(scope,'未记录') if year>=2026 else '—'
                            for year,scope in zip(df.publication_year,df.evidence_scope)]
        result['文献计量建议']=[('是' if recommended else '否') if year>=2026 else '—'
                              for year,recommended in zip(df.publication_year,df.bibliometric_recommended)]
    return result


def explorer(df,public_mode=False):
    ordered=df.sort_values(['publication_year','title'],ascending=[False,True])
    left,right=st.columns([1,1])
    with left: size=st.selectbox('每页显示',[25,50,100],index=1,key='page_size')
    pages=max(1,math.ceil(len(ordered)/size))
    with right: page=st.number_input('页码',min_value=1,max_value=pages,value=1,step=1,key='paper_page')
    visible=ordered.iloc[(page-1)*size:page*size]
    st.caption(f'共 {len(df):,} 篇 · 第 {page}/{pages} 页；下载包含全部筛选结果。')
    st.dataframe(display_table(visible),hide_index=True,width='stretch',height=410)
    export=public_download_frame(df) if public_mode else df.drop(
        columns=['canonical_pdf','manual_review_required','disease_manual_review_required',
                 'process_manual_review_required','material_manual_review_required',
                 'p_layer_manual_review_required'],errors='ignore')
    st.download_button('下载全部筛选论文 CSV',safe_csv(export),file_name='筛选论文.csv',mime='text/csv',type='primary')
    by_id=visible.set_index('document_id')
    selected=st.selectbox('查看论文详情',visible.document_id.tolist(),
                          format_func=lambda key:f'{by_id.loc[key,"publication_year"]} · {by_id.loc[key,"title"]}',key='selected_paper')
    record=by_id.loc[selected]
    with st.container(border=True):
        st.subheader(record.title)
        st.caption(f'{record.publication_year} · {record.source_journal or "期刊未记录"} · {selected}')
        st.write('作者：',record.authors or '未记录')
        st.write('语料层级：',TIERS.get(record.analysis_corpus_tier,record.analysis_corpus_tier))
        st.write('主类别：',label(record.analysis_primary_p_layer,P),'｜',label(record.disease_primary_code,D))
        st.write('工艺与材料：',label(record.am_process_primary_code,T),'｜',label(record.material_primary_code,M))
        if record.publication_year>=2026:
            st.write('医疗增材制造相关性：',record.get('medical_am_relevance','未记录'))
            st.write('文献计量建议：','纳入' if record.bibliometric_recommended else '暂不纳入')
            st.write('内容核验依据：',EVIDENCE_SCOPES.get(record.get('evidence_scope',''),'未记录'))
            unknown=[name for name,code in [('疾病／应用',record.disease_primary_code),
                                            ('制造工艺',record.am_process_primary_code),
                                            ('材料',record.material_primary_code)] if code=='U']
            if unknown: st.caption('证据未确认：'+'、'.join(unknown))
            if not public_mode and record.get('source_review_limitation',''):
                st.caption('原审核限制：'+record.source_review_limitation)
        if record.doi: st.link_button('打开 DOI 原文入口','https://doi.org/'+quote(record.doi,safe='/()'))
        if not public_mode:
            st.write('摘要')
            st.text(record.abstract or '当前记录没有摘要。')
        with st.expander('标注证据与来源'):
            relevance_basis = evidence_field(record, 'relevance_basis')
            if relevance_basis:
                st.write('**医疗增材制造相关性判断依据**')
                st.text(relevance_basis)
            for title,prefix in [('医疗对象','p_layer'),('语料层级','tier'),('疾病／应用','disease'),
                                 ('制造工艺','process'),('材料','material'),('生物打印','bioprinting')]:
                st.write(f'**{title}**')
                evidence = evidence_field(record, prefix+'_evidence_text')
                if prefix == 'p_layer' and not evidence:
                    evidence = evidence_field(record, 'cross_layer_evidence_text')
                status = evidence_field(record, prefix+'_review_status')
                if status:
                    st.write('自动核验记录：', status)
                st.text(evidence or '未记录证据。')
                section = evidence_field(record, prefix+'_evidence_section')
                pages = evidence_field(record, prefix+'_evidence_pages')
                if prefix == 'p_layer' and not section:
                    section = evidence_field(record, 'cross_layer_evidence_section')
                    pages = evidence_field(record, 'cross_layer_evidence_pages')
                if section or pages:
                    st.caption(f'章节／范围：{section or "未记录"} · 页码：{pages or "未记录"}')


def template_bytes():
    cols=['document_id','doi','title','publication_year','authors','source_journal','abstract',
          'analysis_primary_p_layer','disease_primary_code','am_process_primary_code',
          'material_primary_code','bioprinting_flag','analysis_corpus_tier']
    cols.append('bibliometric_recommended')
    frame=pd.DataFrame(columns=cols)
    excel=io.BytesIO()
    with pd.ExcelWriter(excel,engine='openpyxl') as writer:
        frame.to_excel(writer,index=False,sheet_name='papers')
    return safe_csv(frame),excel.getvalue()


def updates(root,manifest):
    c1,c2,c3,c4=st.columns(4)
    c1.metric('历史论文',f'{manifest["historical_rows"]:,}')
    all_data=load_data(root,True)
    additional=int(all_data.publication_year.ge(2026).sum())
    c2.metric('后续已导入',f'{additional:,}')
    c3.metric('建议纳入文献计量',f'{int(all_data.loc[all_data.publication_year.ge(2026),'bibliometric_recommended'].sum()):,}')
    c4.metric('历史截止年份','2025')
    with st.container(border=True):
        st.subheader('后续论文导入')
        st.write('先填写模板，上传后检查预览，再点击导入。历史文件保持独立；重复记录跳过。')
        csv,excel=template_bytes()
        a,b=st.columns(2)
        a.download_button('下载 CSV 空模板',csv,'论文补充模板.csv','text/csv')
        b.download_button('下载 Excel 空模板',excel,'论文补充模板.xlsx','application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        st.caption('必填：title（标题）、publication_year（2026 至当前年份）、analysis_primary_p_layer（P1–P7 或 U/NA/MULTI）。DOI、ID、摘要及其他标签可选。无标签的字段保持未明确／未分配，不调用 AI 自动分类。')
        st.caption('所有字段名见模板；布尔值用 true/false。上传的 Excel 读取第一个工作表。')
        upload=st.file_uploader('选择补充论文文件',type=['csv','xlsx'],key='upload')
        if upload:
            try:
                raw=read_upload(upload.getvalue(),upload.name)
                valid,errors=validate_additions(raw)
            except (ValueError,OSError,KeyError,UnicodeError) as error:
                st.error(f'文件读取失败：{error}')
                return
            if errors:
                st.error(f'发现 {len(errors)} 个校验问题，本次不会导入任何记录。')
                for error in errors[:30]: st.write(error)
                if len(errors)>30: st.caption('请先修正以上问题，再重新上传。')
            else:
                merged,rejected=deduplicate(pd.concat([all_data,valid],ignore_index=True))
                new=len(merged)-len(all_data)
                st.success(f'校验通过：{len(valid):,} 条输入 · 可新增 {new:,} 篇 · 重复 {len(rejected):,} 条。')
                st.dataframe(display_table(valid.head(100)),hide_index=True,width='stretch')
                if st.button('确认导入补充论文',type='primary',disabled=new==0,key='import_confirm'):
                    try:
                        count,duplicate=save_additions(root,valid)
                        st.cache_data.clear()
                        st.success(f'已保存 {count} 篇新增论文；跳过 {duplicate} 条重复记录。开启侧栏“包含后续补充数据”即可查看。')
                    except (ValueError,OSError) as error: st.error(f'导入失败：{error}')
    with st.expander('分类代码对照表'):
        for name,(_,mapping) in DIMENSIONS.items():
            st.write(f'**{name}**')
            st.dataframe(pd.DataFrame({'代码':list(mapping),'含义':list(mapping.values())}),hide_index=True,width='stretch')
    with st.container(border=True):
        st.subheader('历史来源与统计边界')
        st.write(f'原始输入 {manifest["source_rows"]:,} 条；排除 2026+ {manifest["excluded_2026_plus"]} 条，版本重复 {manifest["duplicate_rows"]} 条；形成 {manifest["historical_rows"]:,} 篇历史快照。')
        st.caption('构建时间：'+manifest['built_at'])
        audit_path=root/'data/2026_import_audit.json'
        if audit_path.exists():
            audit=json.loads(audit_path.read_text(encoding='utf-8'))
            st.write(f'2026 补充来源：{audit["source_file"]}，主表 {audit["source_rows"]:,} 条；建议纳入文献计量 {audit["recommended_for_bibliometrics"]:,} 条。')
            st.caption('原工作簿包含重复附加记录和首次发表年不在 2026 的记录，均未作为新论文导入。')
        for note in manifest['notes']: st.write('• '+note)
        st.write('类别和标注证据沿用论文分析归档，未用模型预测覆盖既有标签。')
        with st.expander('查看来源文件和校验哈希'):
            st.json(manifest)
        excluded=pd.read_csv(root/'data/excluded_duplicates.csv',keep_default_na=False)
        if len(excluded):
            st.write('排除的版本重复记录')
            st.dataframe(excluded,hide_index=True,width='stretch')
    st.info('如需让其他电脑持续访问，需使用自己的服务器或适合的免费托管环境；当前交付在本机运行，不产生软件订阅费用。')

"""Public enterprise pages backed by the reviewed company and event catalogues."""
from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.enterprise_data import parse_p_codes
from dashboard.labels import P, label


TEAL = '#137F75'
BLUE = '#5276BB'
EVENT_COLORS = {
    '产品发布': '#137F75', '技术升级': '#69A89A', '监管许可': '#5276BB',
    '临床应用': '#9A78BD', '合作': '#D5A454', '并购': '#CB756F',
    '融资与投资': '#DB9B5A', '企业布局': '#8393A9',
}


def _hero(title: str, subtitle: str) -> None:
    st.markdown(
        '<div class="hero"><div class="eyebrow">MEDICAL ADDITIVE MANUFACTURING · INDUSTRY OBSERVATORY</div>'
        f'<h1>{html.escape(title)}</h1><p>{html.escape(subtitle)}</p></div>',
        unsafe_allow_html=True,
    )


def _events_for(companies: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    return events.loc[events.company_id.isin(companies.company_id)].copy()


def _source_button(url: str, key: str, evidence_level: str = '') -> None:
    if url:
        caption = '查看参考来源 ↗' if evidence_level == '工作簿整理·年份级' else '查看来源 ↗'
        st.link_button(caption, url, key=key)


def enterprise_overview(companies: pd.DataFrame, events: pd.DataFrame) -> None:
    _hero('企业格局', '从企业地域、医疗对象和有来源的逐年事件，观察这份企业库中的技术与产品变化。')
    selected_events = _events_for(companies, events)
    a, b, c, d = st.columns(4)
    a.metric('企业', f'{len(companies):,}')
    b.metric('涉及国家／地区', f'{companies.country.nunique():,}')
    c.metric('年度节点（含年份级）', f'{len(selected_events):,}')
    d.metric('有年度节点的企业', f'{selected_events.company_id.nunique():,}')

    left, right = st.columns([1.05, 1])
    with left:
        st.subheader('主要国家／地区')
        country = companies.country.value_counts().head(12).sort_values()
        fig = px.bar(x=country.values, y=country.index, orientation='h',
                     labels={'x': '企业数', 'y': ''}, text=country.values)
        fig.update_traces(marker_color=TEAL, textposition='outside')
        fig.update_layout(height=460, margin=dict(l=10, r=55, t=10, b=30),
                          showlegend=False, plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, width='stretch')
    with right:
        st.subheader('医疗对象 P 分类')
        counts = pd.Series([code for value in companies.p_codes for code in parse_p_codes(value)]).value_counts()
        counts = counts.reindex([f'P{i}' for i in range(1, 8)], fill_value=0)
        labels = [label(code, P) for code in counts.index]
        fig = px.bar(x=counts.values, y=labels, orientation='h',
                     labels={'x': '企业数', 'y': ''}, text=counts.values)
        fig.update_traces(marker_color=BLUE, textposition='outside')
        fig.update_layout(height=460, margin=dict(l=10, r=55, t=10, b=30),
                          yaxis=dict(autorange='reversed'), showlegend=False,
                          plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, width='stretch')
    st.caption('一家公司可对应多个 P 类，因此各类数量之和可能大于当前企业数。')

    st.subheader('企业年度变化')
    if selected_events.empty:
        st.info('当前筛选范围没有可确认年份及来源的事件。')
    else:
        annual = selected_events.groupby(['event_year', 'event_type']).size().reset_index(name='事件数')
        annual['event_year'] = annual.event_year.astype(str)
        fig = px.bar(annual, x='event_year', y='事件数', color='event_type',
                     color_discrete_map=EVENT_COLORS, labels={'event_year': '年份', 'event_type': '事件类型'})
        fig.update_layout(barmode='stack', height=400,
                          margin=dict(l=10, r=10, t=15, b=30),
                          legend=dict(orientation='h', y=-0.22), plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, width='stretch')
        st.caption('年度柱表示企业库中记录的产品、技术及市场动作数量，不能据此推算销售额或市场份额。')
    with st.expander('数据与证据口径'):
        st.write('来源工作簿有 347 条记录；合并 3 组同一主体的重复记录后，当前展示 344 家。')
        st.write('时间轴含两种节点：逐条复查来源的节点，以及根据工作簿产品变化摘要整理的年份级节点。年份级节点只表示资料记载的年份；所附链接是参考来源，未必包含同一句发布日期。没有可定位年份的产品仍可在企业档案中检索。')


def enterprise_timeline(companies: pd.DataFrame, events: pd.DataFrame,
                        selected_p_codes: list[str] | None = None) -> None:
    _hero('技术路线图', '按国家、医疗对象和年份查看企业产品、技术与市场动作；每条节点都标明时间和来源口径。')
    selected = _events_for(companies, events)
    if selected_p_codes is not None and len(selected_p_codes) < 7:
        selected = selected.loc[selected.p_codes.map(
            lambda value: bool(set(parse_p_codes(value)).intersection(selected_p_codes)))].copy()
    if selected.empty:
        st.info('当前筛选范围没有可入图的年度事件。可前往企业检索查看公司档案。')
        return
    years = sorted(selected.event_year.unique().tolist())
    types = sorted(selected.event_type.unique().tolist())
    c1, c2 = st.columns(2)
    with c1:
        year_range = st.slider('事件年份', min(years), max(years), (min(years), max(years)), key='enterprise_years') if len(years) > 1 else (years[0], years[0])
    with c2:
        chosen_types = st.multiselect('事件类型', types, default=types, key='enterprise_types')
    selected = selected.loc[selected.event_year.between(*year_range) & selected.event_type.isin(chosen_types)].copy()
    if selected.empty:
        st.info('没有符合这些条件的年度事件。')
        return
    names = companies.set_index('company_id').name.to_dict()
    selected['company_name'] = selected.company_id.map(names)
    metric1, metric2, metric3 = st.columns(3)
    metric1.metric('年度节点', f'{len(selected):,}')
    metric2.metric('有节点的企业', f'{selected.company_id.nunique():,}')
    metric3.metric('覆盖年份', f'{selected.event_year.min()}–{selected.event_year.max()}')

    tab_matrix, tab_annual = st.tabs(['企业 × 年份', '年度汇总'])
    with tab_matrix:
        company_names = sorted(selected.company_name.unique().tolist())
        chosen_name = st.selectbox('定位企业', ['全部'] + company_names, key='enterprise_timeline_company')
        if chosen_name != '全部':
            shown = selected.loc[selected.company_name.eq(chosen_name)]
        else:
            page_count = (len(company_names) + 24) // 25
            page = st.number_input('企业页码（每页最多 25 家）', min_value=1, max_value=page_count,
                                   value=1, step=1, key='enterprise_timeline_page')
            shown = selected.loc[selected.company_name.isin(company_names[(page-1)*25:page*25])]
        fig = px.scatter(shown, x='event_year', y='company_name', color='event_type',
                         hover_name='title', hover_data={'event_year': True, 'event_type': True,
                                                          'company_name': False},
                         color_discrete_map=EVENT_COLORS,
                         labels={'event_year': '年份', 'company_name': '企业', 'event_type': '事件类型'})
        fig.update_traces(marker=dict(size=12, line=dict(width=1, color='white')))
        fig.update_layout(height=max(430, 48 * shown.company_name.nunique() + 100),
                          margin=dict(l=15, r=20, t=20, b=20),
                          legend=dict(orientation='h', y=-0.16), plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, width='stretch')
    with tab_annual:
        yearly = selected.groupby(['event_year', 'event_type']).size().reset_index(name='事件数')
        yearly['event_year'] = yearly.event_year.astype(str)
        fig = px.bar(yearly, x='event_year', y='事件数', color='event_type',
                     color_discrete_map=EVENT_COLORS, barmode='stack',
                     labels={'event_year': '年份', 'event_type': '事件类型'})
        fig.update_layout(height=420, margin=dict(l=10, r=10, t=15, b=30),
                          legend=dict(orientation='h', y=-0.22), plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, width='stretch')
        counts = selected.groupby('event_year').company_id.nunique().rename('有事件的企业数')
        st.dataframe(counts, width='stretch')

    st.subheader('事件与来源')
    choices = selected.sort_values(['event_year', 'company_name'], ascending=[False, True]).reset_index(drop=True)
    index = st.selectbox('选择一条事件', choices.index.tolist(),
                         format_func=lambda i: f"{choices.loc[i, 'event_year']} · {choices.loc[i, 'company_name']} · {choices.loc[i, 'title']}",
                         key='enterprise_event_choice')
    event = choices.loc[index]
    st.markdown(f"**{event['title']}**")
    st.write(event['detail'])
    precision = '年份级' if event['date_precision'] == 'year' else '具体日期'
    st.caption(f"时间：{event['event_date']}（{precision}） · 医疗对象：{event['p_codes'] or '未明确'} · 类型：{event['event_type']} · 依据：{event['evidence_level']}")
    if event['technology']:
        st.write(f"技术／工艺：{event['technology']}")
    if event['material']:
        st.write(f"材料：{event['material']}")
    _source_button(event['source_url'], f"timeline_source_{event['event_id']}", event['evidence_level'])


def enterprise_explorer(companies: pd.DataFrame, events: pd.DataFrame) -> None:
    _hero('企业检索与档案', '检索企业、产品与技术平台，查看官网、业务方向和资料记载的逐年变化。')
    if companies.empty:
        st.info('没有匹配的企业，请调整筛选条件。')
        return
    st.caption(f'找到 {len(companies):,} 家企业')
    table = companies.loc[:, ['name', 'country', 'p_codes', 'status', 'event_count']].copy()
    table.columns = ['企业', '国家／地区', 'P 分类', '企业状态', '年度事件']
    st.dataframe(table, hide_index=True, width='stretch', height=350)
    names = companies.sort_values('name').name.tolist()
    selected_name = st.selectbox('选择企业查看档案', names, key='enterprise_selected_company')
    company = companies.loc[companies.name.eq(selected_name)].iloc[0]
    st.subheader(company['name'])
    st.caption(f"{company['country']} · {company['status']} · {company['p_codes'] or 'P 类待确认'}")
    if company['website']:
        st.markdown(f"官方网站：[访问 {company['website']}]({company['website']})")
    else:
        st.caption('官方网站：暂无可确认公开链接')
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('**产品与服务（来源工作簿摘要）**')
        st.write(company['product_summary'] or '暂无可核实的产品描述。')
    with c2:
        st.markdown('**技术路线（来源工作簿摘要）**')
        st.write(company['technology_summary'] or '暂无可核实的技术描述。')
    st.markdown('**逐年事件**')
    company_events = events.loc[events.company_id.eq(company['company_id'])].sort_values(
        ['event_year', 'event_date'], ascending=False)
    if company_events.empty:
        st.info('目前未找到足以确认具体年份和产品／技术变化的公开资料。')
    else:
        for event in company_events.itertuples():
            with st.expander(f'{event.event_year} · {event.event_type} · {event.title}'):
                st.write(event.detail)
                if event.technology:
                    st.write(f'技术／工艺：{event.technology}')
                if event.material:
                    st.write(f'材料：{event.material}')
                precision = '年份级' if event.date_precision == 'year' else '具体日期'
                st.caption(f'时间：{event.event_date}（{precision}） · 医疗对象：{event.p_codes or "未明确"} · 依据：{event.evidence_level}')
                _source_button(event.source_url, f'profile_source_{event.event_id}', event.evidence_level)

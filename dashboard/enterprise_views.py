"""Public enterprise pages backed by the reviewed company and event catalogues."""
from __future__ import annotations

import html

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dashboard.enterprise_data import parse_p_codes
from dashboard.labels import P, label
from dashboard.i18n import localized_multiselect, tr


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


def _selection_items(selection: object, kind: str) -> list:
    if not isinstance(selection, dict):
        return []
    return selection.get('selection', {}).get(kind, [])


def _timeline_target(selection: object, company_names: set[str]) -> tuple[str, str, str] | None:
    """Resolve the clicked marker to a company and its catalogue record."""
    for point in _selection_items(selection, 'points'):
        company = point.get('y')
        data = point.get('customdata') or []
        if company in company_names:
            kind = str(data[0]) if len(data) > 0 else ''
            record_id = str(data[1]) if len(data) > 1 else ''
            return company, kind, record_id
    return None


def _table_target(selection: object, names: list[str]) -> str | None:
    for index in _selection_items(selection, 'rows'):
        if isinstance(index, int) and 0 <= index < len(names):
            return names[index]
    return None


def _open_company(company: str, kind: str = '', record_id: str = '') -> None:
    st.session_state['enterprise_selected_company'] = company
    st.session_state['enterprise_focus_record'] = (kind, record_id)
    st.session_state['page'] = '企业检索'


def _on_timeline_select(company_names: set[str]) -> None:
    target = _timeline_target(st.session_state.get('enterprise_timeline_points'), company_names)
    if target:
        _open_company(*target)


def _on_brief_select(names: list[str]) -> None:
    company = _table_target(st.session_state.get('enterprise_timeline_brief'), names)
    if company:
        _open_company(company)


def _source_button(url: str, key: str, evidence_level: str = '') -> None:
    if url:
        caption = '查看参考来源 ↗' if evidence_level == '工作簿整理·年份级' else '查看来源 ↗'
        st.link_button(caption, url, key=key)


def enterprise_overview(companies: pd.DataFrame, events: pd.DataFrame,
                        observations: pd.DataFrame | None = None) -> None:
    _hero('企业格局', '观察企业分布、产品与技术方向，以及有来源的逐年变化。')
    if companies.empty:
        st.info('没有匹配的企业，请调整筛选条件。')
        return
    selected_events = _events_for(companies, events)
    current = (observations.loc[observations.company_id.isin(companies.company_id) &
                                observations.observation_kind.eq('当前现状')]
               if observations is not None else pd.DataFrame())
    a, b, c, d = st.columns(4)
    a.metric('企业', f'{len(companies):,}')
    b.metric('涉及国家／地区', f'{companies.country.nunique():,}')
    c.metric('年度节点（含年份级）', f'{len(selected_events):,}')
    d.metric('有产品／技术描述', f'{current.content_status.ne("资料不足").sum():,}'
             if not current.empty else f'{selected_events.company_id.nunique():,}')

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
    with st.expander('数据与证据口径'):
        st.write('来源工作簿有 347 条记录，合并 3 组重复主体后为 344 家；本轮另加入 8 家交叉分析中核查的企业。')
        st.write('技术地图展示当前产品与技术、年度事件及工作簿资料年份线索。年度变化统计采用年度事件。')


def enterprise_timeline(companies: pd.DataFrame, events: pd.DataFrame,
                        observations: pd.DataFrame,
                        selected_p_codes: list[str] | None = None) -> None:
    _hero('技术路线图', '逐家查看医疗增材制造产品与技术现状，以及有年份的公开变化。')
    if companies.empty:
        st.info('没有匹配的企业，请调整筛选条件。')
        return
    selected_events = _events_for(companies, events)
    selected_observations = observations.loc[observations.company_id.isin(companies.company_id)].copy()
    years = sorted(set(selected_events.event_year.tolist()) |
                   set(selected_observations.loc[selected_observations.observation_year.gt(0),
                                                 'observation_year'].astype(int).tolist()))
    types = sorted(selected_events.event_type.unique().tolist())
    c1, c2 = st.columns(2)
    with c1:
        year_range = (st.slider('年份范围', min(years), max(years), (min(years), max(years)),
                                key='enterprise_years') if len(years) > 1 else
                      (years[0], years[0]) if years else (2010, 2026))
    with c2:
        chosen_types = localized_multiselect(st, '事件类型', types, default=types,
                                             key='enterprise_types')
    selected_events = selected_events.loc[
        selected_events.event_year.between(*year_range) &
        selected_events.event_type.isin(chosen_types)].copy()
    clues = selected_observations.loc[
        selected_observations.observation_kind.eq('资料年份线索') &
        selected_observations.observation_year.between(*year_range)].copy()
    current = selected_observations.loc[
        selected_observations.observation_kind.eq('当前现状')].copy()
    names = companies.set_index('company_id').name.to_dict()
    selected_events['company_name'] = selected_events.company_id.map(names)
    clues['company_name'] = clues.company_id.map(names)
    current['company_name'] = current.company_id.map(names)
    a, b, c, d = st.columns(4)
    a.metric('匹配企业', f'{len(companies):,}')
    b.metric('有产品／技术描述', f'{current.content_status.ne("资料不足").sum():,}')
    c.metric('年度事件', f'{len(selected_events):,}')
    d.metric('资料年份线索', f'{len(clues):,}')
    st.caption('图例：现状为当前产品与技术；黄色菱形为工作簿资料年份线索。年度变化统计采用有来源的年度事件。')

    tab_matrix, tab_annual = st.tabs(['全部企业技术地图', '年度变化'])
    with tab_matrix:
        company_names = sorted(companies.name.tolist())
        chosen_name = st.selectbox('定位企业', ['全部'] + company_names,
                                   key='enterprise_timeline_company')
        if chosen_name != '全部':
            shown_names = [chosen_name]
        else:
            page_count = (len(company_names) + 24) // 25
            page = st.number_input('企业页码（每页 25 家）', min_value=1,
                                   max_value=page_count, value=1, step=1,
                                   key='enterprise_timeline_page')
            shown_names = company_names[(page-1)*25:page*25]
        shown_ids = set(companies.loc[companies.name.isin(shown_names), 'company_id'])
        points = []
        for event in selected_events.loc[selected_events.company_id.isin(shown_ids)].itertuples():
            points.append({'位置': str(event.event_year), '企业': event.company_name,
                           '节点类型': event.event_type, '内容': event.title,
                           '时间口径': event.event_date, '来源': event.evidence_level,
                           'record_kind': 'event', 'record_id': event.event_id})
        for clue in clues.loc[clues.company_id.isin(shown_ids)].itertuples():
            points.append({'位置': str(clue.observation_year), '企业': clue.company_name,
                           '节点类型': '资料年份线索', '内容': clue.title,
                           '时间口径': clue.date_basis, '来源': clue.source_basis,
                           'record_kind': 'observation', 'record_id': clue.observation_id})
        for state in current.loc[current.company_id.isin(shown_ids)].itertuples():
            points.append({'位置': '现状', '企业': state.company_name,
                           '节点类型': '资料待补' if state.content_status == '资料不足' else '当前产品／技术',
                           '内容': state.title, '时间口径': state.date_basis,
                           '来源': state.source_basis,
                           'record_kind': 'observation', 'record_id': state.observation_id})
        positions = [str(year) for year in range(year_range[0], year_range[1]+1)] + ['现状']
        colors = {**EVENT_COLORS, '资料年份线索': '#D5A454',
                  '当前产品／技术': '#137F75', '资料待补': '#A5B1BE'}
        symbols = {'资料年份线索': 'diamond', '当前产品／技术': 'circle',
                   '资料待补': 'circle-open'}
        fig = px.scatter(pd.DataFrame(points), x='位置', y='企业', color='节点类型',
                         symbol='节点类型', hover_name='内容',
                         hover_data={'企业': False, '位置': True, '时间口径': True, '来源': True},
                         custom_data=['record_kind', 'record_id'],
                         category_orders={'位置': positions, '企业': list(reversed(shown_names))},
                         color_discrete_map=colors, symbol_map=symbols,
                         labels={'位置': '年份／当前状态'})
        fig.update_traces(marker=dict(size=12, line=dict(width=1, color='white')))
        fig.update_layout(height=max(430, 39 * len(shown_names) + 120),
                          margin=dict(l=15, r=20, t=20, b=20),
                          legend=dict(orientation='h', y=-0.15), plot_bgcolor='rgba(0,0,0,0)')
        st.caption('点击图中的节点，可查看对应企业的档案与节点内容。')
        st.plotly_chart(fig, width='stretch', key='enterprise_timeline_points',
                        on_select=lambda: _on_timeline_select(set(shown_names)),
                        selection_mode='points')
        st.markdown('**本页企业产品与技术**')
        brief = current.loc[current.company_id.isin(shown_ids),
                            ['company_name', 'title', 'content_status']].copy()
        brief.columns = ['企业', '产品／技术概况', '内容状态']
        brief = brief.sort_values('企业').reset_index(drop=True)
        st.caption('点击企业行左侧的选择框，可打开该企业档案。')
        st.dataframe(brief, hide_index=True, width='stretch', height=320,
                     key='enterprise_timeline_brief',
                     on_select=lambda: _on_brief_select(brief['企业'].tolist()),
                     selection_mode='single-row')
        detail_name = st.selectbox('查看企业现状与来源', shown_names,
                                   key='enterprise_timeline_detail')
        state = current.loc[current.company_name.eq(detail_name)].iloc[0]
        st.markdown('**当前产品／技术**')
        st.write(state['product_summary'] or '未查到可确认的具体产品。')
        st.write(state['technology_summary'] or '未查到可确认的具体技术路线。')
        st.caption(f"依据：{tr(state['source_basis'])} · {tr(state['date_basis'])}")
        _source_button(state['source_url'], f"state_source_{state['observation_id']}")
        company_clues = clues.loc[clues.company_name.eq(detail_name)]
        for clue in company_clues.itertuples():
            st.write(f'{clue.observation_year} · 资料年份线索：{tr(clue.title)}')
            st.caption(f'{tr(clue.date_basis)} · {tr(clue.source_basis)}')
            _source_button(clue.source_url, f'clue_source_{clue.observation_id}')
    with tab_annual:
        if selected_events.empty:
            st.info('当前筛选范围没有有来源的年度事件。')
        else:
            yearly = selected_events.groupby(['event_year', 'event_type']).size().reset_index(name='事件数')
            yearly['event_year'] = yearly.event_year.astype(str)
            annual_fig = px.bar(yearly, x='event_year', y='事件数', color='event_type',
                                color_discrete_map=EVENT_COLORS, barmode='stack',
                                labels={'event_year': '年份', 'event_type': '事件类型'})
            annual_fig.update_layout(height=420, margin=dict(l=10, r=10, t=15, b=30),
                                     legend=dict(orientation='h', y=-0.22),
                                     plot_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(annual_fig, width='stretch')
            counts = selected_events.groupby('event_year').company_id.nunique().rename('有事件的企业数')
            st.dataframe(counts, width='stretch')

    if not selected_events.empty:
        st.subheader('年度事件与来源')
        choices = selected_events.sort_values(['event_year', 'company_name'],
                                              ascending=[False, True]).reset_index(drop=True)
        index = st.selectbox('选择一条事件', choices.index.tolist(),
                             format_func=lambda i: f"{choices.loc[i, 'event_year']} · {choices.loc[i, 'company_name']} · {tr(choices.loc[i, 'title'])}",
                             key='enterprise_event_choice')
        event = choices.loc[index]
        st.markdown(f"**{tr(event['title'])}**")
        st.write(event['detail'])
        precision = '年份级' if event['date_precision'] == 'year' else '具体日期'
        st.caption(f"时间：{event['event_date']}（{tr(precision)}） · 医疗对象：{event['p_codes'] or '未明确'} · 类型：{tr(event['event_type'])} · 依据：{tr(event['evidence_level'])}")
        if event['technology']:
            st.write(f"技术／工艺：{tr(event['technology'])}")
        if event['material']:
            st.write(f"材料：{tr(event['material'])}")
        _source_button(event['source_url'], f"timeline_source_{event['event_id']}", event['evidence_level'])


def enterprise_explorer(companies: pd.DataFrame, events: pd.DataFrame,
                        observations: pd.DataFrame) -> None:
    _hero('企业检索与档案', '检索企业、产品与技术平台，查看官网、业务方向和资料记载的逐年变化。')
    if companies.empty:
        st.info('没有匹配的企业，请调整筛选条件。')
        return
    st.caption(f'找到 {len(companies):,} 家企业')
    table = companies.loc[:, ['name', 'country', 'p_codes', 'status', 'event_count']].copy()
    table.columns = ['企业', '国家／地区', 'P 分类', '企业状态', '年度事件']
    st.dataframe(table, hide_index=True, width='stretch', height=350)
    names = companies.sort_values('name').name.tolist()
    selected_name = st.selectbox('选择企业查看档案', names, key='enterprise_selected_company',
                                 on_change=lambda: st.session_state.pop('enterprise_focus_record', None))
    company = companies.loc[companies.name.eq(selected_name)].iloc[0]
    current = observations.loc[observations.company_id.eq(company['company_id']) &
                               observations.observation_kind.eq('当前现状')]
    st.subheader(company['name'])
    st.caption(f"{tr(company['country'])} · {tr(company['status'])} · {company['p_codes'] or 'P 类待确认'}")
    if company['website']:
        st.markdown(f"官方网站：[访问 {company['website']}]({company['website']})")
    else:
        st.caption('官方网站：暂无可确认公开链接')
    focus_kind, focus_id = st.session_state.get('enterprise_focus_record', ('', ''))
    if focus_kind == 'event':
        focus = events.loc[events.company_id.eq(company['company_id']) & events.event_id.eq(focus_id)]
        if not focus.empty:
            item = focus.iloc[0]
            st.markdown(f"**来自技术路线图的节点 · {item['event_year']} · {tr(item['event_type'])}**")
            st.write(item['title'])
            st.write(item['detail'])
            _source_button(item['source_url'], f"focus_source_{item['event_id']}", item['evidence_level'])
    elif focus_kind == 'observation':
        focus = observations.loc[observations.company_id.eq(company['company_id']) &
                                 observations.observation_id.eq(focus_id)]
        if not focus.empty and focus.iloc[0]['observation_kind'] == '资料年份线索':
            item = focus.iloc[0]
            st.markdown(f"**来自技术路线图的资料年份线索 · {item['observation_year']}**")
            st.write(item['title'])
            _source_button(item['source_url'], f"focus_source_{item['observation_id']}")
    if not current.empty:
        state = current.iloc[0]
        st.caption(f"内容状态：{tr(state['content_status'])} · 来源核查：{tr(company['source_status'])} · {tr(state['date_basis'])} · {tr(state['source_basis'])}")
        _source_button(state['source_url'], f"profile_state_{state['observation_id']}")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown('**产品与服务**')
        st.write(state['product_summary'] if not current.empty and state['product_summary']
                 else '未查到可确认的医疗增材制造产品。')
    with c2:
        st.markdown('**技术路线**')
        st.write(state['technology_summary'] if not current.empty and state['technology_summary']
                 else '未查到可确认的医疗增材制造技术路线。')
    company_clues = observations.loc[
        observations.company_id.eq(company['company_id']) &
        observations.observation_kind.eq('资料年份线索')].sort_values('observation_year', ascending=False)
    if not company_clues.empty:
        st.markdown('**资料年份线索（非发布年份）**')
        for clue in company_clues.itertuples():
            st.write(f'{clue.observation_year} · {tr(clue.title)}')
            st.caption(f'{tr(clue.date_basis)} · {tr(clue.source_basis)}')
            _source_button(clue.source_url, f'profile_clue_{clue.observation_id}')
    st.markdown('**逐年事件**')
    company_events = events.loc[events.company_id.eq(company['company_id'])].sort_values(
        ['event_year', 'event_date'], ascending=False)
    if company_events.empty:
        st.info('目前未找到足以确认具体年份和产品／技术变化的公开资料。')
    else:
        for event in company_events.itertuples():
            with st.expander(f'{event.event_year} · {tr(event.event_type)} · {tr(event.title)}'):
                st.write(event.detail)
                if event.technology:
                    st.write(f'技术／工艺：{tr(event.technology)}')
                if event.material:
                    st.write(f'材料：{tr(event.material)}')
                precision = '年份级' if event.date_precision == 'year' else '具体日期'
                st.caption(f'时间：{event.event_date}（{tr(precision)}） · 医疗对象：{event.p_codes or "未明确"} · 依据：{tr(event.evidence_level)}')
                _source_button(event.source_url, f'profile_source_{event.event_id}', event.evidence_level)

"""Paper–enterprise comparison pages with traceable, question-level evidence."""
from __future__ import annotations

import html
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.cross_data import (
    CROSS_CUTTING, direction_summary, load_direction_classification, themed_direction_summary,
)
from dashboard.labels import P, label
from dashboard.i18n import (LOCALIZED_SELECTION_KEYS, clear_localized_selection,
                            tr, language, preserve_original_text, protect_names, localized_selectbox)
from dashboard.report_navigation import open_question_report
from dashboard.direction_reports import (
    UI, direction_id, direction_report_url, localized_direction_title, open_direction_report,
)


def _open_company_profile(company: str) -> None:
    for key in ('enterprise_countries', 'enterprise_p_codes', 'enterprise_statuses'):
        clear_localized_selection(st.session_state, key)
    st.session_state['enterprise_query'] = company
    st.session_state['page'] = '企业检索'


def _open_paper_profile(paper_id: str) -> None:
    for key in ('years', 'p_layers', 'tiers', 'diseases', 'processes', 'materials',
                'work_types', 'paper_page', 'selected_paper', 'include_future'):
        (clear_localized_selection(st.session_state, key) if key in LOCALIZED_SELECTION_KEYS
         else st.session_state.pop(key, None))
    st.session_state['query'] = paper_id
    st.session_state['page'] = '论文检索'


def _select_direction_from_table() -> None:
    """Use the clicked summary row to choose the detailed direction below."""
    rows = st.session_state['cross_direction_table']['selection']['rows']
    options = st.session_state['cross_direction_options']
    if rows and 0 <= rows[0] < len(options):
        st.session_state['cross_direction'] = options[rows[0]]
        st.session_state['cross_scroll_to_direction'] = True


def _select_cross_cutting() -> None:
    st.session_state['cross_direction'] = CROSS_CUTTING
    st.session_state['cross_scroll_to_direction'] = True


def _direction_picker(data: dict, root: Path, classification: dict) -> dict:
    code = language()
    directions = themed_direction_summary(data, classification)
    st.subheader('H01–H36 研究方向')
    selected_p = localized_selectbox(
        st, '医疗对象', ['全部'] + [f'P{i}' for i in range(1, 8)],
        format_func=lambda value: '全部 P 层' if value == '全部' else label(value, P),
        key='cross_p',
    )
    visible = [row for row in directions
               if selected_p == '全部' or selected_p in row['p_layers']]
    report_rows = [row for row in visible if row['id'] != CROSS_CUTTING]
    titles = {row['id']: localized_direction_title(root, row['id'], code) for row in visible}
    options = [row['id'] for row in report_rows]
    st.session_state['cross_direction_options'] = options
    table = pd.DataFrame([{
        'P 层': ' / '.join(row['p_layers']),
        '研究方向': titles[row['id']],
        '研究问题': len(row['questions']),
        '主题关联论文': row['paper_count'],
        '问题关联企业': row['companies'],
        '报告': direction_report_url(row['id'], code),
    } for row in report_rows])
    st.dataframe(
        table, hide_index=True, width='stretch', height=380,
        column_config={'报告': st.column_config.LinkColumn(UI[code]['read'], display_text=UI[code]['read'])},
        key='cross_direction_table', on_select=_select_direction_from_table,
        selection_mode='single-row',
    )
    st.caption(tr('主题关联来自 H36 分类资料与论文库的匹配，共 {n} 篇；研究问题按主方向计数。')
               .format(n=f"{classification['unique_papers_with_theme']:,}"))
    if CROSS_CUTTING in titles:
        st.button(titles[CROSS_CUTTING] + f" ({len(classification['cross_cutting'])})",
                  key='open_cross_cutting', on_click=_select_cross_cutting)
    if selected_p == '全部':
        st.markdown('**学术与企业证据分布**')
        points = table.drop(columns=['报告'])
        fig = px.scatter(points, x='主题关联论文', y='问题关联企业',
                         color='P 层', hover_name='研究方向',
                         hover_data={'研究问题': True})
        fig.update_traces(marker={'size': 11, 'opacity': .8})
        fig.update_layout(height=390, margin=dict(l=10, r=20, t=15, b=20),
                          plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation='h', y=-0.16))
        st.plotly_chart(fig, width='stretch')
    selection = localized_selectbox(
        st, '选择研究方向', list(titles), key='cross_direction', format_func=titles.__getitem__,
    )
    return next(row for row in visible if row['id'] == selection)


def cross_analysis_page(data: dict, available_reports: set[str] | None = None) -> None:
    root = Path(__file__).resolve().parents[1]
    classification = load_direction_classification(root)
    hero_copy = (tr('从 36 个技术主题进入方向报告，或按研究问题查阅论文、企业技术和来源。')
                 if classification else tr('从医疗对象进入研究方向，再沿研究问题查看论文、企业技术与外部依据。'))
    st.markdown(
        '<div class="hero"><div class="eyebrow">ACADEMIC × INDUSTRY · RESEARCH MAP</div>'
        f'<h1>{html.escape(tr("学术与企业联系"))}</h1><p>{html.escape(hero_copy)}</p></div>',
        unsafe_allow_html=True,
    )
    questions = data['questions']
    evidence = data['enterprise_evidence']
    paper_rows = data['papers']
    a, b, c, d = st.columns(4)
    a.metric('研究方向', len(classification['directions']) if classification else len(direction_summary(data)))
    b.metric('研究问题', len(questions))
    c.metric('问题关联论文', f"{len({row['id'] for row in paper_rows}):,}")
    d.metric('对应企业', len({row['company'] for row in evidence
                          if row['source_kind'] != '非企业开源项目'}))
    if classification:
        chosen = _direction_picker(data, root, classification)
        scope = [q for q in questions if q['question_id'] in chosen['questions']]
        rid = chosen['id'] if chosen['id'] != CROSS_CUTTING else None
        heading = localized_direction_title(root, chosen['id'], language())
    else:
        directions = direction_summary(data)
        st.subheader('七个 P 层中的研究方向')
        selected_p = localized_selectbox(st,'医疗对象', ['全部'] + [f'P{i}' for i in range(1, 8)],
                                  format_func=lambda code: '全部 P 层' if code == '全部' else label(code, P),
                                  key='cross_p')
        visible = [row for row in directions if selected_p == '全部' or row['p'] == selected_p]
        table = pd.DataFrame([{'P 层': label(row['p'], P), '研究方向': row['direction'],
                               '研究问题': row['questions'], '关联论文': row['papers'],
                               '有来源的企业': row['companies'], '具体技术对应问题': row['direct']}
                              for row in visible])
        table['报告'] = [f'?view=direction-report&direction={direction_id(root,r["p"],r["direction"])}&lang={language()}' for r in visible]
        direction_options = [f"{row['p']} · {row['direction']}" for row in visible]
        st.session_state['cross_direction_options'] = direction_options
        st.dataframe(table, hide_index=True, width='stretch', height=350,
                     column_config={'报告':st.column_config.LinkColumn(UI[language()]['read'],display_text=UI[language()]['read'])},
                     key='cross_direction_table', on_select=_select_direction_from_table,
                     selection_mode='single-row')
        if selected_p == '全部':
            st.markdown('**学术与企业证据分布**')
            points = pd.DataFrame([{'P 层': row['p'], '研究方向': row['direction'],
                                    '关联论文': row['papers'], '有来源的企业': row['companies'],
                                    '研究问题': row['questions']}
                                   for row in directions])
            chart = px.scatter(points, x='关联论文', y='有来源的企业', color='P 层',
                               size='研究问题', hover_name='研究方向',
                               size_max=22)
            chart.update_layout(height=460, margin=dict(l=10, r=20, t=15, b=20),
                                plot_bgcolor='rgba(0,0,0,0)', legend=dict(orientation='h', y=-0.16))
            st.plotly_chart(chart, width='stretch')

        choice = localized_selectbox(st,'选择研究方向', direction_options, key='cross_direction',
                              format_func=lambda option: tr(option))
        chosen = visible[direction_options.index(choice)]
        scope = [q for q in questions if q['p'] == chosen['p'] and q['direction'] == chosen['direction']]
        rid = direction_id(root, chosen['p'], chosen['direction'])
        heading = f"{chosen['p']} · {chosen['direction']}"
    ids = {q['question_id'] for q in scope}
    scoped_papers = [p for p in paper_rows if p['question_id'] in ids]
    st.html('<div id="cross-direction-detail" style="scroll-margin-top:100px"></div>')
    direction_title, direction_button = st.columns([5,1.6],vertical_alignment='center')
    direction_title.subheader(heading)
    if rid:
        direction_button.button(UI[language()]['read'],key='open_direction_report',type='primary',on_click=open_direction_report,args=(rid,))
    if st.session_state.pop('cross_scroll_to_direction', False):
        st.html('''<script>
        requestAnimationFrame(() => {
            const target = document.getElementById('cross-direction-detail');
            if (target) target.scrollIntoView({behavior:'smooth', block:'start'});
        });
        </script>''', unsafe_allow_javascript=True)
    c1, c2, c3 = st.columns(3)
    c1.metric('研究问题', len(scope))
    if classification and rid:
        c2.metric('主题关联论文', chosen['paper_count'])
        years = {int(year): count for year, count in chosen['paper_year_counts'].items()}
        axis = '主题关联论文'
    else:
        c2.metric('问题关联论文', len({p['id'] for p in scoped_papers}))
        years = Counter(year for year, _ in {(p['year'], p['id']) for p in scoped_papers})
        axis = '问题关联论文'
    c3.metric('问题关联企业', chosen['companies'])
    if years:
        timeline = pd.DataFrame({'年份': sorted(years), axis: [years[y] for y in sorted(years)]})
        fig = px.bar(timeline, x='年份', y=axis, text=axis, color_discrete_sequence=['#137F75'])
        fig.update_layout(height=320, margin=dict(l=10, r=15, t=10, b=20),
                          plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, width='stretch')

    related_ids = chosen.get('related', [])
    if related_ids:
        code = language()
        question_lookup = {q['question_id']: q['question'] for q in questions}
        with st.expander(tr('相关研究问题')+f' ({len(related_ids)})', expanded=not scope):
            for qid in related_ids:
                st.link_button(f'{qid} · {tr(question_lookup[qid])}',
                               direction_report_url(qid, code, question=True),
                               key=f'related_question_{qid}')
    if not scope:
        return

    options = [q['question_id'] for q in scope]
    by_id = {q['question_id']: q for q in scope}
    selected_language = language()
    project_root = Path(__file__).resolve().parents[1]
    selected = localized_selectbox(st,'选择研究问题', options,
                            format_func=lambda qid, c=selected_language, r=project_root:
                            f"{qid} · {tr(by_id[qid]['question'], code=c, root=r)}",
                            key='cross_question')
    question = by_id[selected]
    title_col, report_col = st.columns([5, 1.5], vertical_alignment='center')
    title_col.markdown(f"### {html.escape(tr(question['question']))}")
    if available_reports is None or selected in available_reports:
        report_col.button('查看分析报告 →', key=f'open_question_report_{selected}',
                          type='primary', on_click=open_question_report, args=(selected,))
    st.caption(f"企业对应：{question['status']}")
    matched = [row for row in evidence if row['question_id'] == selected]
    if matched:
        st.markdown('**企业技术与产品证据**')
        for item in matched:
            with st.container(border=True):
                match_level = tr(item['match_level'])
                with preserve_original_text():
                    st.markdown(f"**{html.escape(item['company'])}** · {match_level}")
                st.write(item['evidence_summary'])
                st.caption(item['stage'])
                st.link_button('查看企业资料来源 ↗', item['source_url'],
                               key=f"cross_source_{selected}_{item['evidence_id']}")
                if item['source_kind'] != '非企业开源项目':
                    st.button('在企业档案中检索',
                              key=f"cross_company_{selected}_{item['evidence_id']}",
                              on_click=_open_company_profile, args=(item['company'],))
    else:
        st.info('此问题暂未找到可核实的具体企业技术对应。')

    related = [row for row in data['contexts'] if selected in row['ids'].split()]
    if related:
        with st.expander(f'相关专利、法规与标准（{len(related)}）'):
            for item in related:
                st.markdown(f"**{html.escape(tr(item['title']))}** · {tr(item['kind'])}")
                st.caption(item['note'])
                st.link_button('查看文件原始路径 ↗', item['url'],
                               key=f"cross_context_{selected}_{item['context_id']}")

    relevant = sorted((p for p in scoped_papers if p['question_id'] == selected),
                      key=lambda p: (-p['year'], p['title']))
    st.markdown(f'**相关论文（{len(relevant)} 条对应记录）**')
    if relevant:
        page_count = (len(relevant) + 19) // 20
        page = st.number_input('论文页码（每页 20 篇）', min_value=1, max_value=page_count,
                               value=1, step=1, key=f'cross_paper_page_{selected}')
        shown = relevant[(page-1)*20:page*20]
        st.caption('将鼠标悬停在论文名称上可查看中文归纳；点击“查看”进入论文检索中的对应记录。')
        st.markdown('<style>.cross-paper-title{cursor:help;line-height:1.5;overflow-wrap:anywhere}</style>',
                    unsafe_allow_html=True)
        with st.container(border=True):
            for paper in shown:
                year_col, title_col, action_col = st.columns([1, 8, 1.4], vertical_alignment='center')
                year_col.write(str(paper['year']))
                localized_summary = tr(paper['summary'])
                with preserve_original_text():
                    title_col.markdown(
                        f'<span class="cross-paper-title" title="{html.escape(localized_summary, quote=True)}">'
                        f'{html.escape(paper["title"])}</span>', unsafe_allow_html=True)
                action_col.button('查看 ↗', key=f'cross_open_paper_{selected}_{paper["id"]}',
                                  on_click=_open_paper_profile, args=(paper['id'],))
        titles = [f"{p['year']} · {p['title']}" for p in shown]
        protect_names(titles)
        paper_choice = st.selectbox('查看论文详情与 DOI', range(len(shown)),
                                    format_func=lambda i: titles[i], key=f'cross_paper_{selected}')
        paper = shown[paper_choice]
        st.write(paper['summary'])
        if paper['doi']:
            doi_url = 'https://doi.org/' + paper['doi'].removeprefix('https://doi.org/')
            st.link_button('打开 DOI 原文入口 ↗', doi_url, key=f"cross_doi_{selected}_{paper['id']}")

"""Paper–enterprise comparison pages with traceable, question-level evidence."""
from __future__ import annotations

import html
from collections import Counter
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.cross_data import direction_summary
from dashboard.labels import P, label
from dashboard.i18n import (LOCALIZED_SELECTION_KEYS, clear_localized_selection,
                            tr, language, preserve_original_text, protect_names)
from dashboard.report_navigation import open_question_report


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


def cross_analysis_page(data: dict, available_reports: set[str] | None = None) -> None:
    st.markdown(
        '<div class="hero"><div class="eyebrow">ACADEMIC × INDUSTRY · RESEARCH MAP</div>'
        '<h1>学术与企业联系</h1><p>从医疗对象进入研究方向，再沿研究问题查看论文、企业技术与外部依据。</p></div>',
        unsafe_allow_html=True,
    )
    directions = direction_summary(data)
    questions = data['questions']
    evidence = data['enterprise_evidence']
    paper_rows = data['papers']
    a, b, c, d = st.columns(4)
    a.metric('研究方向', len(directions))
    b.metric('研究问题', len(questions))
    c.metric('关联论文', f"{len({row['id'] for row in paper_rows}):,}")
    d.metric('对应企业', len({row['company'] for row in evidence
                          if row['source_kind'] != '非企业开源项目'}))
    st.subheader('七个 P 层中的研究方向')
    selected_p = st.selectbox('医疗对象', ['全部'] + [f'P{i}' for i in range(1, 8)],
                              format_func=lambda code: '全部 P 层' if code == '全部' else label(code, P),
                              key='cross_p')
    visible = [row for row in directions if selected_p == '全部' or row['p'] == selected_p]
    table = pd.DataFrame([{'P 层': label(row['p'], P), '研究方向': row['direction'],
                           '研究问题': row['questions'], '关联论文': row['papers'],
                           '有来源的企业': row['companies'], '具体技术对应问题': row['direct']}
                          for row in visible])
    st.dataframe(table, hide_index=True, width='stretch', height=350)
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

    direction_options = [f"{row['p']} · {row['direction']}" for row in visible]
    choice = st.selectbox('选择研究方向', direction_options, key='cross_direction',
                          format_func=lambda option: tr(option))
    chosen = visible[direction_options.index(choice)]
    scope = [q for q in questions if q['p'] == chosen['p'] and q['direction'] == chosen['direction']]
    ids = {q['question_id'] for q in scope}
    scoped_papers = [p for p in paper_rows if p['question_id'] in ids]
    st.subheader(f"{chosen['p']} · {chosen['direction']}")
    c1, c2, c3 = st.columns(3)
    c1.metric('研究问题', len(scope))
    c2.metric('关联论文', len({p['id'] for p in scoped_papers}))
    c3.metric('有来源的企业', chosen['companies'])
    if scoped_papers:
        annual = Counter((p['year'], p['id']) for p in scoped_papers)
        years = Counter(year for year, _ in annual)
        timeline = pd.DataFrame({'年份': sorted(years), '论文数': [years[y] for y in sorted(years)]})
        fig = px.bar(timeline, x='年份', y='论文数', text='论文数', color_discrete_sequence=['#137F75'])
        fig.update_layout(height=320, margin=dict(l=10, r=15, t=10, b=20),
                          plot_bgcolor='rgba(0,0,0,0)')
        st.plotly_chart(fig, width='stretch')

    options = [q['question_id'] for q in scope]
    by_id = {q['question_id']: q for q in scope}
    selected_language = language()
    project_root = Path(__file__).resolve().parents[1]
    selected = st.selectbox('选择研究问题', options,
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

"""Direction and question navigation, with links to the full reports."""
from __future__ import annotations

from pathlib import Path

import streamlit as st

from dashboard.cross_data import CROSS_CUTTING, load_direction_classification
from dashboard.i18n import (LOCALIZED_SELECTION_KEYS, clear_localized_selection,
                            tr, language, localized_selectbox)
from dashboard.report_navigation import open_question_report
from dashboard.direction_reports import (
    direction_id, localized_direction_title, open_direction_report,
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


def cross_analysis_page(data: dict, available_reports: set[str] | None = None) -> None:
    root = Path(__file__).resolve().parents[1]
    code = language()
    classification = load_direction_classification(root)
    questions = data['questions']
    if classification:
        choices = {
            group['id']: localized_direction_title(root, group['id'], code)
            for group in classification['directions']
        }
        if classification['cross_cutting']:
            choices[CROSS_CUTTING] = localized_direction_title(root, CROSS_CUTTING, code)
    else:
        choices = {
            f"{q['p']} · {q['direction']}": q['direction']
            for q in questions
        }

    st.title('研究方向与研究问题')
    picker, action = st.columns([5, 2], vertical_alignment='bottom')
    with picker:
        selected_direction = localized_selectbox(
            st, '选择研究方向', list(choices), key='cross_direction',
            format_func=lambda value: tr(choices[value], code=code, root=root),
        )
    if classification:
        scope = [q for q in questions if q['direction_id'] == selected_direction]
        rid = selected_direction if selected_direction != CROSS_CUTTING else None
    else:
        scope = [q for q in questions if f"{q['p']} · {q['direction']}" == selected_direction]
        rid = direction_id(root, scope[0]['p'], scope[0]['direction'])

    if rid:
        action.button('查看方向报告 →', key='open_direction_report', on_click=open_direction_report,
                      args=(rid,), width='stretch')
    if not scope:
        return
    by_id = {q['question_id']: q for q in scope}
    picker, action = st.columns([5, 2], vertical_alignment='bottom')
    with picker:
        selected = localized_selectbox(
            st, '选择研究问题', list(by_id), key='cross_question',
            format_func=lambda qid: f"{qid} · {tr(by_id[qid]['question'], code=code, root=root)}",
        )
    if available_reports is None or selected in available_reports:
        action.button('查看问题报告 →', key=f'open_question_report_{selected}', type='primary',
                      on_click=open_question_report, args=(selected,), width='stretch')

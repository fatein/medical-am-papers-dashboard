"""Callbacks keep report URLs and ordinary page navigation in sync."""
from collections.abc import Mapping

import streamlit as st


def resolve_report_id(params: Mapping[str, str], questions: list[dict]) -> str | None:
    if params.get('view') != 'question-report':
        return None
    return str(params.get('question', ''))


def clear_report_route() -> None:
    for key in ('view', 'question'):
        st.query_params.pop(key, None)


def open_question_report(question_id: str) -> None:
    keys = ('cross_p', 'cross_direction', 'cross_question', f'cross_paper_page_{question_id}')
    st.session_state['report_return_state'] = {
        key: st.session_state[key] for key in keys if key in st.session_state}
    st.session_state['report_return_question'] = question_id
    st.session_state['report_scroll_to_top'] = True
    st.query_params['view'] = 'question-report'
    st.query_params['question'] = question_id
    st.session_state['page'] = '学术与企业联系'


def restore_question_context(question: dict | None) -> None:
    clear_report_route()
    st.session_state['page'] = '学术与企业联系'
    if not question:
        for key in ('cross_p', 'cross_direction', 'cross_question'):
            st.session_state.pop(key, None)
        return
    qid = question['question_id']
    saved = st.session_state.get('report_return_state', {}) if st.session_state.get('report_return_question') == qid else {}
    st.session_state['cross_p'] = saved.get('cross_p', question['p'])
    st.session_state['cross_direction'] = f"{question['p']} · {question['direction']}"
    st.session_state['cross_question'] = qid
    key = f'cross_paper_page_{qid}'
    st.session_state[key] = saved.get(key, 1)


def open_report_paper(paper_id: str) -> None:
    from dashboard.cross_views import _open_paper_profile
    clear_report_route()
    _open_paper_profile(paper_id)


def open_report_company(company: str) -> None:
    from dashboard.cross_views import _open_company_profile
    clear_report_route()
    _open_company_profile(company)

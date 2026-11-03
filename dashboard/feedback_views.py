"""Paper feedback forms and the public, categorized feedback summary."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4

import pandas as pd
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from .data import safe_csv
from .feedback_data import DIMENSIONS, FEEDBACK_TYPES, make_paper_feedback, paper_classification
from .feedback_store import FeedbackStoreError, GitHubFeedbackStore, SQLiteFeedbackStore
from .i18n import language, localized_selectbox, preserve_original_text, protect_names
from .labels import label

STATUS_LABELS = {'pending': '待处理', 'resolved': '已处理'}


def get_feedback_store(root: Path, public_mode: bool):
    try:
        settings = dict(st.secrets.get('feedback', {}))
    except (FileNotFoundError, StreamlitSecretNotFoundError):
        settings = {}
    token = settings.get('token') or os.environ.get('AM_FEEDBACK_TOKEN', '')
    repository = settings.get('repository') or os.environ.get(
        'AM_FEEDBACK_REPOSITORY', 'fatein/medical-am-papers-dashboard')
    if token or public_mode:
        return GitHubFeedbackStore(repository, token)
    path = os.environ.get('AM_FEEDBACK_LOCAL_PATH') or Path(root)/'.runtime/feedback.sqlite3'
    return SQLiteFeedbackStore(Path(path))


def _show_store_error(error):
    if error.reason == 'permission':
        st.error('反馈服务暂不可用，请稍后重试。')
    elif error.reason == 'not_configured':
        st.info('反馈提交暂未启用。')
    else:
        st.error('反馈保存失败，请稍后重试。输入内容已保留。')


def _open_summary():
    from .report_navigation import clear_report_route
    clear_report_route()
    st.session_state['page'] = '反馈汇总'


def _toggle_form(paper_id):
    current = st.session_state.get('_am_feedback_open_id')
    st.session_state['_am_feedback_open_id'] = None if current == paper_id else paper_id


def paper_feedback(paper, root: Path, public_mode=False):
    paper_id = str(paper['document_id'])
    st.button('分类反馈', key=f'paper_feedback_open_{paper_id}',
              on_click=_toggle_form, args=(paper_id,))
    if st.session_state.get('_am_feedback_open_id') != paper_id:
        return
    store = get_feedback_store(root, public_mode)
    with st.container(border=True):
        st.markdown('**论文分类反馈**')
        st.caption('选择建议分类，并补充相关说明。反馈将在反馈汇总中公开展示。')
        before = paper_classification(paper)
        if not store.writable:
            st.info('反馈提交暂未启用。')
        # Synchronize draft widget edits before a sidebar language change.
        with st.container():
            suggested = {}
            columns = st.columns(2)
            for index, (code, (title, _, mapping)) in enumerate(DIMENSIONS.items()):
                options = list(mapping)
                if before[code] not in options:
                    options.append(before[code])
                with columns[index % 2]:
                    suggested[code] = localized_selectbox(
                        st, title, options, key=f'feedback_{paper_id}_{code}',
                        index=options.index(before[code]),
                        format_func=lambda item, labels=mapping: label(item, labels))
            description = st.text_area('反馈说明', key=f'feedback_{paper_id}_description',
                                       max_chars=3000, height=120,
                                       placeholder='说明不准确之处，或提供支持建议分类的论文内容与来源。')
            submitted = st.button('提交反馈', key=f'feedback_submit_{paper_id}',
                                  type='primary', disabled=not store.writable)
        if submitted:
            fingerprint = hashlib.sha256(json.dumps(
                [paper_id, suggested, description.strip()], ensure_ascii=False,
                sort_keys=True).encode()).hexdigest()
            ids = st.session_state.setdefault('feedback_submission_ids', {})
            submission_id = ids.setdefault(fingerprint, str(uuid4()))
            try:
                record = make_paper_feedback(paper, suggested, description, language=language(),
                                             submission_id=submission_id)
                receipt = store.submit(record)
            except ValueError:
                st.warning('请至少修改一个分类，或填写反馈说明。')
            except FeedbackStoreError as error:
                _show_store_error(error)
            else:
                st.success('反馈已提交。')
                st.caption('反馈编号：' + receipt['feedback_id'])
        st.button('查看反馈汇总', key=f'paper_feedback_summary_{paper_id}', on_click=_open_summary)


def _display_feedback(item):
    with preserve_original_text():
        st.subheader(item['subject_title'])
    st.caption(item['submitted_at'].replace('T', ' ')[:19] + ' UTC · ' + item['subject_id'])
    st.write('处理状态：', STATUS_LABELS.get(item['status'], '待处理'))
    if item['feedback_type'] == 'paper_classification':
        rows = []
        for code, (title, _, mapping) in DIMENSIONS.items():
            before = item['original_classification'][code]
            after = item['suggested_classification'][code]
            rows.append({'分类维度': title, '原分类': label(before, mapping),
                         '建议分类': label(after, mapping), '是否修改': '是' if before != after else '否'})
        st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    st.markdown('**反馈说明**')
    with preserve_original_text():
        st.text(item['description'] or '—')
    if item['feedback_type'] == 'paper_classification':
        from .report_navigation import open_report_paper
        st.button('查看对应论文', key='feedback_open_paper', on_click=open_report_paper,
                  args=(item['subject_id'],))
    if item.get('source_url', '').startswith('https://github.com/'):
        st.link_button('查看反馈记录 ↗', item['source_url'])


def feedback_summary(root: Path, public_mode=False):
    st.markdown('<div class="hero"><div class="eyebrow">FEEDBACK</div>'
                '<h1>反馈汇总</h1><p>查看论文分类建议与分析报告评估。</p></div>',
                unsafe_allow_html=True)
    left, middle, right = st.columns([2, 4, 1])
    with left:
        status = localized_selectbox(st,'处理状态', ['all', 'pending', 'resolved'],
                              format_func=lambda code: '全部状态' if code == 'all' else STATUS_LABELS[code],
                              key='feedback_status')
    with middle:
        query = st.text_input('检索反馈', placeholder='论文名称、编号或反馈内容…', key='feedback_query')
    with right:
        st.button('刷新', key='feedback_refresh')
    try:
        items = get_feedback_store(root, public_mode).list_feedback()
    except (FeedbackStoreError, ValueError):
        st.error('暂时无法读取反馈，请稍后刷新。')
        return
    protect_names(item['subject_title'] for item in items)
    metrics = st.columns(3)
    metrics[0].metric('反馈总数', str(len(items)))
    metrics[1].metric('待处理', str(sum(item['status'] == 'pending' for item in items)))
    metrics[2].metric('已处理', str(sum(item['status'] == 'resolved' for item in items)))
    tabs = st.tabs(list(FEEDBACK_TYPES.values()))
    for (category, _), tab in zip(FEEDBACK_TYPES.items(), tabs):
        with tab:
            selected = [item for item in items if item['feedback_type'] == category
                        and (status == 'all' or item['status'] == status)
                        and (not query.strip() or query.strip().casefold() in
                             ' '.join(str(item.get(field, '')) for field in
                                      ('subject_id', 'subject_title', 'description')).casefold())]
            if not selected:
                st.info('暂无符合条件的论文分类反馈。' if category == 'paper_classification'
                        else '分析报告评估将归集在此分类。')
                continue
            table = pd.DataFrame([{
                '反馈编号': item['feedback_id'], '提交时间（UTC）': item['submitted_at'][:19].replace('T', ' '),
                '论文题名': item['subject_title'], '变更维度': '、'.join(item.get('changed_dimensions', [])) or '说明',
                '处理状态': STATUS_LABELS[item['status']],
            } for item in selected])
            st.dataframe(table, hide_index=True, width='stretch', height=300)
            export = table.copy()
            export['反馈说明'] = [item['description'] for item in selected]
            for code in DIMENSIONS:
                export[f'{code} 原分类'] = [item.get('original_classification', {}).get(code, '') for item in selected]
                export[f'{code} 建议分类'] = [item.get('suggested_classification', {}).get(code, '') for item in selected]
            st.download_button('下载反馈 CSV', safe_csv(export), file_name=f'feedback_{category}.csv',
                                mime='text/csv', key=f'feedback_download_{category}')
            by_id = {item['feedback_id']: item for item in selected}
            key = f'feedback_selected_{category}'
            if st.session_state.get(key) not in by_id:
                st.session_state.pop(key, None)
            choice = st.selectbox('查看反馈详情', list(by_id), key=key,
                                  format_func=lambda ident: by_id[ident]['subject_title'])
            with st.container(border=True):
                _display_feedback(by_id[choice])

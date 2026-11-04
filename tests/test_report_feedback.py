import json
from datetime import datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from dashboard.feedback_data import make_report_feedback, validate_feedback
from dashboard.feedback_store import SQLiteFeedbackStore, encode_issue_body, _decode_issue


@pytest.mark.parametrize('kind,ident', [('direction', 'P1-01'), ('question', 'P1-001')])
def test_report_feedback_roundtrip_and_timestamp(tmp_path, kind, ident):
    record = make_report_feedback(ident, '报告名称', kind, 4, '图表解读需要补充来源。', version='2026-11-04')
    assert datetime.fromisoformat(record['submitted_at']).utcoffset().total_seconds() == 0
    store = SQLiteFeedbackStore(tmp_path/'feedback.db')
    store.submit(record)
    assert store.list_feedback()[0]['report_kind'] == kind
    decoded = _decode_issue({'body': encode_issue_body(record), 'state': 'open'})
    assert decoded['rating'] == 4
    assert decoded['submitted_at'] == record['submitted_at']
    assert decoded['subject_id'] == ident
    assert 'Rating: 4 / 5' in encode_issue_body(record)


def test_empty_or_invalid_report_feedback_rejected():
    with pytest.raises(ValueError):
        make_report_feedback('P1-001', 'Title', 'question', 5, '  ')
    with pytest.raises(ValueError):
        make_report_feedback('P1-001', 'Title', 'question', 6, 'text')


def test_report_form_submits_to_summary_with_time(tmp_path, monkeypatch):
    monkeypatch.setenv('AM_FEEDBACK_LOCAL_PATH', str(tmp_path/'feedback.db'))
    monkeypatch.delenv('AM_FEEDBACK_TOKEN', raising=False)
    app = AppTest.from_string('''
from pathlib import Path
from dashboard.feedback_views import report_feedback, feedback_summary
import dashboard.feedback_views as views
from dashboard.feedback_store import SQLiteFeedbackStore
import os
views.get_feedback_store = lambda *args: SQLiteFeedbackStore(Path(os.environ['AM_FEEDBACK_LOCAL_PATH']))
report_feedback('P1-001', '孔径如何影响骨长入？', 'question', Path('.'))
feedback_summary(Path('.'))
''', default_timeout=20).run()
    assert not app.exception
    app.button(key='report_feedback_open_question_P1-001').click().run()
    app.text_area(key='report_description_question_P1-001').input('需要解释孔径测量方法。')
    app.button(key='report_submit_question_P1-001').click().run()
    assert not app.exception
    rows = SQLiteFeedbackStore(tmp_path/'feedback.db').list_feedback()
    assert len(rows) == 1
    assert rows[0]['description'] == '需要解释孔径测量方法。'
    assert any('提交时间' in str(d.value.columns) for d in app.dataframe)
    assert any(b.label == '查看对应报告' for b in app.button)


def test_new_feedback_labels_are_translated():
    root = Path(__file__).resolve().parents[1]
    for code in ('en', 'de'):
        mapping = json.loads((root/'data/i18n'/f'{code}.json').read_text(encoding='utf-8'))
        for key in ('报告反馈', '报告质量反馈', '质量评分', '报告名称', '查看对应报告', '请填写反馈说明。'):
            assert mapping[key] != key


def test_academic_reader_uses_localized_report_title_for_feedback(monkeypatch):
    from dashboard import academic_questions, feedback_views
    class Captured(Exception):
        pass
    report = {'question_id': 'P1-001', 'updated_at': '2026-11-04',
              'references': [], 'figures': [],
              'locales': {code: {'title': '孔道问题' if code == 'zh' else 'Pore question'}
                          for code in ('zh', 'en', 'de')}}
    def capture(ident, title, kind, *args, **kwargs):
        assert (ident, title, kind) == ('P1-001', '孔道问题', 'question')
        raise Captured()
    monkeypatch.setattr(feedback_views, 'report_feedback', capture)
    with pytest.raises(Captured):
        academic_questions.academic_question_page(report, None, Path('.'))

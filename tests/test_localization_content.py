"""Integrity checks for localized report chronology and source links."""
from collections import Counter
import json
from pathlib import Path
import re

import pytest

from dashboard.i18n import set_language, tr
from dashboard.report_views import render_cited_markdown

ROOT=Path(__file__).resolve().parents[1]
YEAR=re.compile(r'(?<!\d)(?:19|20)\d{2}(?!\d)')
REF=re.compile(r'ref:([A-Za-z0-9_-]+)')


@pytest.mark.parametrize('code',['en','de'])
def test_all_question_report_dates_and_reference_ids_survive_translation(code):
    reports=json.loads((ROOT/'data/question_reports.json').read_text('utf8'))['reports']
    try:
        set_language(code,ROOT)
        for qid,report in reports.items():
            for section in report['sections']:
                source=section['markdown']
                target=tr(source)
                assert Counter(YEAR.findall(target))==Counter(YEAR.findall(source)), (code,qid,section['id'])
                assert REF.findall(target)==REF.findall(source), (code,qid,section['id'])
                rendered=render_cited_markdown(section,report['references'])
                assert 'ref:' not in rendered
                for ref_id in REF.findall(source):
                    ref=next(ref for ref in report['references'] if ref['id']==ref_id)
                    assert ref['url'].replace('&','&amp;') in rendered
    finally:
        set_language('zh',ROOT)

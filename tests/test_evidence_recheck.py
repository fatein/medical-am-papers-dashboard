"""Integrity and semantic regressions for the November source recheck."""
import hashlib
import json
from pathlib import Path
import re

import pandas as pd

from dashboard.i18n import tr
from dashboard.views import evidence_field

ROOT=Path(__file__).resolve().parents[1]
COLUMNS={'p_layer':'analysis_primary_p_layer','tier':'analysis_corpus_tier',
         'disease':'disease_primary_code','process':'am_process_primary_code',
         'material':'material_primary_code','bioprinting':'bioprinting_flag'}

def reviewed():
    return json.loads((ROOT/'docs/paper-evidence-recheck-2026-11-05.json').read_text(encoding='utf-8'))

def papers():
    return pd.read_csv(ROOT/'data/papers_pre2026.csv',keep_default_na=False,dtype=str).set_index('document_id')

def test_all_507_decisions_are_present_and_released_evidence_matches_review():
    audit=reviewed();data=papers();rows=audit['records']
    assert len(rows)==507 and len({r['task_id'] for r in rows})==507
    assert sum(r['task_id'].startswith('excerpt-') for r in rows)==366
    assert sum(r['task_id'].startswith('label-') for r in rows)==141
    assert len(data)==6092
    for r in rows:
        paper=data.loc[r['document_id']];prefix=r['field']+'_evidence_'
        assert paper[COLUMNS[r['field']]]==r['code'],r['task_id']
        assert hashlib.sha256(paper[prefix+'text'].encode()).hexdigest()==r['evidence_sha256'],r['task_id']
        assert paper[prefix+'section']==r['section'] and paper[prefix+'pages']==r['pages']
        if r['decision']!='skip' and paper[prefix+'text']:
            assert evidence_field(paper,prefix+'text'),r['task_id']

def test_recheck_distinguishes_administration_files_affiliations_and_real_devices():
    audit={r['task_id']:r for r in reviewed()['records']};data=papers()
    expected={'label-002':'D14', 'label-009':'D4','label-011':'P6',
              'excerpt-096':'D0','excerpt-099':'U','excerpt-125':'U',
              'excerpt-275':'T4','excerpt-310':'T1','excerpt-331':'P7',
              'label-003':'MULTI','label-082':'T4','label-101':'T1'}
    for task,code in expected.items():
        row=audit[task]
        assert data.loc[row['document_id'],COLUMNS[row['field']]]==code,task
    for task in ('excerpt-275','excerpt-310','label-003','label-082','label-101'):
        r=audit[task];assert evidence_field(data.loc[r['document_id']],r['field']+'_evidence_text')

def test_new_generic_source_labels_display_in_both_languages():
    for lang in ('en','de'):
        for source in ('PDF 正文','XML 全文','题名'):
            assert not re.search('[\u3400-\u9fff]',tr(source,code=lang,root=ROOT))

def test_public_review_register_contains_no_private_source_paths_or_quotes():
    raw=(ROOT/'docs/paper-evidence-recheck-2026-11-05.json').read_text(encoding='utf-8')
    assert not re.search(r'(?i)[A-Z]:[\\/]|file://',raw)
    assert all('evidence_text' not in r for r in reviewed()['records'])

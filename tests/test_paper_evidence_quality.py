"""Regression checks for evidence displayed in public paper profiles."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from dashboard.views import evidence_field
from dashboard.public_data import public_download_frame
from dashboard.i18n import tr


ROOT = Path(__file__).resolve().parents[1]
BAD_DISPLAY = re.compile(r'[\ufffd\uf000-\uf8ff\u25a1\u25af\x00-\x08\x0b\x0e-\x1f]')


def public_records():
    history = pd.read_csv(ROOT / 'data/papers_pre2026.csv', keep_default_na=False)
    additions = [json.loads(line) for line in
                 (ROOT / 'data/additions.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    return pd.concat([history, pd.DataFrame(additions)], ignore_index=True)


def test_paper_evidence_does_not_display_legacy_placeholder_or_garbled_glyphs():
    for _, row in public_records().iterrows():
        for prefix in ('p_layer', 'tier', 'disease', 'process', 'material', 'bioprinting'):
            text = evidence_field(row, prefix + '_evidence_text')
            assert not BAD_DISPLAY.search(text), (row.document_id, prefix, text[:100])
            assert not text.lower().startswith('insufficient evidence'), (row.document_id, prefix)


def test_hand_assistive_device_evidence_describes_its_own_device():
    row = public_records().set_index('document_id').loc['doc_44188debf12eee40ec89']
    medical_object = evidence_field(row, 'p_layer_evidence_text')
    application = evidence_field(row, 'disease_evidence_text')
    assert 'www.' not in medical_object
    assert 'hand' in medical_object.casefold() and 'device' in medical_object.casefold()
    assert 'stroke' in application.casefold()
    assert row['p_layer_evidence_pages'] in ('2', '3')


def test_stl_file_and_surface_treatment_are_not_called_vat_photopolymerization():
    papers = public_records().set_index('document_id')
    expected = {
        'doc_e91c251620f47a25be5e': 'T2',
        'doc_accb004801da5bb2b299': 'T2',
        'doc_d9e185217f44d4c1f854': 'T2',
        'doc_a58f56372c6a5671abf3': 'T2',
        'doc_da246ff167be76b71b4a': 'T2',
        'doc_7b1d4f475627ae2fde17': 'T3',
        'doc_22918ebb2f3722a30a35': 'T2',
        'doc_5d26ddbede8e44717787': 'T2',
        'doc_fbedf615bfcb5e0c6a08': 'T2',
        'doc_5a54faf77f98e707347a': 'T2',
        'doc_e7f171ea129ed7eb2ffa': 'T3',
        'doc_4d519e1896514c30da4e': 'T2',
        'doc_57d02ed7b8d11cb712dc': 'T3',
    }
    for docid, code in expected.items():
        paper = papers.loc[docid]
        assert paper['am_process_primary_code'] == code, docid
        assert evidence_field(paper, 'process_evidence_text')
        assert paper['process_evidence_pages'].isdigit(), docid


def test_export_does_not_restore_damaged_or_placeholder_evidence():
    frame = pd.DataFrame([
        {'document_id': 'one', 'p_layer_evidence_text': ' www.example.com unrelated links'},
        {'document_id': 'two', 'process_evidence_text': 'insufficient evidence'},
    ])
    exported = public_download_frame(frame)
    assert exported.loc[0, 'p_layer_evidence_text'] == ''
    assert exported.loc[1, 'process_evidence_text'] == ''


def test_front_matter_and_reference_lists_do_not_appear_as_label_evidence():
    examples = [
        'Acknowledgements The authors thank the laboratory for providing specimens.',
        'Abbreviations CAD Computer-aided design; STL Stereolithography file.',
        'https://doi.org/10.1234/example Copyright 2024 by the authors.',
        'Technique Types of Materials Advantages Limitations References [12, 13]',
        'www.example.com Product list www.example.org Manufacturer list',
    ]
    for example in examples:
        assert evidence_field({'material_evidence_text': example}, 'material_evidence_text') == ''


def test_german_missing_evidence_uses_scholarly_beleg_term():
    assert tr('未记录证据。', code='de', root=ROOT) == 'Keine Belegstelle erfasst.'

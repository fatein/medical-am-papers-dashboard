"""Versioned visitor feedback; suggestions never mutate the paper dataset."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from .labels import P, D, T, M

FEEDBACK_TYPES = {'paper_classification': '论文分类反馈',
                  'report_evaluation': '分析报告评估'}
DIMENSIONS = {
    'P': ('医疗对象（P）', 'analysis_primary_p_layer', P),
    'D': ('疾病／应用（D）', 'disease_primary_code', D),
    'T': ('制造工艺（T）', 'am_process_primary_code', T),
    'M': ('材料体系（M）', 'material_primary_code', M),
}


def paper_classification(paper) -> dict[str, str]:
    return {code: str(paper.get(column, 'U') or 'U')
            for code, (_, column, _) in DIMENSIONS.items()}


def validate_feedback(record: dict) -> None:
    if not isinstance(record, dict) or record.get('schema_version') != 1:
        raise ValueError('Invalid feedback schema')
    if record.get('feedback_type') not in FEEDBACK_TYPES:
        raise ValueError('Invalid feedback type')
    for field in ('feedback_id', 'subject_id', 'subject_title', 'submitted_at'):
        if not isinstance(record.get(field), str) or not record[field].strip():
            raise ValueError('Missing feedback identity')
    if len(record['feedback_id']) > 100 or len(record['subject_id']) > 200:
        raise ValueError('Invalid feedback identity')
    try:
        datetime.fromisoformat(record['submitted_at'].replace('Z', '+00:00'))
    except ValueError as error:
        raise ValueError('Invalid feedback date') from error
    description = record.get('description')
    if not isinstance(description, str) or len(description) > 3000:
        raise ValueError('Invalid feedback description')
    dimensions = record.get('changed_dimensions', [])
    if (not isinstance(dimensions, list) or any(not isinstance(code, str) or code not in DIMENSIONS
                                               for code in dimensions)):
        raise ValueError('Invalid changed dimensions')
    for field in ('original_classification', 'suggested_classification'):
        values = record.get(field, {})
        if not isinstance(values, dict) or any(
                code not in DIMENSIONS or not isinstance(value, str) or len(value) > 64
                for code, value in values.items()):
            raise ValueError('Invalid classification map')
    if record['feedback_type'] == 'paper_classification':
        before, after = (record.get(field) for field in
                         ('original_classification', 'suggested_classification'))
        if (not isinstance(before, dict) or not isinstance(after, dict)
                or set(before) != set(DIMENSIONS) or set(after) != set(DIMENSIONS)):
            raise ValueError('Four classification dimensions are required')
        for code, (_, _, mapping) in DIMENSIONS.items():
            if (not isinstance(before[code], str) or not isinstance(after[code], str)
                    or after[code] not in mapping and after[code] != before[code]):
                raise ValueError('Invalid classification code')
        changes = [code for code in DIMENSIONS if before[code] != after[code]]
        if record.get('changed_dimensions') != changes:
            raise ValueError('Inconsistent classification changes')
        if not changes and not description.strip():
            raise ValueError('A suggested change or description is required')


def make_paper_feedback(paper, suggested: dict[str, str], description: str,
                        *, language: str = 'zh', submission_id: str | None = None) -> dict:
    before = paper_classification(paper)
    item = {
        'schema_version': 1, 'feedback_id': submission_id or str(uuid4()),
        'feedback_type': 'paper_classification',
        'subject_id': str(paper['document_id']), 'subject_title': str(paper['title']),
        'subject_year': int(paper['publication_year']), 'doi': str(paper.get('doi', '') or ''),
        'submitted_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'language': language, 'original_classification': before,
        'suggested_classification': dict(suggested), 'description': description.strip(),
        'changed_dimensions': [code for code in DIMENSIONS if suggested.get(code) != before[code]],
    }
    validate_feedback(item)
    return item

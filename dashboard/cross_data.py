"""Read the reviewed paper–enterprise crosswalk and compute visible counts."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from statistics import median


def load_cross_analysis(root: Path) -> dict:
    return json.loads((Path(root) / 'data/cross_analysis.json').read_text(encoding='utf-8'))


def direction_summary(data: dict) -> list[dict]:
    grouped = defaultdict(lambda: {'questions': 0, 'paper_links': 0,
                                   'paper_ids': set(), 'companies': set(),
                                   'direct': 0, 'adjacent': 0})
    by_question = {}
    for question in data['questions']:
        key = (question['p'], question['direction'])
        row = grouped[key]
        row['questions'] += 1
        row['direct'] += question['status'] == '直接企业对应'
        row['adjacent'] += question['status'] == '相关平台/企业线索'
        by_question[question['question_id']] = key
    for paper in data['papers']:
        row = grouped[by_question[paper['question_id']]]
        row['paper_links'] += 1
        row['paper_ids'].add(paper['id'])
    for item in data['enterprise_evidence']:
        if item['source_kind'] != '非企业开源项目':
            grouped[by_question[item['question_id']]]['companies'].add(item['company'])
    return [{'p': p, 'direction': direction, 'questions': value['questions'],
             'paper_links': value['paper_links'], 'papers': len(value['paper_ids']),
             'companies': len(value['companies']), 'direct': value['direct'],
             'adjacent': value['adjacent']}
            for (p, direction), value in grouped.items()]


def relative_evidence_position(summary: list[dict]) -> list[dict]:
    """Label this curated dataset's relative coverage, never market demand."""
    if not summary:
        return []
    paper_middle = median(row['papers'] for row in summary)
    company_middle = median(row['companies'] for row in summary)
    result = []
    for row in summary:
        paper_high = row['papers'] >= paper_middle
        company_high = row['companies'] >= company_middle
        name = ({(True, True): '双侧记录较多',
                 (True, False): '论文较多、企业证据较少',
                 (False, True): '企业证据较多、论文较少',
                 (False, False): '双侧记录较少'}[(paper_high, company_high)])
        result.append({**row, 'position': name})
    return result

"""Project bibliographic data and concise, path-free evidence for public sharing."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd

from .data import deduplicate, normalize_records


PUBLIC_COLUMNS = (
    'document_id', 'title', 'publication_year', 'authors', 'source_journal',
    'doi', 'pmid', 'pmcid', 'analysis_primary_p_layer',
    'disease_primary_code', 'am_process_primary_code', 'material_primary_code',
    'bioprinting_flag', 'evidence_scope', 'analysis_corpus_tier',
    'normalized_work_type', 'lexical_theme_id', 'bibliometric_recommended',
    'medical_am_relevance', 'relevance_basis',
    *(
        f'{dimension}_{part}'
        for dimension in ('p_layer', 'tier', 'disease', 'process', 'material', 'bioprinting')
        for part in ('evidence_text', 'evidence_section', 'evidence_pages', 'review_status')
    ),
)
PUBLIC_PACKAGE_FILES = frozenset({
    '.streamlit/config.toml', 'LICENSE', 'README.md', 'requirements.txt',
    'app.py', 'public_app.py',
    'dashboard/__init__.py', 'dashboard/analytics.py', 'dashboard/charts.py',
    'dashboard/data.py', 'dashboard/filter_state.py', 'dashboard/labels.py',
    'dashboard/public_data.py', 'dashboard/views.py',
    'data/papers_pre2026.csv', 'data/additions.jsonl', 'data/manifest.json',
})

_PRIVATE_PATH = re.compile(r'(?i)(?<![A-Z])[A-Z]:[\\/]|file://|\\\\[^\\]')
EVIDENCE_EXCERPT_LIMIT = 700
FUTURE_EVIDENCE_EXCERPT_LIMIT = 900


def _read_source(root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    history = normalize_records(pd.read_csv(root/'data/papers_pre2026.csv', keep_default_na=False))
    addition = root/'data/additions.jsonl'
    rows = [json.loads(line) for line in addition.read_text(encoding='utf-8').splitlines()
            if line.strip()] if addition.exists() else []
    future = normalize_records(pd.DataFrame(rows)) if rows else history.iloc[:0].copy()
    if not history.publication_year.lt(2026).all() or not future.publication_year.ge(2026).all():
        raise ValueError('来源年份与历史／后续数据分区不一致。')
    combined = pd.concat([history, future], ignore_index=True)
    _, rejected = deduplicate(combined)
    if not rejected.empty:
        raise ValueError(f'来源含重复论文：{len(rejected)} 条。')
    return history, future


def _select_public(frame: pd.DataFrame) -> pd.DataFrame:
    public = frame.copy()
    if 'p_layer_evidence_text' not in public and 'cross_layer_evidence_text' in public:
        for part in ('evidence_text', 'evidence_section', 'evidence_pages'):
            public[f'p_layer_{part}'] = public.get(f'cross_layer_{part}', '')
    public = public.reindex(columns=PUBLIC_COLUMNS, fill_value='').fillna('')
    for column in public.columns:
        if 'evidence_' in column or column.endswith('_review_status'):
            public[column] = [
                _public_evidence(str(value), FUTURE_EVIDENCE_EXCERPT_LIMIT
                                 if year >= 2026 else EVIDENCE_EXCERPT_LIMIT)
                for value, year in zip(public[column], public['publication_year'])
            ]
    if public.select_dtypes(include=['object', 'string']).astype(str).apply(
            lambda col: col.str.contains(_PRIVATE_PATH)).any().any():
        raise ValueError('公开字段含本机路径。')
    return public


def _public_evidence(value: str, limit: int = EVIDENCE_EXCERPT_LIMIT) -> str:
    """Publish a brief evidence excerpt; never expose a local file reference."""
    value = value.strip()
    if _PRIVATE_PATH.search(value):
        return '已隐去本机文件路径；请通过 DOI 核查原文。'
    if len(value) > limit:
        return value[:limit].rstrip() + '…（证据节选）'
    return value


def project_public_data(root: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    root = Path(root)
    history, future = _read_source(root)
    public_history, public_future = _select_public(history), _select_public(future)
    years = pd.concat([history.publication_year, future.publication_year], ignore_index=True)
    manifest = {
        'historical_rows': len(history),
        'year_2026_rows': int(future.publication_year.eq(2026).sum()),
        'recommended_for_bibliometrics_2026': int(
            future.loc[future.publication_year.eq(2026), 'bibliometric_recommended'].sum()),
        'total_rows': len(history) + len(future),
        'year_min': int(years.min()),
        'year_max': int(years.max()),
        'notes': ['项目收录语料；2026 年仍在持续补充，不与完整年度直接比较。'],
    }
    return public_history, public_future, manifest


def validate_public_package(root: Path) -> dict:
    root = Path(root)
    actual = {path.relative_to(root).as_posix() for path in root.rglob('*') if path.is_file()
              and '.git' not in path.relative_to(root).parts}
    extra, missing = actual-PUBLIC_PACKAGE_FILES, PUBLIC_PACKAGE_FILES-actual
    if extra:
        raise ValueError(f'公开包含非白名单文件：{sorted(extra)}')
    if missing:
        raise ValueError(f'公开包缺少文件：{sorted(missing)}')
    config = (root/'.streamlit/config.toml').read_text(encoding='utf-8')
    if re.search(r'(?im)^\s*(address|port)\s*=', config):
        raise ValueError('公开包包含本机监听地址或端口。')
    with (root/'data/manifest.json').open(encoding='utf-8') as handle:
        manifest = json.load(handle)
    history = pd.read_csv(root/'data/papers_pre2026.csv', keep_default_na=False)
    future = pd.read_json(root/'data/additions.jsonl', lines=True) if (root/'data/additions.jsonl').stat().st_size else pd.DataFrame(columns=PUBLIC_COLUMNS)
    for name, frame in (('data/papers_pre2026.csv', history), ('data/additions.jsonl', future)):
        text_fields = frame.select_dtypes(include=['object', 'string']).astype(str)
        if text_fields.apply(lambda col: col.str.contains(_PRIVATE_PATH)).any().any():
            raise ValueError(f'公开包包含本机路径：{name}')
    if _PRIVATE_PATH.search(json.dumps(manifest, ensure_ascii=False)):
        raise ValueError('公开包包含本机路径：data/manifest.json')
    if tuple(history.columns) != PUBLIC_COLUMNS or tuple(future.columns) != PUBLIC_COLUMNS:
        raise ValueError('公开包数据列不等于字段白名单。')
    if not history.publication_year.lt(2026).all() or not future.publication_year.ge(2026).all():
        raise ValueError('公开包年度分区错误。')
    combined = pd.concat([normalize_records(history), normalize_records(future)], ignore_index=True)
    _, rejected = deduplicate(combined)
    if not rejected.empty:
        raise ValueError('公开包包含重复论文。')
    expected = {
        'historical_rows': len(history),
        'year_2026_rows': int(future.publication_year.eq(2026).sum()),
        'recommended_for_bibliometrics_2026': int(
            normalize_records(future).loc[future.publication_year.eq(2026), 'bibliometric_recommended'].sum()),
        'total_rows': len(combined),
    }
    if any(manifest.get(key) != value for key, value in expected.items()):
        raise ValueError('公开包清单与实际论文数量不一致。')
    return expected


def public_download_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.reindex(columns=PUBLIC_COLUMNS, fill_value='').fillna('')

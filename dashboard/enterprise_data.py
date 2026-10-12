"""Read and filter the public company and sourced-event catalogues."""
from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


P_CODES = frozenset(f'P{i}' for i in range(1, 8))
EVENT_COLUMNS = (
    'event_id', 'company_id', 'event_year', 'event_date', 'date_precision',
    'event_type', 'title', 'detail', 'p_codes', 'technology', 'material',
    'source_url', 'source_title', 'source_date', 'evidence_level',
)


def normalize_public_url(value: object) -> str:
    """Keep a single externally usable http(s) URL, never a local path."""
    text = str(value or '').strip().split()[0] if str(value or '').strip() else ''
    parsed = urlparse(text)
    if parsed.scheme.lower() not in {'http', 'https'} or not parsed.netloc:
        return ''
    if any(char in text for char in ('\\', '<', '>', '"')):
        return ''
    return text


def parse_p_codes(value: object) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        code for code in re.split(r'[;；,，\s]+', str(value or '').upper())
        if code in P_CODES
    ))


def latest_dated_claim(summary: object, year: int) -> str:
    """Extract only the clause attached to the requested year."""
    text = str(summary or '').strip()
    for clause in re.split(r'(?<=[；;。])', text):
        years = re.findall(r'20(?:2[1-6])', clause)
        if str(year) in years and len(set(years)) == 1:
            return clause.strip()
    return ''


def load_enterprises(root: Path) -> pd.DataFrame:
    path = Path(root) / 'data/enterprises.csv'
    return pd.read_csv(path, keep_default_na=False)


def load_enterprise_events(root: Path) -> pd.DataFrame:
    path = Path(root) / 'data/enterprise_events.jsonl'
    if not path.exists() or not path.stat().st_size:
        return pd.DataFrame(columns=EVENT_COLUMNS)
    frame = pd.read_json(path, lines=True)
    for col in EVENT_COLUMNS:
        if col not in frame:
            frame[col] = ''
    frame['event_year'] = pd.to_numeric(frame.event_year, errors='raise').astype(int)
    return frame.loc[:, EVENT_COLUMNS]


def filter_enterprises(
    companies: pd.DataFrame,
    countries: list[str] | None = None,
    p_codes: list[str] | None = None,
    query: str = '',
    statuses: list[str] | None = None,
) -> pd.DataFrame:
    mask = pd.Series(True, index=companies.index)
    if countries is not None:
        mask &= companies.country.isin(countries)
    if statuses is not None:
        mask &= companies.status.isin(statuses)
    if p_codes is not None:
        wanted = set(p_codes)
        if wanted != P_CODES:
            mask &= companies.p_codes.map(lambda value: bool(wanted.intersection(parse_p_codes(value))))
    if query.strip():
        needle = query.strip().casefold()
        fields = [col for col in ('name', 'product_summary', 'technology_summary', 'company_id') if col in companies]
        found = pd.Series(False, index=companies.index)
        for field in fields:
            found |= companies[field].astype(str).str.casefold().str.contains(needle, regex=False)
        mask &= found
    return companies.loc[mask].copy()


def yearly_event_summary(events: pd.DataFrame) -> pd.DataFrame:
    if events.empty:
        return pd.DataFrame(columns=['events', 'companies']).rename_axis('event_year')
    return events.groupby('event_year').agg(
        events=('company_id', 'size'), companies=('company_id', 'nunique')
    )

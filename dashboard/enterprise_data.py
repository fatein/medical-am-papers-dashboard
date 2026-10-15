"""Read and filter the public company and sourced-event catalogues."""
from __future__ import annotations

import re
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd


P_CODES = frozenset(f'P{i}' for i in range(1, 8))
EVENT_COLUMNS = (
    'event_id', 'company_id', 'event_year', 'event_date', 'date_precision',
    'event_type', 'title', 'detail', 'p_codes', 'technology', 'material',
    'source_url', 'source_title', 'source_date', 'evidence_level',
)
OBSERVATION_COLUMNS = (
    'observation_id', 'company_id', 'observation_kind', 'observation_year',
    'title', 'product_summary', 'technology_summary', 'p_codes',
    'source_url', 'source_basis', 'date_basis', 'content_status',
)
_PLACEHOLDER = re.compile(r'暂无可核实|暂无可核验|暂无可确认|未查到可确认|未找到可确认|无可核实|未取得同时证明')
_YEAR = re.compile(r'(?<!\d)(20(?:1\d|2[0-6]))\s*年')
_YEAR_RANGE = re.compile(r'20(?:1\d|2[0-6])\s*[—–~－-]\s*20(?:1\d|2[0-6])\s*年')
_SUBJECT = re.compile(r'产品|技术|打印|制造|植入|义齿|导板|假体|模型|材料|设备|系统|服务|软件|工艺|骨科|牙科')
_ASSERTION = re.compile(r'列出|提及|采用|应用|推出|发布|升级|获得|获批|上市|完成|增加|扩展|使用|开始|开发|披露|供应|销售|推出')
_NEGATIVE = re.compile(r'计划|拟推出|拟发布|拟在|预计|预期|未发现|未查到|未找到|暂无|不足以|未证明|未确认|未将|没有|不能|无法|并非|不证明|不应|待确认|召回|但不|奖项.*决赛')
# Date mentions that the prior source audit identified as unrelated to a
# confirmed medical additive-manufacturing product/technology change.
YEAR_CLUE_EXCLUSIONS = frozenset({
    ('CMP-3f6516bfdecf259e', 2024),  # CTL implant clearance: AM not established
    ('CMP-218871a6275db67b', 2026),  # PSI platform: printing not established
    ('CMP-86d190098e1aba11', 2025),  # parent-company product, subsidiary attribution
    ('CMP-fc0c202661bf7043', 2026),  # MOVE-P implantation: AM not established
    ('CMP-907e560ea7e81470', 2024),  # ROSA system: AM not established
    ('CMP-b1dfb1325a9f2f26', 2023),  # acquisition: AM connection not established
    ('CN-COMP-f51890545a4d558b9033', 2024),  # survey, no product update
    ('CN-COMP-12759f29459b6963', 2026),  # report publication, not product year
    ('COM-9286fe110789e13c', 2023),  # image software clearance, no AM proof
    ('CMP-e72bbdc8aac657cb', 2025),  # veterinary product, outside human medical scope
    ('COM-16ca85fc4cd0d8ab', 2026),  # general market explainer
    ('CMP-9d85f6911016fa36', 2025),  # therapy licence, no AM proof
    ('COM-4ec5772f6d13bd85', 2025),  # award finalist, no product change
})


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
    base = pd.read_csv(path, keep_default_na=False)
    additions_path = Path(root) / 'data/enterprise_cross_additions.json'
    if not additions_path.exists():
        return base
    additions = pd.DataFrame(json.loads(additions_path.read_text(encoding='utf-8')))
    if additions.empty:
        return base
    if (set(additions.company_id) & set(base.company_id) or
            set(additions.name.str.casefold()) & set(base.name.str.casefold())):
        raise ValueError('新增企业与原企业库存在重复主体。')
    return pd.concat([base, additions.reindex(columns=base.columns, fill_value='')],
                     ignore_index=True)


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


def _substantive_summary(value: object) -> str:
    value = str(value or '').strip()
    return '' if not value or _PLACEHOLDER.search(value) and len(value) < 160 else value


def _profile_source(company: object) -> tuple[str, str]:
    source_status = str(getattr(company, 'source_status', '') or '')
    for candidate in str(getattr(company, 'source_urls', '') or '').split('|'):
        url = normalize_public_url(candidate)
        if url:
            return url, ('补充核验来源' if source_status == '补充来源已核验'
                         else '企业档案参考来源')
    website = normalize_public_url(getattr(company, 'website', ''))
    return (website, '企业官网入口') if website else ('', '暂无公开链接')


def _observation_id(company_id: str, kind: str, year: int, title: str) -> str:
    digest = hashlib.sha256(f'{company_id}|{kind}|{year}|{title}'.encode('utf-8')).hexdigest()[:16]
    return f'OBS-{digest}'


def build_observations(companies: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Give every company a current-state record; keep year clues out of events."""
    dated = {(str(row.company_id), int(row.event_year)) for row in events.itertuples()}
    rows = []
    for company in companies.itertuples():
        company_id = str(company.company_id)
        product = _substantive_summary(getattr(company, 'product_summary', ''))
        technology = _substantive_summary(getattr(company, 'technology_summary', ''))
        source_url, source_basis = _profile_source(company)
        status = '有产品或技术描述' if product or technology else '资料不足'
        title = (product or technology)[:100].strip('；;。 ') if status != '资料不足' else '未查到可确认的医疗增材制造产品／技术'
        rows.append({
            'observation_id': _observation_id(company_id, '当前现状', 0, title),
            'company_id': company_id, 'observation_kind': '当前现状',
            'observation_year': 0, 'title': title,
            'product_summary': product, 'technology_summary': technology,
            'p_codes': str(getattr(company, 'p_codes', '') or ''),
            'source_url': source_url, 'source_basis': source_basis,
            'date_basis': '截至资料核查日的档案现状；不是产品发布日期',
            'content_status': status,
        })
        if not source_url:
            continue
        seen_years = set()
        for summary in (product, technology):
            for clause in re.split(r'[；;。\n]+', summary):
                clause = clause.strip()
                years = {int(match) for match in _YEAR.findall(clause)}
                if (len(years) != 1 or _YEAR_RANGE.search(clause) or _NEGATIVE.search(clause)
                        or not (_SUBJECT.search(clause) and _ASSERTION.search(clause))):
                    continue
                year = years.pop()
                if ((company_id, year) in dated or (company_id, year) in YEAR_CLUE_EXCLUSIONS
                        or year in seen_years):
                    continue
                seen_years.add(year)
                rows.append({
                    'observation_id': _observation_id(company_id, '资料年份线索', year, clause),
                    'company_id': company_id, 'observation_kind': '资料年份线索',
                    'observation_year': year, 'title': clause[:160],
                    'product_summary': '', 'technology_summary': '',
                    'p_codes': str(getattr(company, 'p_codes', '') or ''),
                    'source_url': '',
                    'source_basis': '工作簿年份叙述；未逐条核验外部来源',
                    'date_basis': '工作簿叙述年份；非发布日期',
                    'content_status': '年份线索待逐条独立核验',
                })
    result = pd.DataFrame(rows, columns=OBSERVATION_COLUMNS)
    if result.observation_id.duplicated().any():
        raise ValueError('企业观测记录 ID 重复。')
    return result


def load_enterprise_observations(root: Path) -> pd.DataFrame:
    path = Path(root) / 'data/enterprise_observations.jsonl'
    if not path.exists() or not path.stat().st_size:
        return pd.DataFrame(columns=OBSERVATION_COLUMNS)
    frame = pd.read_json(path, lines=True, dtype={'company_id': str, 'observation_id': str})
    frame = frame.reindex(columns=OBSERVATION_COLUMNS, fill_value='').fillna('')
    additions_path = Path(root) / 'data/enterprise_cross_additions.json'
    if not additions_path.exists():
        return frame
    additions = pd.DataFrame(json.loads(additions_path.read_text(encoding='utf-8')))
    if additions.empty:
        return frame
    if set(additions.company_id) & set(frame.company_id):
        raise ValueError('新增企业现状与原观测记录重复。')
    current = build_observations(additions, pd.DataFrame(columns=EVENT_COLUMNS))
    return pd.concat([frame, current], ignore_index=True)


def observation_coverage(companies: pd.DataFrame, observations: pd.DataFrame) -> dict:
    current = observations.loc[observations.observation_kind.eq('当前现状')]
    missing = set(companies.company_id) - set(current.company_id)
    return {
        'company_rows': len(companies),
        'current_state_companies': current.company_id.nunique(),
        'missing_current_state': len(missing),
        'year_clues': int(observations.observation_kind.eq('资料年份线索').sum()),
        'limited_profiles': int(current.content_status.eq('资料不足').sum()),
    }

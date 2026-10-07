"""Read-only historical data and separately persisted future additions."""
from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
import uuid
import os
import threading
import time
from contextlib import contextmanager
from zipfile import BadZipFile
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo

import pandas as pd
from openpyxl.utils.exceptions import InvalidFileException
from .labels import P, D, T, M

BOOL_FIELDS = ['manual_review_required','bioprinting_flag',
               'disease_manual_review_required','process_manual_review_required',
               'material_manual_review_required','p_layer_manual_review_required',
               'bibliometric_recommended','pdf_analysis_recommended']
DEFAULTS = {'document_id':'','title':'','publication_year':None,'abstract':'',
            'authors':'','source_journal':'','source_platforms':'', 'doi':'',
            'analysis_primary_p_layer':'unassigned',
            'disease_primary_code':'unassigned','am_process_primary_code':'T0',
            'material_primary_code':'M0','analysis_corpus_tier':'unknown',
            'normalized_work_type':'unknown','lexical_theme_id':'unassigned',
            'evidence_scope':'',
            'dataset_batch':'historical','imported_at':''}


def normalize_doi(value):
    text = str(value or '').strip().lower()
    text = re.sub(r'^https?://(?:dx\.)?doi\.org/|^doi:\s*','',text)
    return unquote(text).strip()


def bool_value(value, default=False):
    if value is None or str(value).strip().lower() in ('','nan','none','<na>'):
        return default
    text = str(value).strip().lower()
    if text in ('true','1','yes','是','y'): return True
    if text in ('false','0','no','否','n'): return False
    raise ValueError(f'无法识别的布尔值：{value}')


def normalize_records(frame):
    out = frame.drop(columns=['canonical_pdf'],errors='ignore').copy().reset_index(drop=True).fillna('')
    for col, default in DEFAULTS.items():
        if col not in out: out[col] = default
        if col != 'publication_year':
            out[col] = out[col].map(lambda v: json.dumps(v,ensure_ascii=False)
                                   if isinstance(v,(list,dict)) else str(v).strip())
            if default: out[col] = out[col].replace('',default)
    year = pd.to_numeric(out.publication_year,errors='coerce')
    out['publication_year'] = year.where(year.mod(1).eq(0)).astype('Int64')
    out['doi'] = out.doi.map(normalize_doi)
    for field in BOOL_FIELDS:
        if field not in out: out[field] = False
        out[field] = out[field].map(lambda v: bool_value(v,False))
    for i in out.index[out.document_id.eq('')]:
        identity = f'{out.at[i,"doi"]}|{out.at[i,"title"]}|{out.at[i,"publication_year"]}'
        out.at[i,'document_id'] = 'import_' + hashlib.sha256(identity.encode()).hexdigest()[:20]
    return out


def identity_keys(row):
    keys = [('id',row['document_id'])]
    if row['doi']: keys.append(('doi',row['doi']))
    title = unicodedata.normalize('NFKC',row['title']).casefold()
    title = re.sub(r'\s+',' ',title).strip()
    if title and pd.notna(row['publication_year']):
        keys.append(('title_year',title,int(row['publication_year'])))
    return keys


def deduplicate(frame):
    seen, keep, reject = set(), [], []
    for i, row in frame.iterrows():
        keys = identity_keys(row)
        if any(key in seen for key in keys): reject.append(i)
        else: keep.append(i)
        seen.update(keys)
    return frame.loc[keep].reset_index(drop=True), frame.loc[reject].reset_index(drop=True)


def filter_papers(frame, include_future=False, years=None, p_layers=None,
                  tiers=None, review='全部', query='', diseases=None,
                  processes=None, materials=None, work_types=None,
                  bibliometric_only=False):
    mask = frame.publication_year.notna()
    if not include_future: mask &= frame.publication_year.lt(2026)
    if years: mask &= frame.publication_year.between(*years)
    if bibliometric_only:
        mask &= frame.publication_year.lt(2026) | frame.bibliometric_recommended
    for col, values in [('analysis_primary_p_layer',p_layers),('analysis_corpus_tier',tiers),
                        ('disease_primary_code',diseases),('am_process_primary_code',processes),
                        ('material_primary_code',materials),('normalized_work_type',work_types)]:
        if values is not None: mask &= frame[col].isin(values)
    if review == '无需复核标记': mask &= ~frame.manual_review_required
    elif review == '待复核': mask &= frame.manual_review_required
    if query.strip():
        found = pd.Series(False,index=frame.index)
        for col in ['title','authors','doi','abstract','document_id','source_journal']:
            found |= frame[col].str.contains(query.strip(),case=False,regex=False,na=False)
        mask &= found
    return frame.loc[mask].copy()


def read_upload(raw, name):
    if len(raw)>25*1024*1024: raise ValueError('文件超过 25 MB。')
    suffix=Path(name).suffix.lower()
    if suffix=='.csv':
        try: return pd.read_csv(io.BytesIO(raw),encoding='utf-8-sig',keep_default_na=False)
        except UnicodeDecodeError:
            return pd.read_csv(io.BytesIO(raw),encoding='gb18030',keep_default_na=False)
    if suffix=='.xlsx':
        try:
            return pd.read_excel(io.BytesIO(raw),engine='openpyxl',keep_default_na=False)
        except (BadZipFile,InvalidFileException,KeyError,ValueError,SyntaxError) as error:
            raise ValueError('Excel 文件无法解析，请确认文件未损坏并使用有效的 XLSX 工作簿。') from error
    raise ValueError('仅支持 CSV 和 XLSX。')


def validate_additions(frame):
    errors=[]
    if frame.empty: return frame, ['文件没有论文记录。']
    for col in ['title','publication_year','analysis_primary_p_layer']:
        if col not in frame: errors.append(f'缺少必填列：{col}')
    if errors: return frame.iloc[:0],errors
    source=frame.copy().fillna('').reset_index(drop=True)
    current_year=datetime.now(ZoneInfo('Asia/Shanghai')).year
    for i,row in source.iterrows():
        prefix=f'第 {i+2} 行：'
        year=pd.to_numeric(row.publication_year,errors='coerce')
        if pd.isna(year) or year%1!=0 or not 2026<=year<=current_year:
            errors.append(prefix+f'年份必须为 2026–{current_year} 的整数。')
        if not str(row.title).strip(): errors.append(prefix+'标题不能为空。')
        for col, allowed in [('analysis_primary_p_layer',P),('disease_primary_code',D),
                             ('am_process_primary_code',T),('material_primary_code',M)]:
            value=str(row.get(col,'')).strip()
            if value and value not in allowed:
                errors.append(prefix+f'{col} 的分类代码无效：{value}')
        if not str(row.analysis_primary_p_layer).strip(): errors.append(prefix+'P 类别不能为空。')
        doi=normalize_doi(row.get('doi',''))
        if doi and not re.fullmatch(r'10\.\d{4,9}/\S+',doi): errors.append(prefix+'DOI 格式无效。')
        for col in BOOL_FIELDS:
            try: bool_value(row.get(col,''))
            except ValueError: errors.append(prefix+f'{col} 应填写 true/false。')
    if errors: return source.iloc[:0],errors
    out=normalize_records(source)
    out['dataset_batch']='addition'
    out['imported_at']=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    return out,errors


def load_data(root, include_future=False):
    root=Path(root)
    historical=normalize_records(pd.read_csv(root/'data/papers_pre2026.csv',keep_default_na=False))
    historical=filter_papers(historical)
    addition=root/'data/additions.jsonl'
    if include_future and addition.exists() and addition.stat().st_size:
        records=[json.loads(line) for line in addition.read_text(encoding='utf-8').splitlines() if line.strip()]
        future=normalize_records(pd.DataFrame(records))
        future=future.loc[future.publication_year.ge(2026)]
        historical=pd.concat([historical,future],ignore_index=True)
    return deduplicate(historical)[0]


_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


@contextmanager
def addition_lock(path):
    """Serialize the full transaction across sessions and local server processes."""
    key = str(path.resolve())
    with _LOCKS_GUARD:
        lock = _LOCKS.setdefault(key, threading.Lock())
    with lock, path.open('a+b') as handle:
        if path.stat().st_size == 0:
            handle.write(b'0')
            handle.flush()
        if os.name == 'nt':
            import msvcrt
            deadline = time.monotonic() + 30
            while True:
                try:
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise OSError('其他导入仍在进行，请稍后重试。')
                    time.sleep(.05)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt': msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else: fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def save_additions(root, frame):
    root=Path(root)
    valid,errors=validate_additions(frame)
    if errors: raise ValueError('\n'.join(errors))
    (root/'data').mkdir(parents=True, exist_ok=True)
    with addition_lock(root/'data/.additions.lock'):
        return _save_additions_locked(root, valid)


def _save_additions_locked(root, valid):
    existing=load_data(root,include_future=True)
    combined,rejected=deduplicate(pd.concat([existing,valid],ignore_index=True))
    additions=combined.loc[combined.publication_year.ge(2026)].copy()
    path=root/'data/additions.jsonl'
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(f'.additions-{uuid.uuid4().hex}.tmp')
    try:
        temporary.write_text(additions.to_json(orient='records',lines=True,force_ascii=False),encoding='utf-8')
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return len(combined)-len(existing),len(rejected)


def safe_csv(frame):
    out=frame.copy()
    def escaped(value):
        if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@')):
            return "'"+value
        return value
    for col in out.select_dtypes(include=['object','string']).columns:
        out[col]=out[col].map(escaped)
    return out.to_csv(index=False).encode('utf-8-sig')

"""Validate independent editorial patches and merge the direction report bodies."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dashboard.direction_reports import block_html


def _same_shape(a, b, path=''):
    if type(a) is not type(b):
        raise ValueError('Translation type mismatch: '+path)
    if isinstance(a, dict):
        if set(a) != set(b):
            raise ValueError('Translation keys mismatch: '+path)
        for key in a:
            _same_shape(a[key], b[key], path+'/'+key)
    elif isinstance(a, list):
        if len(a) != len(b):
            raise ValueError('Translation length mismatch: '+path)
        for index, (first, second) in enumerate(zip(a, b)):
            _same_shape(first, second, path+f'/{index}')
    elif isinstance(a, str):
        if Counter(re.findall(r'\[R\d+\]', a)) != Counter(re.findall(r'\[R\d+\]', b)):
            raise ValueError('Translation citation mismatch: '+path)
        if path.split('/')[-1] == 'type' and a != b:
            raise ValueError('Translation block mismatch: '+path)


def merge_rewrites(root: Path, patches: list[Path], audit_path: Path, baseline_dir: Path | None = None) -> dict:
    sources = {code: root/f'data/direction_reports/{code}.json' for code in ('zh', 'en', 'de')}
    originals = {code: json.loads(path.read_text(encoding='utf8')) for code, path in sources.items()}
    baseline = originals
    if baseline_dir is not None:
        baseline = {code: {} for code in sources}
        for rid in originals['zh']:
            packet = json.loads((baseline_dir/f'{rid}.json').read_text(encoding='utf8'))
            for code in sources:
                baseline[code][rid] = packet['reports'][code]
    merged = {}
    for patch in patches:
        records = json.loads(patch.read_text(encoding='utf8'))
        if merged.keys() & records.keys():
            raise ValueError('Direction appears in two patches')
        merged.update(records)
    if set(merged) != set(originals['zh']):
        raise ValueError('Patches must cover all 35 original directions')
    rows = []
    for rid, variants in merged.items():
        if set(variants) != set(sources):
            raise ValueError('Missing report language: '+rid)
        indices = (4, 5, 6) if rid.startswith('P7-') else (3, 4, 5)
        for code, patch in variants.items():
            if set(patch) != {'sections', 'references'}:
                raise ValueError('Unexpected patch fields: '+rid)
            if patch['references'] != variants['zh']['references']:
                raise ValueError('Reference translation mismatch: '+rid)
            _same_shape(variants['zh']['sections'], patch['sections'], rid+'/'+code)
            original = baseline[code][rid]
            if len(original['sections']) != len(patch['sections']):
                raise ValueError('Section count changed: '+rid)
            for index, section in enumerate(original['sections']):
                if index not in indices and patch['sections'][index] != section:
                    raise ValueError(f'Untargeted chapter changed: {rid}/{code}/{index}')
            refs = {ref['id']: ref for ref in patch['references']}
            if len(refs) != len(patch['references']):
                raise ValueError('Duplicate reference ID: '+rid)
            for section in patch['sections']:
                for block in section['blocks']:
                    block_html(block, refs)
                citations = set(re.findall(r'\[(R\d+)\]', json.dumps(section, ensure_ascii=False)))
                if citations - refs.keys():
                    raise ValueError('Unresolved citation: '+rid)
        original_refs = {ref['id'] for ref in baseline['zh'][rid]['references']}
        added = [ref for ref in variants['zh']['references'] if ref['id'] not in original_refs]
        rows.append({'id': rid, 'title': originals['zh'][rid]['title'],
                     'chapter_indices': list(indices), 'new_references': added,
                     'zh_chapter_characters': [len(json.dumps(variants['zh']['sections'][i], ensure_ascii=False)) for i in indices]})
    before = {code: hashlib.sha256(path.read_bytes()).hexdigest() for code, path in sources.items()}
    for code, path in sources.items():
        for rid, variants in merged.items():
            originals[code][rid].update(variants[code])
        path.write_text(json.dumps(originals[code], ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    audit = {'version': '2026-11-07', 'directions': len(rows), 'rewritten_chapters': len(rows)*3,
             'language_versions': len(rows)*3, 'source_before': before,
             'source_after': {code: hashlib.sha256(path.read_bytes()).hexdigest() for code, path in sources.items()},
             'reports': sorted(rows, key=lambda row: row['id'])}
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    return {key: value for key, value in audit.items() if key != 'reports'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--patch', type=Path, action='append', required=True)
    parser.add_argument('--audit', type=Path, required=True)
    parser.add_argument('--baseline-dir', type=Path, help='Original source packets for repeatable validation and reference counts')
    args = parser.parse_args()
    print(json.dumps(merge_rewrites(args.root, args.patch, args.audit, args.baseline_dir)))

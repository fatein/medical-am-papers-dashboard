"""Export complete direction reports, preserving the dashboard's citations and layout."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dashboard.direction_reports import (COLORS, CSS, UI, block_html, cited,
                                         diagram_html, load_reports, safe_url,
                                         source_date)


def report_html(report: dict, code: str) -> str:
    ui = UI[code]
    refs = {ref['id']: ref for ref in report['references']}
    title = report['id'] + ' · ' + report['title']
    body = [f'<!doctype html><html lang="{code}"><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,initial-scale=1">',
            f'<title>{html.escape(title)}</title>', CSS,
            '<style>body{margin:0;padding:32px 20px;background:#f7fafc}iframe{width:100%;height:830px;border:0}nav a{display:inline-block;margin:4px}</style>',
            f'<main class="dr" style="--accent:{COLORS[report["p"]]}">',
            f'<header class="dr-hero"><h1>{html.escape(title)}</h1>',
            f'<p>{html.escape(report["subtitle"])}</p><small>{ui["date"]}</small>',
            f'<aside><h3>{ui["finding"]}</h3><p>{cited(report["thesis"], refs)}</p></aside></header>',
            '<nav class="dr-toc">']
    for index, section in enumerate(report['sections']):
        body.append(f'<a href="#s{index}">{index+1}. {html.escape(section["title"])}</a>')
    body.append(f'<a href="#sources">{ui["sources"]}</a></nav>')
    body.append(f'<section><h2>{ui["questions"]}</h2>')
    for question in report['questions']:
        body.append(f'<div class="dr-question"><strong>{question["id"]} · {cited(question["question"], refs)}</strong><p>{cited(question["focus"], refs)}</p></div>')
    body.append('</section>')
    for index, section in enumerate(report['sections']):
        if index == 1:
            body.append(f'<section><h2>{html.escape(report["graph"]["title"])}</h2><p>{html.escape(report["graph"]["summary"])}</p>')
            body.append('<iframe title="'+html.escape(ui['graph'], quote=True)+'" srcdoc="'+html.escape(diagram_html(report, ui), quote=True)+'"></iframe></section>')
        body.append(f'<section id="s{index}"><h2>{index+1}. {html.escape(section["title"])}</h2>')
        body.extend(block_html(block, refs) for block in section['blocks'])
        body.append('</section>')
    body.append(f'<section id="sources"><h2>{ui["sources"]}</h2>')
    for ref in report['references']:
        if safe_url(ref['url']):
            body.append(f'<div class="dr-source"><b>{ref["id"]}</b> · <a href="{html.escape(ref["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(ref["title"])}</a><br><small>{html.escape(source_date(str(ref.get("year", "")), code))} · {html.escape(ref.get("source", ""))}</small></div>')
    return ''.join(body)+'</section></main></html>'


def export_direction_reports(root: Path, output: Path) -> dict:
    root, output = Path(root), Path(output)
    rows = []
    for code in ('zh', 'en', 'de'):
        folder = output/code
        folder.mkdir(parents=True, exist_ok=True)
        for rid, report in load_reports(str(root), code).items():
            content = report_html(report, code).encode('utf-8')
            path = folder/f'{rid}.html'
            path.write_bytes(content)
            rows.append({'id': rid, 'language': code, 'title': report['title'],
                         'path': f'{code}/{rid}.html',
                         'sha256': hashlib.sha256(content).hexdigest()})
    links = ''.join(f'<li><a href="{row["path"]}">{html.escape(row["id"]+" · "+row["language"]+" · "+row["title"])}</a></li>' for row in rows)
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>研究方向报告</title><style>body{max-width:1000px;margin:40px auto;font:16px/1.9 system-ui}a{color:#117f78}</style><h1>研究方向报告：论文—专利—企业</h1><ul>'+links+'</ul>', encoding='utf-8')
    manifest = {'version': '2026-11-07', 'direction_reports': len({row['id'] for row in rows}),
                'language_versions': len(rows), 'reports': rows}
    (output/'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return {key: value for key, value in manifest.items() if key != 'reports'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(export_direction_reports(args.root, args.output)))

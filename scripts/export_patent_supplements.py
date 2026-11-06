"""Export all scoped patent chapters and their coverage audit to a local archive."""
from __future__ import annotations
import argparse
import gzip
import hashlib
import html
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dashboard.bridge_data import load_bridge
from dashboard.patent_report_views import compose_patent_supplement,export_html,validate_editorial


def export_supplements(root,output):
    root=Path(root); output=Path(output)
    graph=load_bridge(root)
    editorial_path=root/'data/patent_report_editorial.json'
    editorial=json.loads(editorial_path.read_text(encoding='utf-8'))
    errors=validate_editorial(editorial,graph['reports'])
    if errors: raise ValueError('; '.join(errors))
    folder=output/'reports_patent_supplements'; folder.mkdir(parents=True,exist_ok=True)
    models=[]; rows=[]
    for ident,scope in sorted(graph['reports'].items()):
        variants=[compose_patent_supplement(graph,editorial,ident,code) for code in ('zh','en','de')]
        models.extend(variants)
        (folder/f'{ident}.html').write_text(export_html(variants),encoding='utf-8')
        rows.append({'id':ident,'scope':scope['scope'],'title':scope['title'],
                     **variants[0]['counts'],'representative_families':len(variants[0]['representatives']),
                     'path':f'reports_patent_supplements/{ident}.html'})
    payload=json.dumps({'schema_version':1,'method_version':graph['method_version'],'chapters':models},ensure_ascii=False,separators=(',',':')).encode('utf-8')
    (output/'report_supplements.json.gz').write_bytes(gzip.compress(payload,mtime=0))
    summary={'schema_version':1,'method_version':graph['method_version'],
             'source_manifest':json.loads((root/'data/patent_bridge_manifest.json').read_text(encoding='utf-8')),
             'editorial_sha256':hashlib.sha256(editorial_path.read_bytes()).hexdigest(),
             'reports':len(rows),'question_reports':sum(r['scope']=='question' for r in rows),
             'direction_reports':sum(r['scope']=='direction' for r in rows),
             'reports_with_topic_matches':sum(r['publications']>0 for r in rows),
             'reports_without_topic_matches':[r['id'] for r in rows if not r['publications']],
             'note':'Counts are per report; the same patent may appear in multiple scopes. Empty scopes retain tailored evidence-gap analysis.',
             'coverage':rows}
    (output/'coverage_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    links=''.join(f'<li><a href="{html.escape(r["path"],quote=True)}">{html.escape(r["id"]+" · "+r["title"])}</a> — {r["publications"]} 条主题匹配公开记录 / {r["families"]} 个已知同族组</li>' for r in rows)
    index='<!doctype html><meta charset="utf-8"><title>专利补充报告索引</title><style>body{font:16px/1.9 system-ui;max-width:1100px;margin:40px auto;padding:20px}a{color:#107e77}</style><h1>论文—专利—企业：报告补充索引</h1><p>113 份问题报告与 35 份方向报告。各页含中文、英文、德文；保留原始题名、申请人与来源链接。每份报告计数可能与其他报告重叠；无匹配不代表领域内没有专利。</p><ul>'+links+'</ul>'
    (output/'index.html').write_text(index,encoding='utf-8')
    return {k:v for k,v in summary.items() if k not in ('source_manifest','coverage')}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(export_supplements(args.root,args.output),ensure_ascii=True,indent=2))

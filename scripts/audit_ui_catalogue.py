"""List untranslated source spans in public presentation modules."""
import ast, json, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dashboard.i18n import tr,set_language,_SEGMENT
sources={}
for name in ['app.py','dashboard/views.py','dashboard/charts.py','dashboard/enterprise_views.py',
             'dashboard/cross_views.py','dashboard/report_views.py','dashboard/feedback_views.py']:
 for node in ast.walk(ast.parse((ROOT/name).read_text('utf8'))):
  if isinstance(node,ast.Constant) and isinstance(node.value,str):
   for phrase in _SEGMENT.findall(node.value):
    sources.setdefault(phrase,[]).append(f'{name}:{node.lineno}')
rows=[]
for phrase,locations in sources.items():
 en=tr(phrase,code='en',root=ROOT);de=tr(phrase,code='de',root=ROOT)
 if re.search('[\u3400-\u9fff]',en+de):rows.append({'source':phrase,'en':en,'de':de,'locations':locations})
out=ROOT/'outputs/full_i18n_review_20261103/ui_missing.json'
out.write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf8')
for r in rows:print(r['source'],r['locations'][0])

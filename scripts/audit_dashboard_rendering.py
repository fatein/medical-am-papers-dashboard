"""Capture real rendered presentation strings without changing source records."""
import ast,csv,json,re,sys
from pathlib import Path
from streamlit.testing.v1 import AppTest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dashboard.i18n import set_language,tr,protect_names
from dashboard.report_views import render_cited_markdown
OUT=ROOT/'outputs/full_i18n_review_20261103';OUT.mkdir(parents=True,exist_ok=True)
HAN=re.compile('[\u3400-\u9fff]')
# Literal company/product names and Chinese registration prefixes are intentional.
names={'先临齿科','上海三友医疗','三迭纪','国械注准','成都口口齿科',
       '泰利斯数智制造解决方案','易齿盟','云南家红','家红','嘉思特','百齿泰','迅实科技'};originals=set()
for filename,field in [('enterprises.csv','name'),('papers_pre2026.csv','title')]:
 with (ROOT/'data'/filename).open(encoding='utf-8-sig',newline='') as f:
  for row in csv.DictReader(f):
   if HAN.search(row.get(field,'')):names.add(row[field])
   for k,v in row.items():
    if v and ('evidence' in k or k=='abstract') and len(v)>25:originals.add(v)
cross=json.loads((ROOT/'data/cross_analysis.json').read_text('utf8'))
for r in cross['papers']:
 if HAN.search(r['title']):names.add(r['title'])
for filename in ['additions.jsonl','enterprise_observations.jsonl','enterprise_events.jsonl']:
 for line in (ROOT/'data'/filename).read_text('utf8').splitlines():
  if not line.strip():continue
  r=json.loads(line)
  if filename=='additions.jsonl' and HAN.search(r.get('title','')):names.add(r['title'])
  if 'company' in r and HAN.search(r['company']):names.add(r['company'])
  if filename=='additions.jsonl':
   originals.update(v for k,v in r.items() if isinstance(v,str) and len(v)>25 and ('evidence' in k or k=='abstract'))
protect_names(names)
allowed=re.compile('|'.join(re.escape(x) for x in sorted(names|originals,key=len,reverse=True))) if names|originals else None
def remaining(s):return HAN.search(allowed.sub('',s) if allowed else s)
def strings(v,path=''):
 if isinstance(v,str):yield path,v
 elif isinstance(v,dict):
  for k,x in v.items():yield from strings(x,path+'/'+str(k))
 elif isinstance(v,(list,tuple)):
  for i,x in enumerate(v):yield from strings(x,path+'/'+str(i))
def snapshot(at,page,code):
 values=[];errors=[e.message for e in at.exception]+[e.value for e in at.error]
 for typ in ['markdown','caption','title','header','subheader','info','warning','success','text','button','checkbox','selectbox','multiselect','radio','slider','number_input','text_input','text_area','expander','metric','tabs','download_button','link_button','file_uploader']:
  for i,e in enumerate(at.get(typ)):
   for key in ['label','value','help','placeholder','options','body']:
    if key=='value' and typ in ['selectbox','multiselect','radio']:continue
    if typ=='selectbox' and e.key=='language' and key=='options':continue
    if typ=='text':continue  # Original paper/source excerpts and visitor feedback.
    try:v=getattr(e,key)
    except (AttributeError,KeyError):continue
    for sub,s in strings(v):
     if s:values.append({'kind':typ,'path':str(i)+'/'+key+sub,'text':s})
 for i,e in enumerate(at.dataframe):
  for c in e.value.columns:
   values.append({'kind':'dataframe','path':str(i)+'/column','text':str(c)})
  for col in e.value.select_dtypes(include=['object','string']).columns:
   for v in e.value[col].dropna().astype(str).unique():values.append({'kind':'dataframe','path':str(i)+'/'+str(col),'text':v})
 for i,e in enumerate(at.get('plotly_chart')):
  spec=json.loads(e.proto.spec)
  for path,s in strings(spec):
   if HAN.search(s) and not path.endswith('/legendgroup'):values.append({'kind':'plotly_chart','path':str(i)+path,'text':s})
 for i,e in enumerate(at.get('html')):
  body=getattr(e.proto,'body','')
  if body:values.append({'kind':'html','path':str(i),'text':body})
 leaks=[r for r in values if remaining(r['text'])]
 return {'language':code,'page':page,'errors':errors,'leaks':leaks,'strings':values}
pages=['论文总览','研究结构与趋势','论文检索','学术与企业联系','企业格局','技术路线图','企业检索','反馈汇总']
results=[]
for code in ('en','de'):
 set_language(code,ROOT)
 at=AppTest.from_file(str(ROOT/'public_app.py'),default_timeout=60)
 at.query_params['lang']=code;at.run()
 for page in pages:
  if at.radio(key=f'page__{code}').value!=page:at.radio(key=f'page__{code}').set_value(page).run()
  item=snapshot(at,page,code);results.append(item)
  print(code,page,'leaks',len(item['leaks']),'errors',len(item['errors']),flush=True)
  (OUT/(sys.argv[1] if len(sys.argv)>1 else 'rendered_before.json')).write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf8')
 # Each trend dimension, cross relation and paper/evidence path needs coverage.
 at.radio(key=f'page__{code}').set_value('研究结构与趋势').run()
 from dashboard.labels import DIMENSIONS
 for dimension in DIMENSIONS:
  at.selectbox(key=f'dimension__{code}').set_value(dimension).run()
  item=snapshot(at,'趋势/'+dimension,code);results.append(item)
  print(code,'dimension',dimension,'leaks',len(item['leaks']),flush=True)
 at.selectbox(key=f'relation__{code}').set_value('医疗对象 × 疾病／应用').run()
 results.append(snapshot(at,'交叉/医疗对象×疾病',code))
 report_data=json.loads((ROOT/'data/question_reports.json').read_text('utf8'))['reports']
 report_leaks=[]
 set_language(code,ROOT)
 for qid,r in report_data.items():
  for s in r['sections']:
   rendered=render_cited_markdown(s,r['references'])
   if remaining(rendered):report_leaks.append({'question':qid,'section':s['id'],'text':rendered})
 (OUT/f'question_report_leaks_{code}.json').write_text(json.dumps(report_leaks,ensure_ascii=False,indent=2),'utf8')
 print(code,'question report sections leaking',len(report_leaks),flush=True)
out=OUT/(sys.argv[1] if len(sys.argv)>1 else 'rendered_before.json')
out.write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf8')
print('Saved',out,flush=True)

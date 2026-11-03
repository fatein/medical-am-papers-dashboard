import json,re,sys
from pathlib import Path
from collections import Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dashboard.direction_reports import load_reports,cited,diagram_html,block_html,UI,direction_id,source_date
from dashboard import direction_reports

def test_original_coverage_and_links():
 reports=load_reports(str(ROOT))
 assert len(reports)==35
 assert sum(len(r['questions']) for r in reports.values())==113
 assert sum(len(r['graph']['nodes']) for r in reports.values())==318
 for rid,r in reports.items():
  assert direction_id(ROOT,r['p'],r['title'])==rid
  refs={v['id']:v for v in r['references']}
  rendered=''.join(block_html(b,refs) for s in r['sections'] for b in s['blocks'])+diagram_html(r,UI['zh'])
  for n in r['graph']['nodes']:
   assert n['id'] in rendered
   for ref in n['refs']:assert refs[ref]['url'].replace('&','&amp;') in rendered
  for ref in refs:assert f'[{ref}]' in rendered

def test_citations_and_html_safety():
 refs={'R01':{'url':'https://example.org/paper?a=1&b=2'}}
 s=cited('<script>alert(1)</script>[R01]',refs)
 assert '<script>' not in s and 'noopener noreferrer' in s and '&amp;b=2' in s

def test_translations_complete_and_structurally_equal():
 zh=load_reports(str(ROOT))
 def walk(a,b,path=''):
  if isinstance(a,dict):
   assert set(a)==set(b),path
   for k in a:
    if k=='references':assert a[k]==b[k],path
    else:walk(a[k],b[k],path+'/'+k)
  elif isinstance(a,list):
   assert len(a)==len(b),path
   for i,(x,y) in enumerate(zip(a,b)):walk(x,y,path+f'/{i}')
  elif isinstance(a,str):
   assert Counter(re.findall(r'\[R\d+\]',a))==Counter(re.findall(r'\[R\d+\]',b)),path
   if path.split('/')[-1] in {'id','p','from','to','kind','type'}:assert a==b,path
   assert 'ZXQ' not in b and '▁' not in b,path
   if re.search('[\u3400-\u9fff]',a):
    assert not re.search('[\u3400-\u9fff]',b),path
 for lang in ('en','de'):
  translated=load_reports(str(ROOT),lang);assert set(translated)==set(zh)
  for rid in zh:walk(zh[rid],translated[rid],rid)

def test_reference_date_labels():
 for code in ('en','de'):
  for r in load_reports(str(ROOT)).values():
   for ref in r['references']:assert not re.search('[\u3400-\u9fff]',source_date(str(ref.get('year','')),code))

def test_return_restores_question_and_ignores_stale_context(monkeypatch):
 class State:
  session_state={'cross_p':'全部','cross_direction':'P1 · 个体化植入物','cross_question':'P1-004','cross_paper_page_P1-004':3}
  query_params={}
 fake=State()
 monkeypatch.setattr(direction_reports,'st',fake)
 direction_reports.open_direction_report('P1-02')
 fake.session_state.pop('cross_question')
 direction_reports.return_to_direction(ROOT,'P1-02')
 assert fake.session_state['cross_question']=='P1-004'
 assert fake.session_state['cross_paper_page_P1-004']==3
 assert fake.session_state['cross_p']=='全部'
 direction_reports.return_to_direction(ROOT,'P2-01')
 assert fake.session_state['cross_p']=='P2'
 assert 'cross_question' not in fake.session_state

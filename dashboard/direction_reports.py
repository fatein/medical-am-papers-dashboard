"""Direction-level reports, fully pretranslated with source-preserving diagrams."""
from __future__ import annotations
import html,json,re
from pathlib import Path
from functools import lru_cache
from urllib.parse import urlparse
import streamlit as st
import streamlit.components.v1 as components
from dashboard.i18n import language,preserve_original_text

UI={
 'zh':{'read':'查看报告 →','back':'← 返回研究方向','contents':'报告目录','graph':'详细研究脉络图','sources':'论文与网页来源','questions':'研究问题','finding':'核心判断','zoom':'缩放','reset':'适应宽度','feedback':'虚线：反馈任务','date':'更新于 2026-11-03'},
 'en':{'read':'Read report →','back':'← Back to research direction','contents':'Contents','graph':'Detailed research pathway','sources':'Papers and web sources','questions':'Research questions','finding':'Core finding','zoom':'Zoom','reset':'Fit to width','feedback':'Dashed lines: feedback tasks','date':'Updated 2026-11-03'},
 'de':{'read':'Bericht lesen →','back':'← Zurück zur Forschungsrichtung','contents':'Inhalt','graph':'Detaillierter Forschungsverlauf','sources':'Publikationen und Webquellen','questions':'Forschungsfragen','finding':'Kernaussage','zoom':'Zoom','reset':'An Breite anpassen','feedback':'Gestrichelte Linien: Rückkopplungsaufgaben','date':'Aktualisiert am 03.11.2026'},
}
COLORS={'P1':'#386c9c','P2':'#11857f','P3':'#9d692d','P4':'#7760a3','P5':'#a44f68','P6':'#477653','P7':'#307d91'}

@lru_cache(maxsize=9)
def load_reports(root:str,code:str='zh')->dict:
 return json.loads((Path(root)/'data/direction_reports'/f'{code}.json').read_text(encoding='utf8'))

def direction_id(root:Path,p:str,title:str)->str|None:
 return next((k for k,v in load_reports(str(root)).items() if v['p']==p and v['title']==title),None)

def open_direction_report(rid:str)->None:
 keys=('cross_p','cross_direction','cross_question')
 saved={k:st.session_state[k] for k in keys if k in st.session_state}
 qid=saved.get('cross_question')
 if qid and f'cross_paper_page_{qid}' in st.session_state:
  saved[f'cross_paper_page_{qid}']=st.session_state[f'cross_paper_page_{qid}']
 st.session_state['direction_report_return']={'rid':rid,**saved}
 st.session_state['direction_report_scroll_to_top']=True
 st.query_params.pop('question',None)
 st.query_params['view']='direction-report';st.query_params['direction']=rid
 st.query_params['lang']=language()
 st.session_state['page']='学术与企业联系'

def return_to_direction(root:Path,rid:str)->None:
 for k in ('view','direction','question'):st.query_params.pop(k,None)
 original=load_reports(str(root))[rid]
 st.session_state['page']='学术与企业联系'
 saved=st.session_state.get('direction_report_return',{})
 if saved.get('rid')!=rid:saved={}
 st.session_state['cross_p']=saved.get('cross_p',original['p'])
 st.session_state['cross_direction']=f"{original['p']} · {original['title']}"
 qid=saved.get('cross_question')
 if qid in {q['id'] for q in original['questions']}:
  st.session_state['cross_question']=qid
  page_key=f'cross_paper_page_{qid}'
  if page_key in saved:st.session_state[page_key]=saved[page_key]
 else:st.session_state.pop('cross_question',None)
 st.session_state['cross_scroll_to_direction']=True

def safe_url(url:str)->bool:
 p=urlparse(url);return p.scheme in ('http','https') and bool(p.netloc) and not p.username

def source_date(value:str,code:str)->str:
 if code=='zh':return value
 words={'en':{'截至':'As of ','的现行指南':' current guidance','现行产品文档':'Current product documentation','现行产品资料':'Current product information','现行技术资料':'Current technical information','现行服务资料':'Current service information','现行材料资料':'Current material information','现行项目资料':'Current project information','年现行资料':' current information','在线':' online','卷期':' print issue','项目':' project','更新':' updated','访问':' accessed','文件':' document','状态':' status','年':'-','月':''},'de':{'截至':'Stand ','的现行指南':' aktuelle Leitlinie','现行产品文档':'Aktuelle Produktdokumentation','现行产品资料':'Aktuelle Produktinformationen','现行技术资料':'Aktuelle technische Informationen','现行服务资料':'Aktuelle Dienstleistungsinformationen','现行材料资料':'Aktuelle Materialinformationen','现行项目资料':'Aktuelle Projektinformationen','年现行资料':' aktuelle Informationen','在线':' online','卷期':' Druckausgabe','项目':' Projekt','更新':' aktualisiert','访问':' abgerufen','文件':' Dokument','状态':' Stand','年':'-','月':''}}
 for term in sorted(words[code],key=len,reverse=True):value=value.replace(term,words[code][term])
 return value.replace('／',' / ').replace('；','; ').replace('（',' (').replace('）',')')

def cited(text:str,refs:dict)->str:
 value=html.escape(str(text)).replace('\n','<br>')
 def sub(m):
  r=refs.get(m[1]);return f'<a class="citation" href="{html.escape(r["url"],quote=True)}" target="_blank" rel="noopener noreferrer">[{m[1]}]</a>' if r and safe_url(r['url']) else m[0]
 return re.sub(r'\[(R\d+)\]',sub,value)

def block_html(b:dict,refs:dict)->str:
 typ=b['type']
 if typ=='p':return '<p>'+cited(b['text'],refs)+'</p>'
 if typ=='h3':return '<h3>'+cited(b['text'],refs)+'</h3>'
 if typ=='bullets':return '<ul>'+''.join('<li>'+cited(t,refs)+'</li>' for t in b['items'])+'</ul>'
 if typ=='callout':return '<aside><h3>'+cited(b.get('title',''),refs)+'</h3><p>'+cited(b['text'],refs)+'</p></aside>'
 if typ=='table':return '<div class="dr-table"><table><thead><tr>'+''.join('<th>'+cited(t,refs)+'</th>' for t in b['headers'])+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+cited(t,refs)+'</td>' for t in row)+'</tr>' for row in b['rows'])+'</tbody></table></div>'
 raise ValueError('Unknown report block '+typ)

CSS='''<style>
.dr{max-width:1120px;margin:0 auto;color:#19374b}.dr p,.dr li{font-size:16px;line-height:1.95;margin:0 0 18px}.dr h2{font-size:26px;margin:36px 0 18px;line-height:1.5}.dr h3{font-size:19px;line-height:1.65;margin:28px 0 12px}.dr .dr-hero{border:1px solid #d8e8e9;background:linear-gradient(120deg,#e8f4f0,#edf2fb);border-radius:18px;padding:32px;margin-bottom:28px}.dr .dr-hero h1{font-size:36px;line-height:1.35;margin:12px 0}.dr .dr-kicker{font-size:12px;letter-spacing:.08em;color:#137f75}.dr .dr-sub{font-size:19px;color:#577184}.dr .dr-date{font-size:12px;color:#718596}.dr aside{border-left:4px solid var(--accent);background:#eef5f7;padding:18px 24px;border-radius:0 10px 10px 0;margin:20px 0}.dr aside h3{margin:0 0 8px}.dr aside p{margin:0}.dr a{color:#117f78;text-underline-offset:3px}.dr .citation{font-size:.82em;white-space:nowrap}.dr .dr-toc{display:flex;flex-wrap:wrap;gap:9px;margin:16px 0 28px}.dr .dr-toc a{padding:9px 13px;background:white;border:1px solid #dce5ec;border-radius:8px;text-decoration:none;font-size:13px}.dr section{scroll-margin-top:90px;border-top:1px solid #dce6ed;padding-top:6px}.dr .dr-table{overflow-x:auto}.dr table{border-collapse:collapse;width:100%;font-size:14px;margin:18px 0 25px}.dr th{background:var(--accent);color:white;text-align:left}.dr td,.dr th{padding:12px;vertical-align:top;border:1px solid #dce6ed;min-width:140px}.dr tbody tr:nth-child(even){background:#f1f6f8}.dr .dr-question{padding:12px 0;border-bottom:1px solid #e4ebef}.dr .dr-question strong{font-size:17px}.dr .dr-question p{font-size:14px;color:#61788a;margin:6px 0}.dr .dr-source{padding:15px 0;border-bottom:1px solid #e1e9ed;line-height:1.7}.dr .dr-source small{color:#738799}
@media(max-width:700px){.dr .dr-hero{padding:22px}.dr .dr-hero h1{font-size:28px}.dr p,.dr li{font-size:15px}.dr h2{font-size:23px}}
</style>'''

def diagram_html(report:dict,ui:dict)->str:
 g=report['graph'];refs={r['id']:r for r in report['references']};color=COLORS[report['p']]
 bw,bh,step=430,190,270
 boxes={n['id']:(80+n['lane']*510,65+n['stage']*step) for n in g['nodes']}
 paths=[];labels=[]
 for i,e in enumerate(g['edges']):
  x,y=boxes[e['from']];xx,yy=boxes[e['to']];sx=x+bw/2;tx=xx+bw/2
  feed=e.get('kind')=='feedback';co='#b77c41' if feed else color
  if feed:
   gutter=30 if i%2 else 1560;start=x if i%2 else x+bw;end=xx if i%2 else xx+bw
   points=[(start,y+bh/2),(gutter,y+bh/2),(gutter,yy+bh/2),(end,yy+bh/2)]
  elif y==yy:
   level=y-35;points=[(sx,y),(sx,level),(tx,level),(tx,yy)];labels.append((e['label'],(sx+tx)/2,level-5,co))
  elif yy-y>step:
   gutter=x+bw+25 if x<1100 else x-25
   points=[(sx,y+bh),(sx,y+bh+22),(gutter,y+bh+22),(gutter,yy-22),(tx,yy-22),(tx,yy)]
   labels.append((e['label'],(sx+gutter)/2,y+bh+18,co))
  else:
   mid=(y+bh+yy)/2;points=[(sx,y+bh),(sx,mid),(tx,mid),(tx,yy)];labels.append((e['label'],(sx+tx)/2,mid-5,co))
  poly=' '.join(f'{a},{b}' for a,b in points)
  paths.append(f'<polyline points="{poly}" fill="none" stroke="{co}" stroke-width="2" {"stroke-dasharray=\"7 5\"" if feed else ""} marker-end="url(#{"fb" if feed else "ar"})"/>')
 nodes=[]
 for n in g['nodes']:
  x,y=boxes[n['id']];rs=' '.join(f'[{v}]' for v in n['refs'])
  nodes.append(f'<foreignObject x="{x}" y="{y}" width="{bw}" height="{bh}"><div xmlns="http://www.w3.org/1999/xhtml" class="node"><header style="background:{color}"><b>{html.escape(n["id"]+" · "+n["title"])}</b><small>{html.escape(str(n["time"]))}</small></header><div class="node-body"><strong>{cited(n["question"],refs)}</strong><p>{cited(n["evidence"]+" "+rs,refs)}</p></div></div></foreignObject>')
 edge_labels=[]
 for t,x,y,co in labels:
  edge_labels.append(f'<foreignObject x="{x-150}" y="{y-25}" width="300" height="55"><div xmlns="http://www.w3.org/1999/xhtml" class="edge" style="color:{co}"><span>{html.escape(t)}</span></div></foreignObject>')
 feeds='; '.join(e['from']+' → '+e['to']+': '+e['label'] for e in g['edges'] if e.get('kind')=='feedback')
 svg=f'<svg xmlns="http://www.w3.org/2000/svg" width="1600" height="1390" viewBox="0 0 1600 1390"><defs><marker id="ar" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="{color}"/></marker><marker id="fb" markerWidth="9" markerHeight="9" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#b77c41"/></marker></defs>'+''.join(paths+nodes+edge_labels)+'</svg>'
 return '<!doctype html><meta charset="utf-8"><style>body{margin:0;color:#19374b;font-family:Arial,"Microsoft YaHei",sans-serif}.toolbar{display:flex;gap:8px;align-items:center;padding:10px;position:sticky;top:0;background:#f3f7fa;z-index:2}button{border:1px solid #ccdce5;background:white;padding:7px 13px;border-radius:6px;cursor:pointer}#viewport{overflow:auto;height:690px;border:1px solid #dce7ed;border-radius:10px;background:#fff}#canvas{transform-origin:top left}.node{height:188px;box-sizing:border-box;border:1px solid #cbdde6;border-radius:9px;background:#fff;overflow:auto}header{color:white;padding:10px 13px;font-size:15px;line-height:1.4}header small{display:block;font-size:12px;margin-top:3px}.node-body{padding:12px 14px;font-size:14px;line-height:1.6}.node-body strong{font-weight:500}.node-body p{margin:8px 0;color:#607b8e;font-size:13px}a{color:#087b77}.edge{text-align:center;font-size:12px;line-height:1.4}.edge span{background:white;padding:1px 4px}footer{font-size:12px;line-height:1.7;padding:10px;color:#8e673b}</style><div class="toolbar"><button onclick="scaleBy(1.25)">＋</button><button onclick="scaleBy(.8)">−</button><button onclick="fit()">'+html.escape(ui['reset'])+'</button></div><div id="viewport"><div id="canvas">'+svg+'</div></div><footer>'+html.escape(ui['feedback']+' · '+feeds)+'</footer><script>let scale=1;function apply(){document.querySelector("svg").style.width=1600*scale+"px";document.querySelector("svg").style.height=1390*scale+"px"}function scaleBy(v){scale=Math.max(.35,Math.min(2.5,scale*v));apply()}function fit(){scale=document.getElementById("viewport").clientWidth/1600;apply()}fit();</script>'

def direction_report_page(root:Path,rid:str)->None:
 code=language();ui=UI[code];reports=load_reports(str(root),code)
 if rid not in reports:
  st.info({'zh':'未找到对应报告。','en':'Report not found.','de':'Bericht nicht gefunden.'}[code]);return
 r=reports[rid];refs={v['id']:v for v in r['references']};accent=COLORS[r['p']]
 with preserve_original_text():
  st.button(ui['back'],on_click=return_to_direction,args=(root,rid),key='direction_report_back')
  hero=f'<div class="dr" style="--accent:{accent}"><div class="dr-hero"><div class="dr-kicker">{r["p"]} / {rid} · AM HEALTHCARE</div><h1>{html.escape(r["title"])}</h1><p class="dr-sub">{html.escape(r["subtitle"])}</p><div class="dr-date">{ui["date"]}</div><aside><h3>{ui["finding"]}</h3><p>{cited(r["thesis"],refs)}</p></aside></div>'
  toc=[('questions',ui['questions']),('pathway',ui['graph'])]+[(f's{i}',s['title']) for i,s in enumerate(r['sections'])]+[('sources',ui['sources'])]
  hero+='<nav class="dr-toc">'+''.join(f'<a href="#dr-{k}" target="_self">{html.escape(t)}</a>' for k,t in toc)+'</nav>'
  hero+=f'<section id="dr-questions"><h2>{ui["questions"]}</h2>'+''.join(f'<div class="dr-question"><strong>{q["id"]} · {cited(q["question"],refs)}</strong><p>{cited(q["focus"],refs)}</p></div>' for q in r['questions'])+'</section></div>'
  st.html(CSS+hero)
  for i,s in enumerate(r['sections']):
   if i==1:
    st.html(f'<div class="dr"><section id="dr-pathway"><h2>{html.escape(r["graph"]["title"])}</h2><p>{html.escape(r["graph"]["summary"])}</p></section></div>')
    components.html(diagram_html(r,ui),height=820,scrolling=True)
   st.html(f'<div class="dr" style="--accent:{accent}"><section id="dr-s{i}"><h2>{i+1}. {html.escape(s["title"])}</h2>'+''.join(block_html(b,refs) for b in s['blocks'])+'</section></div>')
  source_html=f'<div class="dr"><section id="dr-sources"><h2>{ui["sources"]}</h2>'
  for ref in r['references']:
   if safe_url(ref['url']):source_html+=f'<div class="dr-source"><b>{ref["id"]}</b> · <a href="{html.escape(ref["url"],quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(ref["title"])}</a><br><small>{html.escape(source_date(str(ref.get("year","")),code))} · {html.escape(ref.get("source",""))}</small></div>'
  st.html(source_html+'</section></div>')
  if st.session_state.pop('direction_report_scroll_to_top',False):
   st.html('''<script>requestAnimationFrame(() => {
    const main=document.querySelector('[data-testid="stMain"]');
    if(main) main.scrollTo({top:0,behavior:'instant'});
    window.scrollTo({top:0,behavior:'instant'});
   });</script>''',unsafe_allow_javascript=True)

"""Interactive topic-mediated paper, patent and company network."""
from __future__ import annotations
from collections import Counter
from collections.abc import Mapping
import hashlib
import html
import json
import math
import plotly.graph_objects as go

KINDS=('papers','patents','companies')
COLORS={'papers':'#4F79BC','patents':'#139A89','companies':'#AD6CA6','topics':'#D0A050'}
COPY={
 'papers':('论文','Papers','Publikationen'), 'patents':('专利','Patents','Patente'),
 'companies':('企业','Companies','Unternehmen'), 'topics':('技术主题','Technical topics','Technische Themen'),
 'membership':('主题关联','Topic relation','Themenbezug'),
 'applicant':('申请人关联','Applicant relation','Anmelderbezug'),
 'size':('图谱规模','Network size','Netzwerkgröße'),
 'nodes':('节点','Nodes','Knoten'), 'edges':('关系','Relations','Beziehungen'),
 'details':('节点详情','Node details','Knotendetails'),
 'choose':('选择节点','Select a node','Knoten auswählen'),
 'open':('查看原文 ↗','View original ↗','Original ansehen ↗'),
 'website':('企业网站 ↗','Company website ↗','Unternehmenswebsite ↗'),
 'focus':('聚焦此主题','Focus this topic','Dieses Thema fokussieren'),
 'empty':('暂无关联记录','No related records','Keine verknüpften Einträge'),
 'reset':('重置图谱','Reset graph','Graph zurücksetzen'),
 'neighbors':('关联节点','Connected nodes','Verbundene Knoten'),
 'applicants':('申请人','Applicants','Anmelder'),
 'year':('年份','Year','Jahr'), 'family':('同族编号','Family ID','Familien-ID'),
}

def label(key,code):
    return COPY[key][{'zh':0,'en':1,'de':2}[code]]

def build_network(graph,selection,max_nodes=90):
    from dashboard.bridge_data import select_bridge
    selected=select_bridge(graph,**selection)
    max_nodes=max(6,int(max_nodes))
    topics={r['id']:r for r in graph['topics']}
    if selection.get('application'):
        topics={ident:row for ident,row in topics.items() if selection['application'] in row.get('applications',[])}
    if selection.get('topic'):
        topics={ident:row for ident,row in topics.items() if ident==selection['topic']}
    if selection.get('scope_id'):
        scoped=set(graph.get('reports',{}).get(selection['scope_id'],{}).get('topic_ids',[]))
        topics={ident:row for ident,row in topics.items() if ident in scoped}
    rows={kind:[r for r in selected[kind] if r.get('association_status')!='excluded_nonmedical_context'] for kind in KINDS}
    available={kind:{r['id'] for r in rows[kind]} for kind in KINDS}
    named=[e for e in graph.get('company_patent_links',[]) if e['company_id'] in available['companies'] and e['patent_id'] in available['patents']]
    degree=Counter(v for e in named for v in ('patents:'+e['patent_id'],'companies:'+e['company_id']))
    counts={topic:{kind:sum(topic in r['topics'] for r in rows[kind]) for kind in KINDS} for topic in topics}
    ranked=sorted(topics,key=lambda t:(-sum(bool(n) for n in counts[t].values()),-sum(math.log1p(n) for n in counts[t].values()),t))
    chosen_topics=[t for t in ranked if any(counts[t].values())][:min(8,max_nodes//6)]
    chosen_set=set(chosen_topics)
    def rank(kind,row):
        return (-degree[kind+':'+row['id']],-len(chosen_set.intersection(row['topics'])),-(row.get('year') or 0),row['id'])
    candidates={kind:sorted([r for r in rows[kind] if chosen_set.intersection(r['topics']) or degree[kind+':'+r['id']]],key=lambda r:rank(kind,r)) for kind in KINDS}
    limit=(max_nodes-len(chosen_topics))//3
    picks={kind:[] for kind in KINDS}; ids={kind:set() for kind in KINDS}
    def add(kind,row,quota):
        if row['id'] not in ids[kind] and len(picks[kind])<quota:
            picks[kind].append(row); ids[kind].add(row['id'])
    for kind in KINDS:
        for topic in chosen_topics:
            first=next((r for r in candidates[kind] if topic in r['topics']),None)
            if first: add(kind,first,limit)
        for row in candidates[kind]: add(kind,row,limit)
    remaining=max_nodes-len(chosen_topics)-sum(map(len,picks.values()))
    for kind in KINDS:
        for row in candidates[kind]:
            if remaining and row['id'] not in ids[kind]:
                add(kind,row,max_nodes); remaining-=1
    nodes=[dict(key=kind+':'+r['id'],kind=kind,id=r['id'],record=r) for kind in KINDS for r in picks[kind]]
    used={t for node in nodes for t in node['record']['topics'] if t in chosen_set}
    nodes.extend(dict(key='topics:'+t,kind='topics',id=t,record=topics[t]) for t in chosen_topics if t in used)
    keys={n['key'] for n in nodes}; edges=[]
    for node in nodes:
        if node['kind']=='topics': continue
        edges.extend(dict(source=node['key'],target='topics:'+t,kind='topic_membership') for t in node['record']['topics'] if 'topics:'+t in keys)
    edges.extend(dict(source='patents:'+e['patent_id'],target='companies:'+e['company_id'],kind='applicant_name_match') for e in named if 'patents:'+e['patent_id'] in keys and 'companies:'+e['company_id'] in keys)
    unique={(e['source'],e['target'],e['kind']):e for e in edges}
    return {'nodes':nodes,'edges':list(unique.values())}

def selection_node(event,network):
    if not isinstance(event,Mapping): return None
    lookup={n['key']:n for n in network['nodes']}
    points=event.get('selection',{}).get('points',[])
    for point in reversed(points):
        data=point.get('customdata')
        key=data[0] if isinstance(data,(list,tuple)) and data else point.get('id')
        if isinstance(key,str) and key in lookup: return lookup[key]
    return None

def node_title(node,code):
    row=node['record']
    return row.get('labels',{}).get(code) or row.get('title') or row.get('name') or row['id']

def _positions(network):
    topics=[n['id'] for n in network['nodes'] if n['kind']=='topics']
    ty={t:1.0-i*2/max(1,len(topics)-1) for i,t in enumerate(topics)}
    if len(topics)==1: ty[topics[0]]=0.0
    positions={}; xs={'papers':0.0,'topics':1.15,'patents':2.3,'companies':3.45}
    for node in network['nodes']:
        if node['kind']=='topics': positions[node['key']]=(xs['topics'],ty[node['id']])
    for kind in KINDS:
        nodes=[n for n in network['nodes'] if n['kind']==kind]
        order={topic:i for i,topic in enumerate(topics)}
        nodes.sort(key=lambda n:(min((order[t] for t in n['record']['topics'] if t in order),default=len(topics)),n['id']))
        for i,node in enumerate(nodes):
            y=0.0 if len(nodes)==1 else 1.10-i*2.20/(len(nodes)-1)
            positions[node['key']]=(xs[kind],y)
    return positions

def network_figure(network,code='zh'):
    positions=_positions(network); fig=go.Figure()
    for relation,color,width in [('topic_membership','rgba(137,158,178,.24)',1),('applicant_name_match','rgba(163,91,155,.65)',1.8)]:
        x=[]; y=[]
        for edge in network['edges']:
            if edge['kind']!=relation: continue
            a,b=positions[edge['source']],positions[edge['target']]
            # Curved edges separate the dense topic fans and explicit applicant links.
            for i in range(13):
                t=i/12; bend=.10*math.sin(math.pi*t)
                x.append(a[0]+(b[0]-a[0])*t); y.append(a[1]+(b[1]-a[1])*t+bend)
            x.append(None); y.append(None)
        fig.add_trace(go.Scatter(x=x,y=y,mode='lines',line=dict(color=color,width=width),
            name=label('membership' if relation=='topic_membership' else 'applicant',code),hoverinfo='skip',showlegend=bool(x)))
    degree=Counter(v for e in network['edges'] for v in (e['source'],e['target']))
    for kind in ('papers','topics','patents','companies'):
        nodes=[n for n in network['nodes'] if n['kind']==kind]
        if not nodes: continue
        names=[html.escape(node_title(n,code)) for n in nodes]
        data=[[n['key'],n['kind'],n['id'],name] for n,name in zip(nodes,names)]
        texts=[(name[:16]+'…' if len(name)>16 else name) if kind=='topics' else '' for name in names]
        fig.add_trace(go.Scatter(x=[positions[n['key']][0] for n in nodes],y=[positions[n['key']][1] for n in nodes],
            mode='markers+text' if kind=='topics' else 'markers',ids=[n['key'] for n in nodes],customdata=data,
            text=texts,textposition='top center',textfont=dict(size=10,color='#665532'),
            name=label(kind,code),hovertemplate='%{customdata[3]}<br>%{customdata[2]}<extra>'+label(kind,code)+'</extra>',
            marker=dict(size=[min(27,11+2*math.log1p(degree[n['key']])) for n in nodes],color=COLORS[kind],
                        symbol={'papers':'circle','patents':'diamond','companies':'square','topics':'hexagon'}[kind],
                        line=dict(width=1.5,color='white')),selected=dict(marker=dict(opacity=1)),unselected=dict(marker=dict(opacity=.55))))
    fig.update_layout(height=640,margin=dict(l=30,r=30,t=48,b=30),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',
        clickmode='event+select',dragmode='pan',hovermode='closest',legend=dict(orientation='h',y=-.02,x=.5,xanchor='center'),
        xaxis=dict(visible=False,range=[-.45,3.9],fixedrange=False),yaxis=dict(visible=False,range=[-1.35,1.4],fixedrange=False))
    for kind,x in [('papers',0),('topics',1.15),('patents',2.3),('companies',3.45)]:
        fig.add_annotation(x=x,y=1.32,text=label(kind,code),showarrow=False,font=dict(size=13,color=COLORS[kind]))
    return fig

def reset_network():
    import streamlit as st
    st.session_state.pop('_relationship_selected',None)
    st.session_state['_relationship_reset']=st.session_state.get('_relationship_reset',0)+1

def _source(row):
    return row.get('source_url') or row.get('website') or next(iter(row.get('source_urls',[])),'')

def render_node_details(node,network,code='zh'):
    import streamlit as st
    from dashboard.i18n import preserve_original_text
    from dashboard.report_data import safe_source_url
    with preserve_original_text():
        st.subheader(label('details',code))
        if node is None:
            st.caption(label('choose',code)); return
        row=node['record']; st.caption(label(node['kind'],code)+' · '+row['id'])
        st.markdown('**'+html.escape(node_title(node,code))+'**')
        if row.get('year'): st.caption(label('year',code)+': '+str(row['year']))
        if row.get('applicants'): st.text(label('applicants',code)+': '+'; '.join(row['applicants']))
        if row.get('family_id'): st.caption(label('family',code)+': '+row['family_id'])
        if row.get('abstract_excerpt'): st.text(row['abstract_excerpt'])
        if row.get('summary'): st.text(row['summary'])
        url=_source(row)
        if safe_source_url(url): st.link_button(label('website' if node['kind']=='companies' else 'open',code),url,width='stretch')
        if node['kind']=='companies':
            for i,url in enumerate(row.get('source_urls',[])[:2],1):
                if safe_source_url(url): st.link_button(label('open',code)+' '+str(i),url,width='stretch')
        keys={e['target'] if e['source']==node['key'] else e['source'] for e in network['edges'] if node['key'] in (e['source'],e['target'])}
        neighbors=[n for n in network['nodes'] if n['key'] in keys]
        if neighbors:
            st.markdown('**'+label('neighbors',code)+'**')
            for neighbor in neighbors[:10]: st.caption(label(neighbor['kind'],code)+' · '+node_title(neighbor,code))

def render_relationship_graph(graph,selection):
    import streamlit as st
    from dashboard.i18n import language,preserve_original_text
    code=language()
    tools,reset=st.columns([4,1])
    with tools: size=st.select_slider(label('size',code),options=[45,90,150,210],value=90,key='relationship_size')
    with reset: st.button(label('reset',code),key='relationship_reset_button',on_click=reset_network,width='stretch')
    network=build_network(graph,selection,max_nodes=size)
    if not network['nodes']:
        st.info(label('empty',code)); return
    context=hashlib.sha256(json.dumps([selection,size,[n['key'] for n in network['nodes']]],sort_keys=True).encode()).hexdigest()[:12]
    if st.session_state.get('_relationship_context')!=context:
        st.session_state.pop('_relationship_selected',None)
        st.session_state['_relationship_context']=context
    st.caption(f'{label("nodes",code)} {len(network["nodes"])} · {label("edges",code)} {len(network["edges"])}')
    chart,details=st.columns([2.8,1.2],gap='large')
    with chart:
        with preserve_original_text():
            event=st.plotly_chart(network_figure(network,code),width='stretch',height=640,
                key=f'relationship_chart_{context}_{code}_{st.session_state.get("_relationship_reset",0)}',
                on_select='rerun',selection_mode=('points',),
                config={'displaylogo':False,'scrollZoom':True,'modeBarButtonsToRemove':['lasso2d','select2d']})
        selected=selection_node(event,network)
        if selected: st.session_state['_relationship_selected']=selected['key']
    node=next((n for n in network['nodes'] if n['key']==st.session_state.get('_relationship_selected')),None)
    with details:
        render_node_details(node,network,code)
        if node and node['kind']=='topics':
            from dashboard.bridge_views import open_bridge_context
            st.button(label('focus',code),key='relationship_focus_topic',on_click=open_bridge_context,
                kwargs={'scope_id':selection.get('scope_id') or '', 'application':selection.get('application') or '', 'topic':node['id']},width='stretch')

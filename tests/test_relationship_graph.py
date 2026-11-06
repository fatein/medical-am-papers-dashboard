from copy import deepcopy
from dashboard.relationship_graph import build_network,network_figure,selection_node
from pathlib import Path

def fixture():
    topic={'id':'crowns','labels':{'zh':'牙冠','en':'Crowns','de':'Kronen'},'applications':['dental']}
    paper=dict(id='paper1',title='Original crown paper',year=2024,source_url='https://doi.org/10.1000/crown',applications=['dental'],topics=['crowns'])
    patent=dict(id='EP1A1',title='Original crown patent',year=2025,source_url='https://worldwide.espacenet.com/patent/search?q=pn%3DEP1A1',applicants=['ACME INC'],family_id='F1',applications=['dental'],topics=['crowns'])
    company=dict(id='company1',name='ACME INC',website='https://example.com',applications=['dental'],topics=['crowns'])
    return dict(topics=[topic],papers=[paper],patents=[patent],companies=[company],company_patent_links=[dict(company_id='company1',patent_id='EP1A1',type='applicant_name_match',applicant_name='ACME INC')],reports={})

def test_network_has_only_supported_topic_and_applicant_edges():
    net=build_network(fixture(),{'application':'dental'})
    assert {r['kind'] for r in net['nodes']}=={'papers','patents','companies','topics'}
    assert len(net['edges'])==4
    assert sum(r['kind']=='applicant_name_match' for r in net['edges'])==1
    assert all(e['source'] in {n['key'] for n in net['nodes']} and e['target'] in {n['key'] for n in net['nodes']} for e in net['edges'])

def test_filters_remove_nodes_and_cannot_reuse_stale_node_events():
    net=build_network(fixture(),{'application':'dental'})
    point={'selection':{'points':[{'customdata':['patents:EP1A1','patents','EP1A1','title']} ]}}
    assert selection_node(point,net)['id']=='EP1A1'
    empty=build_network(fixture(),{'application':'nonexistent'})
    assert not empty['nodes']
    assert selection_node(point,empty) is None
    assert selection_node({'selection':{'points':[{'customdata':['injected']}]}},net) is None

def test_topic_membership_does_not_invent_direct_paper_patent_edges():
    g=fixture(); g['company_patent_links']=[]
    net=build_network(g,{})
    assert all(e['kind']=='topic_membership' for e in net['edges'])
    assert not any(e['source'].startswith('papers:') and e['target'].startswith('patents:') for e in net['edges'])

def test_topic_nodes_respect_application_explicit_topic_and_report_scope():
    g=fixture()
    g['topics'].append({'id':'bone','applications':['implants'],'labels':{'zh':'骨','en':'Bone','de':'Knochen'}})
    for kind in ('papers','patents','companies'):
        g[kind][0]['topics'].append('bone')
    for selection in ({'application':'dental'},{'topic':'crowns'}):
        net=build_network(g,selection)
        assert {n['id'] for n in net['nodes'] if n['kind']=='topics'}=={'crowns'}
    g['reports']={'scope1':dict(topic_ids=['crowns'],paper_ids=['paper1'],company_ids=['company1'],patent_links=[{'patent_id':'EP1A1'}])}
    net=build_network(g,{'scope_id':'scope1'})
    assert {n['id'] for n in net['nodes'] if n['kind']=='topics'}=={'crowns'}

def test_network_is_deterministic_bounded_and_retains_three_resource_types():
    g=fixture()
    for kind in ['papers','patents','companies']:
        template=g[kind][0]
        g[kind]=[dict(template,id=f'{template["id"]}-{i}') for i in range(100)]
    g['company_patent_links']=[]
    a=build_network(g,{},max_nodes=45); b=build_network(g,{},max_nodes=45)
    assert a==b and len(a['nodes'])<=45
    assert {n['kind'] for n in a['nodes']}=={'papers','patents','companies','topics'}

def test_default_network_keeps_dense_multi_topic_nodes_separately_clickable():
    from dashboard.relationship_graph import _positions
    g=fixture()
    for i in range(7): g['topics'].append(dict(g['topics'][0],id=f'extra{i}'))
    topic_ids=[t['id'] for t in g['topics']]
    for kind in ('papers','patents','companies'):
        row=g[kind][0]
        g[kind]=[dict(row,id=f'{row["id"]}-{i}',topics=topic_ids) for i in range(30)]
    g['company_patent_links']=[]
    net=build_network(g,{},max_nodes=90); positions=_positions(net)
    for kind in ('papers','patents','companies'):
        ys=sorted(positions[n['key']][1] for n in net['nodes'] if n['kind']==kind)
        assert all(b-a>.05 for a,b in zip(ys,ys[1:]))

def test_figure_node_customdata_resolves_back_to_original_records():
    net=build_network(fixture(),{})
    fig=network_figure(net,'zh')
    data=[v for trace in fig.data if trace.customdata is not None for v in trace.customdata]
    assert any(v[0]=='patents:EP1A1' for v in data)
    assert fig.layout.clickmode=='event+select'

def test_clicked_node_renders_original_details_and_source_and_resets_on_empty_filter():
    from streamlit.testing.v1 import AppTest
    code='''
import streamlit as st
from pathlib import Path
from dashboard.i18n import set_language
from dashboard.relationship_graph import render_relationship_graph
st.selectbox('Language',['zh','en','de'],key='language')
st.selectbox('Application',['dental','none'],key='application')
set_language(st.session_state['language'],Path.cwd())
original=st.plotly_chart
st.plotly_chart=lambda *a,**k: {'selection':{'points':[{'customdata':['patents:EP1A1','patents','EP1A1','Title']}]}}
try: render_relationship_graph(GRAPH,{'application':st.session_state['application']})
finally: st.plotly_chart=original
'''.replace('GRAPH',repr(fixture()))
    app=AppTest.from_string(code,default_timeout=45).run()
    assert not app.exception
    assert any('Original crown patent' in str(r.value) for r in app.markdown)
    assert any('pn%3DEP1A1' in r.proto.url for r in app.get('link_button'))
    app.selectbox(key='language').set_value('de').run()
    assert not app.exception
    assert any(r.value=='Knotendetails' for r in app.subheader)
    app.selectbox(key='application').set_value('none').run()
    assert not app.exception and not app.get('link_button')

def test_linked_view_exposes_relationship_graph_as_the_first_tab():
    from streamlit.testing.v1 import AppTest
    root=Path(__file__).resolve().parents[1]
    app=AppTest.from_file(str(root/'public_app.py'),default_timeout=75)
    app.query_params['lang']='zh'; app.session_state['page']='医疗应用联动'; app.run()
    assert not app.exception
    assert app.tabs[0].label=='关系图'
    assert len(app.get('plotly_chart'))>=1

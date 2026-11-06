from pathlib import Path
import pytest
from dashboard.patent_report_views import compose_patent_supplement, export_html, validate_editorial

ROOT=Path(__file__).resolve().parents[1]

def fixture():
    patents=[dict(id=i,family_id=f,year=2024,title='Original implant <title>',applicants=['ACME'],source_url='https://worldwide.espacenet.com/patent/search?q=pn%3D'+i,applications=['implants_and_prostheses'],topics=['porous'],abstract_excerpt='Porous implant architecture.') for i,f in [('EP1A1','F1'),('US2A1','F1'),('EP3A1','F3')]]
    paper=dict(id='P1',title='Original bone ingrowth study',year=2022,source_url='https://doi.org/10.1000/example',applications=['implants_and_prostheses'],topics=['porous'])
    companies=[dict(id=i,name=n,website='https://example.com',applications=['implants_and_prostheses'],topics=['porous']) for i,n in [('C1','Topic Company'),('C2','Name Matched Company')]]
    report=dict(id='P1-001',scope='question',title='骨长入',applications=['implants_and_prostheses'],topic_ids=['porous'],paper_ids=['P1'],company_ids=['C1','C2'],patent_links=[dict(patent_id=p['id'],score=10-k,topic_ids=['porous'],matched_terms=['porous','bone']) for k,p in enumerate(patents)])
    g=dict(schema_version=1,method_version='fixture',applications=[],topics=[dict(id='porous',labels=dict(zh='多孔植入物',en='Porous implants',de='Poröse Implantate'))],papers=[paper],patents=patents,companies=companies,company_patent_links=[dict(company_id='C2',patent_id='EP1A1',type='applicant_name_match',applicant_name='ACME')],reports={'P1-001':report})
    copy=dict(focus='Pore geometry focus.',academic_comparison='Compare bone ingrowth measures.',industry_question='Check actual product design.',boundary='Disclosure is not clinical validation.')
    e=dict(schema_version=1,reports={'P1-001':dict(scope='question',locales={c:copy.copy() for c in ('zh','en','de')})})
    return g,e

def test_report_counts_publications_but_uses_family_distinct_representatives():
    g,e=fixture(); m=compose_patent_supplement(g,e,'P1-001','en')
    assert m['counts']['publications']==3
    assert m['counts']['families']==2
    assert len(m['representatives'])==2
    assert m['representatives'][0]['patent']['title']=='Original implant <title>'
    assert m['representatives'][0]['papers'][0]['id']=='P1'

def test_topic_similarity_is_distinct_from_applicant_identity():
    g,e=fixture(); m=compose_patent_supplement(g,e,'P1-001','en')
    row=next(r for r in m['representatives'] if r['patent']['id']=='EP1A1')
    assert [c['id'] for c in row['applicant_companies']]==['C2']
    assert 'C1' in [c['id'] for c in row['topic_companies']]

def test_empty_report_keeps_tailored_gap_analysis():
    g,e=fixture(); g['reports']['P1-001']['patent_links']=[]
    m=compose_patent_supplement(g,e,'P1-001','en')
    assert m['counts']['publications']==0 and not m['representatives']
    assert m['editorial']['academic_comparison']=='Compare bone ingrowth measures.'
    assert m['empty_explanation']

def test_html_escapes_original_titles_and_preserves_source_links():
    g,e=fixture(); v=export_html([compose_patent_supplement(g,e,'P1-001','en')])
    assert '&lt;title&gt;' in v and '<title>' not in v.split('<body>')[-1]
    assert 'pn%3DEP1A1' in v and 'https://doi.org/10.1000/example' in v
    assert 'ACME' in v

def test_editorial_requires_exact_coverage_and_three_languages():
    _,e=fixture()
    assert not validate_editorial(e,['P1-001'])
    assert validate_editorial(e,['P1-001','P2-016'])
    e['reports']['P1-001']['locales'].pop('de')
    assert validate_editorial(e,['P1-001'])

def test_material_and_process_comparison_uses_actual_mentions_not_topic_identity():
    from dashboard.patent_report_views import compare_technical_mentions
    left={'technical_features':[{'id':'titanium','group':'material'},{'id':'laser_powder_bed','group':'process'}]}
    right={'technical_features':[{'id':'titanium','group':'material'},{'id':'fused_deposition','group':'process'}]}
    result=compare_technical_mentions(left,right,'en')
    assert result['shared']==['Titanium']
    assert result['left_only']==['Laser powder bed fusion']
    assert result['right_only']==['Fused deposition']

def test_question_report_contents_links_to_the_patent_chapter():
    import json
    from dashboard.academic_questions import header_html, localize_report
    report=json.loads((ROOT/'data/academic_questions/P1-001.json').read_text(encoding='utf-8'))
    for code in ('zh','en','de'):
        assert 'href="#patent-evidence"' in header_html(localize_report(report,code),code)

def test_every_released_report_has_composable_three_language_patent_analysis():
    import json
    from dashboard.bridge_data import load_bridge
    data=load_bridge(ROOT)
    editorial=json.loads((ROOT/'data/patent_report_editorial.json').read_text(encoding='utf-8'))
    assert len(data['reports'])==148
    assert not validate_editorial(editorial,data['reports'])
    patent_ids={r['id'] for r in data['patents']}
    for ident,scope in data['reports'].items():
        for code in ('zh','en','de'):
            model=compose_patent_supplement(data,editorial,ident,code)
            assert model['counts']['publications']==len({r['patent_id'] for r in scope['patent_links']})
            assert model['scope_title'] and len(model['editorial']['focus'])>30
            assert all(r['patent']['id'] in patent_ids for r in model['representatives'])
            families=[r['patent'].get('family_id') or r['patent']['id'] for r in model['representatives']]
            assert len(families)==len(set(families))

@pytest.mark.parametrize('scope_id,view,param,code',[('P1-001','question-report','question','en'),('P1-01','direction-report','direction','de')])
def test_report_chapter_opens_the_exact_scope_in_linked_browser(scope_id,view,param,code):
    from streamlit.testing.v1 import AppTest
    from dashboard.bridge_data import load_bridge
    data=load_bridge(ROOT)
    app=AppTest.from_file(str(ROOT/'public_app.py'),default_timeout=90)
    app.query_params.update({'lang':code,'view':view,param:scope_id})
    app.run()
    assert not app.exception
    assert app.button(key=f'patent_bridge_report_{scope_id}')
    app.button(key=f'patent_bridge_report_{scope_id}').click().run()
    assert not app.exception
    assert app.radio(key=f'page__{code}').value=='医疗应用联动'
    assert app.selectbox(key=f'bridge_scope__{code}').value==scope_id
    assert app.metric[1].value==f'{len(data["reports"][scope_id]["patent_links"]):,}'

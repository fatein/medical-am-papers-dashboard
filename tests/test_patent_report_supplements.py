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
            assert model['scope_title'] and all(model['editorial'][key].strip() for key in ('focus','academic_comparison','industry_question'))
            assert all(r['patent']['id'] in patent_ids for r in model['representatives'])
            families=[r['patent'].get('family_id') or r['patent']['id'] for r in model['representatives']]
            assert len(families)==len(set(families))


@pytest.mark.parametrize('code,focus,academic,industry,boilerplate', [
    ('zh', '孔径分布、孔形、开放孔隙和贯通路径', '实际孔隙测量与组织学骨长入深度及分布', '植入物型号的孔隙设计文件与制造后孔隙检测',
     ('仅将披露中明确涉及', '专利披露可用于', '技术相近只是核验线索', '全领域专利规模', '方法与限制：', '本问题的证据边界', '不能作为临床', '共同关键词本身不能', '不按法律价值排序', '不等于权利要求限定', '同词也不能证明', '技术主题相似不能证明')),
    ('en', 'pore-size distribution, pore shape, open porosity and connected paths', 'histological depth and distribution of bone ingrowth', 'model-specific pore design documents and as-manufactured porosity measurements',
     ('retain a problem-level connection only', 'A patent disclosure can suggest', 'Technical similarity remains a verification lead', 'not the entire patent landscape', 'Method and limits:', 'Evidence boundary for this question', 'not comparative clinical', 'shared terms alone do not', 'not ranked by legal value', 'do not establish claim limitations', 'same term does not establish identical', 'Topic similarity does not establish ownership')),
    ('de', 'Porengrößenverteilung, Porenform, offene Porosität und durchgängige Wege', 'histologischer Tiefe und Verteilung des Knocheneinwachsens', 'modellspezifische Porendesigns und Messungen am gefertigten Implantat',
     ('einen Bezug zur Forschungsfrage nur', 'Eine Patentschrift kann Prüfvariablen', 'Technische Ähnlichkeit bleibt ein Prüfhinweis', 'nicht auf die gesamte Patentlandschaft', 'Methode und Grenzen:', 'Evidenzgrenze dieser Fragestellung', 'keine vergleichende klinische', 'gemeinsame Begriffe belegen keine', 'Rangliste des rechtlichen Werts', 'belegen weder Anspruchsmerkmale', 'gleiche Begriffe belegen keine identischen', 'Thematische Ähnlichkeit belegt weder Inhaberschaft')),
])
def test_localized_chapters_keep_specific_guidance_without_shared_caveats(code,focus,academic,industry,boilerplate):
    import json
    from dashboard.bridge_data import load_bridge
    graph=load_bridge(ROOT)
    editorial=json.loads((ROOT/'data/patent_report_editorial.json').read_text(encoding='utf-8'))
    models=[compose_patent_supplement(graph,editorial,ident,code) for ident in graph['reports']]
    first=next(m for m in models if m['scope_id']=='P1-001')
    assert focus in first['editorial']['focus']
    assert academic in first['editorial']['academic_comparison']
    assert industry in first['editorial']['industry_question']
    rendered=export_html(models)
    assert all(phrase not in rendered for phrase in boilerplate)
    assert all(m['editorial']['boundary'] not in rendered for m in models)
    assert editorial['reports']['P1-001']['locales'][code]['boundary']==first['editorial']['boundary']


def test_cleanup_preserves_source_negation_and_nonboilerplate_guidance():
    graph,editorial=fixture()
    original='A porous coating does not improve bone ingrowth in this experiment.'
    graph['patents'][0]['abstract_excerpt']=original
    editorial['reports']['P1-001']['locales']['en']['academic_comparison']='The study does not measure pore connectivity.'
    model=compose_patent_supplement(graph,editorial,'P1-001','en')
    rendered=export_html([model])
    assert original in rendered
    assert 'The study does not measure pore connectivity.' in rendered
    assert 'Disclosure is not clinical validation.' not in rendered

@pytest.mark.parametrize('scope_id,view,param,code',[('P1-001','question-report','question','zh'),('P1-001','question-report','question','en'),('P1-01','direction-report','direction','de')])
def test_report_chapter_opens_the_exact_scope_in_linked_browser(scope_id,view,param,code):
    import json
    from streamlit.testing.v1 import AppTest
    from dashboard.bridge_data import load_bridge
    data=load_bridge(ROOT)
    app=AppTest.from_file(str(ROOT/'public_app.py'),default_timeout=90)
    app.query_params.update({'lang':code,'view':view,param:scope_id})
    app.run()
    assert not app.exception
    editorial=json.loads((ROOT/'data/patent_report_editorial.json').read_text(encoding='utf-8'))
    original=editorial['reports'][scope_id]['locales'][code]
    visible='\n'.join(item.value for kind in ('caption','markdown','text','info') for item in app.get(kind))
    assert original['boundary'] not in visible
    assert original['focus'] not in visible
    for phrase in {
        'zh': ('专利披露可用于提出待测变量','技术相近只是核验线索','方法与限制：','共同关键词本身不能证明'),
        'en': ('A patent disclosure can suggest variables','Technical similarity remains a verification lead','Method and limits:','shared terms alone do not establish'),
        'de': ('Eine Patentschrift kann Prüfvariablen','Technische Ähnlichkeit bleibt ein Prüfhinweis','Methode und Grenzen:','gemeinsame Begriffe belegen keine'),
    }[code]:
        assert phrase not in visible
    concise=compose_patent_supplement(data,editorial,scope_id,code)
    assert concise['editorial']['focus'] in visible
    assert concise['editorial']['academic_comparison'] in visible
    assert app.button(key=f'patent_bridge_report_{scope_id}')
    app.button(key=f'patent_bridge_report_{scope_id}').click().run()
    assert not app.exception
    assert app.radio(key=f'page__{code}').value=='医疗应用联动'
    assert app.selectbox(key=f'bridge_scope__{code}').value==scope_id
    assert app.metric[1].value==f'{len(data["reports"][scope_id]["patent_links"]):,}'

"""Scoped patent chapters: recorded evidence, comparisons and honest gaps."""
from __future__ import annotations
import html
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from dashboard.i18n import language, preserve_original_text
from dashboard.report_data import safe_source_url

# Explicit visitor-language copy keeps original source strings unchanged.
COPY = {
 'elements': ('原文提及的方案要素','Technical elements mentioned in the source','In der Quelle erwähnte technische Elemente'),
 'material': ('材料词','Material terms','Materialbegriffe'),
 'process': ('工艺词','Process terms','Verfahrensbegriffe'),
 'design': ('结构／设计词','Structure / design terms','Struktur-/Designbegriffe'),
 'focus_terms': ('关注点术语','Focus terms','Fokusbegriffe'),
 'shared_terms': ('共同出现的材料／工艺词','Material / process terms appearing in both sources','In beiden Quellen vorkommende Material-/Verfahrensbegriffe'),
 'left_terms': ('仅本专利题摘提及','Mentioned only in this patent metadata','Nur in diesen Patentmetadaten erwähnt'),
 'right_terms': ('仅对照资料提及','Mentioned only in the comparison source','Nur in der Vergleichsquelle erwähnt'),
 'updated': ('专利资料更新：2026-11-06','Patent data updated: 2026-11-06','Patentdaten aktualisiert: 2026-11-06'),
 'title': ('专利证据与论文—企业串联','Patent evidence across research and industry','Patentevidenz zwischen Forschung und Industrie'),
 'publications': ('主题匹配公开记录','Topic-matched publications','Thematisch passende Veröffentlichungen'),
 'families': ('已知同族组','Observed patent families','Bekannte Patentfamilien'),
 'papers': ('本报告关联论文','Papers linked by this report','Im Bericht verknüpfte Publikationen'),
 'companies': ('本报告关联企业','Companies linked by this report','Im Bericht verknüpfte Unternehmen'),
 'summary': ('匹配 {publications:,} 条公开记录，涉及 {families:,} 个已知同族组、{applicants:,} 个原始申请人名称；公开年份：{years}。','{publications:,} matched publications span {families:,} observed families and {applicants:,} original applicant names; publication years: {years}.','{publications:,} passende Veröffentlichungen umfassen {families:,} bekannte Familien und {applicants:,} ursprüngliche Anmeldernamen; Veröffentlichungsjahre: {years}.'),
 'focus': ('检索焦点与技术方案','Search focus and technical schemes','Suchfokus und technische Ansätze'),
 'academic_comparison': ('与论文证据如何对照','Comparison with research evidence','Abgleich mit wissenschaftlicher Evidenz'),
 'industry_question': ('与企业技术如何衔接','Connection to enterprise technology','Bezug zur Unternehmenstechnologie'),
 'boundary': ('本问题的证据边界','Evidence boundary for this question','Evidenzgrenze dieser Fragestellung'),
 'coverage': ('技术主题覆盖','Technical topic coverage','Abdeckung technischer Themen'),
 'topic': ('技术主题','Technical topic','Technisches Thema'),
 'selection': ('代表性专利与交叉证据','Representative patents and cross-resource evidence','Repräsentative Patente und quellenübergreifende Evidenz'),
 'basis': ('匹配依据','Matching evidence','Zuordnungsbelege'),
 'facet': ('问题限定词','Question-specific terms','Fragestellungsspezifische Begriffe'),
 'excerpt': ('原始方案节选','Original disclosure excerpt','Auszug aus der Originaloffenbarung'),
 'related_papers': ('共享技术主题的报告论文','Report papers sharing a technical topic','Berichtspublikationen mit gleichem technischem Thema'),
 'applicant_companies': ('申请人名称与企业档案对应','Applicant-name correspondence to company profiles','Übereinstimmung von Anmeldernamen mit Unternehmensprofilen'),
 'topic_companies': ('同主题企业线索','Companies sharing a technical topic','Unternehmen mit gleichem technischem Thema'),
 'no_paper': ('暂无同一细分主题的报告论文。','No report papers share this specific topic.','Keine Berichtspublikationen mit diesem konkreten Thema.'),
 'no_company': ('暂无申请人名称对应的企业档案。','No company profiles match the applicant name.','Keine Unternehmensprofile mit passendem Anmeldernamen.'),
 'empty': ('当前报告范围内暂无匹配专利。','No matching patents in this report scope.','Keine passenden Patente in diesem Berichtsbereich.'),
 'open': ('查看专利原文 ↗','View original patent ↗','Originalpatent ansehen ↗'),
 'not_available': ('未提供','Not provided','Nicht angegeben'),
 'unavailable': ('专利补充数据暂时不可用，请稍后重试。','The patent supplement is temporarily unavailable. Please try again later.','Die Patentergänzung ist vorübergehend nicht verfügbar. Bitte später erneut versuchen.'),
 'alignment': ('技术主题：{topics}','Technical topics: {topics}','Technische Themen: {topics}'),
}

# These exact editorial wrappers are shared by the released reports. Keep
# question-specific comparisons and source excerpts intact.
_EDITORIAL_WRAPPERS = {
 'zh': {
  'focus': ('本报告的专利筛选聚焦', '；仅将披露中明确涉及这些变量的记录纳入对应问题。'),
  'academic_comparison': ('', '专利披露可用于提出待测变量，不能代替这些实测或研究设计。'),
  'industry_question': ('', '技术相近只是核验线索，仍需具体产品或流程资料支持。'),
 },
 'en': {
  'focus': ('Screen patent records for ', '; retain a problem-level connection only when these variables are explicitly disclosed.'),
  'academic_comparison': ('', ' A patent disclosure can suggest variables to test but cannot replace these measurements or study designs.'),
  'industry_question': ('', ' Technical similarity remains a verification lead and requires product- or process-specific documentation.'),
 },
 'de': {
  'focus': ('Patentschriften gezielt auf ', ' prüfen; einen Bezug zur Forschungsfrage nur bei ausdrücklicher Offenlegung dieser Variablen herstellen.'),
  'academic_comparison': ('', ' Eine Patentschrift kann Prüfvariablen anregen, ersetzt aber weder diese Messungen noch das Studiendesign.'),
  'industry_question': ('', ' Technische Ähnlichkeit bleibt ein Prüfhinweis und erfordert produkt- oder prozessspezifische Unterlagen.'),
 },
}


def _concise_editorial(guide,code):
    result=dict(guide)
    for key,(prefix,suffix) in _EDITORIAL_WRAPPERS[code].items():
        value=result[key]
        if value.endswith(suffix):
            value=value[:-len(suffix)]
            if prefix and value.startswith(prefix):
                value=value[len(prefix):]
        result[key]=value.strip()
    return result

def text(key,code):
    return COPY[key][{'zh':0,'en':1,'de':2}[code]]

def patent_section_title(code='zh'):
    return text('title',code)

def validate_editorial(data,expected_ids):
    if not isinstance(data,dict) or data.get('schema_version')!=1 or not isinstance(data.get('reports'),dict):
        return ['Invalid patent editorial schema']
    errors=[]
    if set(data['reports'])!=set(expected_ids): errors.append('Patent editorial report coverage mismatch')
    for ident,row in data['reports'].items():
        if row.get('scope') not in ('question','direction') or set(row.get('locales',{}))!={'zh','en','de'}:
            errors.append(f'{ident}: incomplete locales/scope')
        for code,values in row.get('locales',{}).items():
            if set(values)!={'focus','academic_comparison','industry_question','boundary'} or not all(isinstance(v,str) and v.strip() for v in values.values()):
                errors.append(f'{ident}/{code}: incomplete guidance')
    return errors

def _family(patent):
    return patent.get('family_id') or patent['id']

def compare_technical_mentions(left,right,code):
    from dashboard.technical_features import feature_label
    def terms(row):
        return {r['id'] for r in row.get('technical_features',[]) if r['group'] in ('material','process')}
    a,b=terms(left),terms(right)
    labels=lambda values: [feature_label(i,code) for i in sorted(values)]
    return dict(shared=labels(a&b),left_only=labels(a-b),right_only=labels(b-a))

def _feature_groups(patent,code):
    from dashboard.technical_features import feature_label
    return {group:[dict(row,label=feature_label(row['id'],code)) for row in patent.get('technical_features',[]) if row['group']==group] for group in ('material','process','design','focus')}

def _comparison_text(values,code):
    return ' · '.join(text(label,code)+': '+', '.join(values[key]) for key,label in [('shared','shared_terms'),('left_only','left_terms'),('right_only','right_terms')] if values.get(key))

def compose_patent_supplement(graph,editorial,scope_id,code='zh'):
    if code not in ('zh','en','de'): raise ValueError('Unsupported chapter language')
    scope=graph['reports'][scope_id]
    guide=_concise_editorial(editorial['reports'][scope_id]['locales'][code],code)
    patents={r['id']:r for r in graph['patents']}; pm={r['id']:r for r in graph['papers']}; cm={r['id']:r for r in graph['companies']}
    topics={r['id']:r for r in graph['topics']}
    papers=[pm[i] for i in dict.fromkeys(scope['paper_ids']) if i in pm]
    companies=[cm[i] for i in dict.fromkeys(scope['company_ids']) if i in cm]
    links=sorted(scope['patent_links'],key=lambda r:(-r['score'],-(patents[r['patent_id']].get('year') or 0),r['patent_id']))
    unique={r['patent_id']:r for r in links}; records=[patents[i] for i in unique]
    counts=dict(publications=len(records),families=len({_family(r) for r in records}),applicants=len({n for r in records for n in r['applicants']}),papers=len(papers),companies=len(companies))
    years=[r['year'] for r in records if r.get('year')]
    years_text=f'{min(years)}–{max(years)}' if years else text('not_available',code)
    coverage=[dict(topic=topics[t]['labels'][code],publications=sum(t in l['topic_ids'] for l in unique.values()),papers=sum(t in r['topics'] for r in papers),companies=sum(t in r['topics'] for r in companies)) for t in scope['topic_ids'] if t in topics]
    selected=[]; seen=set(); limit=10 if scope['scope']=='direction' else 6
    def add(link):
        family=_family(patents[link['patent_id']])
        if family not in seen and len(selected)<limit: selected.append(link); seen.add(family)
    for topic in scope['topic_ids']:
        candidate=next((r for r in links if topic in r['topic_ids']),None)
        if candidate: add(candidate)
    for link in links: add(link)
    selected.sort(key=lambda r:(-r['score'],-(patents[r['patent_id']].get('year') or 0),r['patent_id']))
    reps=[]
    for link in selected:
        patent=patents[link['patent_id']]; shared=set(link['topic_ids'])
        direct=[dict(cm[e['company_id']],matched_applicant=e['applicant_name']) for e in graph['company_patent_links'] if e['patent_id']==patent['id'] and e['type']=='applicant_name_match' and e['company_id'] in cm]
        direct_ids={c['id'] for c in direct}
        related=[r for r in papers if shared.intersection(r['topics'])]
        related.sort(key=lambda r:(-len(shared.intersection(r['topics'])),-(r.get('year') or 0),r['id']))
        related=[dict(r,technical_comparison=compare_technical_mentions(patent,r,code)) for r in related[:3]]
        labels=[topics[t]['labels'][code] for t in link['topic_ids'] if t in topics]
        reps.append(dict(patent=patent,technical_groups=_feature_groups(patent,code),matched_terms=link.get('matched_terms',[]),facet_terms=link.get('facet_terms',[]),topic_labels=labels,evidence_excerpt=(link.get('evidence_excerpt') or patent.get('abstract_excerpt',''))[:360],analysis=text('alignment',code).format(topics=' / '.join(labels)),papers=related,applicant_companies=direct,topic_companies=[dict(r,technical_comparison=compare_technical_mentions(patent,r,code)) for r in companies if r['id'] not in direct_ids and shared.intersection(r['topics'])][:4]))
    scope_title=scope.get('labels',{}).get(code) or scope.get('title',scope_id)
    return dict(scope_id=scope_id,scope=scope['scope'],scope_title=scope_title,code=code,title=text('title',code),counts=counts,years=years_text,summary=text('summary',code).format(**counts,years=years_text),editorial=guide,coverage=coverage,representatives=reps,context_only=bool(scope.get('clinical_comparison')),empty_explanation=text('empty',code) if not records else '',method_version=graph['method_version'],papers=papers,companies=companies)


@st.cache_data(show_spinner=False)
def _report_inputs(root,signature):
    from dashboard.bridge_data import load_bridge
    graph=load_bridge(Path(root))
    editorial=json.loads((Path(root)/'data/patent_report_editorial.json').read_text(encoding='utf-8'))
    errors=validate_editorial(editorial,graph['reports'])
    if errors: raise ValueError('; '.join(errors))
    return graph,editorial


def patent_report_section(root,scope_id,code=None):
    code=code or language()
    paths=[Path(root)/'data'/name for name in ('patent_bridge.json.gz','patent_bridge_manifest.json','patent_report_editorial.json')]
    try:
        signature=tuple((p.stat().st_mtime_ns,p.stat().st_size) for p in paths)
        graph,editorial=_report_inputs(str(root),signature)
        model=compose_patent_supplement(graph,editorial,scope_id,code)
    except (OSError,ValueError,KeyError):
        with preserve_original_text(): st.info(text('unavailable',code))
        return
    with preserve_original_text():
        st.html(f'<div class="aq-section report-section" id="patent-evidence"><h2>{html.escape(model["title"])}</h2></div>')
        st.caption(text('updated',code).format(method=model['method_version']))
        for column,key in zip(st.columns(4),('publications','families','papers','companies')):
            column.metric(text(key,code),f'{model["counts"][key]:,}')
        st.write(model['summary'])
        if model['empty_explanation']: st.info(model['empty_explanation'])
        for key in ('focus','academic_comparison','industry_question'):
            st.markdown(f'**{text(key,code)}**'); st.write(model['editorial'][key])
        if model['coverage']:
            st.markdown(f'**{text("coverage",code)}**')
            frame=pd.DataFrame(model['coverage']).rename(columns={k:text(k,code) for k in ('topic','publications','papers','companies')})
            st.dataframe(frame,hide_index=True,width='stretch')
        if model['representatives']:
            st.markdown(f'### {text("selection",code)}')
        for index,row in enumerate(model['representatives'],1):
            patent=row['patent']
            with st.container(border=True):
                st.markdown(f'**{index}. {patent["id"]} · {patent.get("year") or text("not_available",code)}**')
                st.text(patent['title']); st.caption('; '.join(patent['applicants']))
                st.write(row['analysis']); st.caption(text('basis',code)+': '+', '.join(row['matched_terms']))
                if any(row['technical_groups'].values()):
                    st.markdown(f'**{text("elements",code)}**')
                    for group,features in row['technical_groups'].items():
                        if features:
                            st.write(text('focus_terms' if group=='focus' else group,code)+': '+'; '.join(f['label'] for f in features))
                    with st.expander(text('elements',code)+' · '+text('basis',code)):
                        for features in row['technical_groups'].values():
                            for feature in features:
                                st.caption(feature['label']+': '+', '.join(feature['matched_terms']))
                                st.text(feature['excerpt'])
                if row['facet_terms']: st.caption(text('facet',code)+': '+', '.join(row['facet_terms']))
                if row['evidence_excerpt']:
                    st.caption(text('excerpt',code)); st.text(row['evidence_excerpt'])
                st.link_button(text('open',code),patent['source_url'])
                st.markdown(f'**{text("related_papers",code)}**')
                if row['papers']:
                    for paper in row['papers']:
                        if safe_source_url(paper.get('source_url','')): st.link_button(paper['title']+' ↗',paper['source_url'],width='stretch')
                        else: st.text(paper['title'])
                        comparison=_comparison_text(paper['technical_comparison'],code)
                        if comparison: st.caption(comparison)
                else: st.caption(text('no_paper',code))
                if row['applicant_companies']:
                    st.markdown(f'**{text("applicant_companies",code)}**')
                    for company in row['applicant_companies']: st.text(company['name']+' ↔ '+company['matched_applicant'])
                else: st.caption(text('no_company',code))
                if row['topic_companies']:
                    st.markdown(f'**{text("topic_companies",code)}**')
                    for company in row['topic_companies']:
                        if safe_source_url(company.get('website','')): st.link_button(company['name']+' ↗',company['website'])
                        else: st.text(company['name'])
                        comparison=_comparison_text(company['technical_comparison'],code)
                        if comparison: st.caption(comparison)


def _link(label,url):
    escaped=html.escape(str(label))
    return (f'<a href="{html.escape(url,quote=True)}" target="_blank" rel="noopener noreferrer">{escaped}</a>' if safe_source_url(url) else escaped)


def export_html(models):
    """Standalone escaped report archive; no scripts, credentials or full texts."""
    esc=html.escape; parts=[]
    for model in models:
        code=model['code']; ident=model['scope_id']
        body=f'<section id="{esc(code+"-"+ident)}" lang="{esc(code)}"><h1>{esc(ident+" · "+model["scope_title"])}</h1><h2>{esc(model["title"])}</h2><p>{esc(text("updated",code).format(method=model["method_version"]))}</p><p>{esc(model["summary"])}</p>'
        if model['empty_explanation']: body+=f'<aside>{esc(model["empty_explanation"])}</aside>'
        for key in ('focus','academic_comparison','industry_question'): body+=f'<h2>{esc(text(key,code))}</h2><p>{esc(model["editorial"][key])}</p>'
        if model['coverage']:
            body+=f'<h2>{esc(text("coverage",code))}</h2><table><thead><tr>'
            body+=''.join(f'<th>{esc(text(key,code))}</th>' for key in ('topic','publications','papers','companies'))+'</tr></thead><tbody>'
            body+=''.join('<tr>'+''.join(f'<td>{esc(str(row[key]))}</td>' for key in ('topic','publications','papers','companies'))+'</tr>' for row in model['coverage'])+'</tbody></table>'
        if model['representatives']: body+=f'<h2>{esc(text("selection",code))}</h2>'
        for row in model['representatives']:
            p=row['patent']
            body+=f'<article><h3>{_link(p["id"]+" · "+p["title"],p["source_url"])}</h3><p>{esc(str(p.get("year") or ""))} · {esc("; ".join(p["applicants"]))}</p>'
            body+=f'<p>{esc(row["analysis"])}</p><p>{esc(text("basis",code)+": "+", ".join(row["matched_terms"]))}</p>'
            if any(row['technical_groups'].values()):
                body+=f'<h4>{esc(text("elements",code))}</h4><ul>'
                for group,features in row['technical_groups'].items():
                    if features: body+=f'<li>{esc(text("focus_terms" if group=="focus" else group,code))}: {esc("; ".join(f["label"] for f in features))}</li>'
                body+='</ul>'
            if row['facet_terms']: body+=f'<p>{esc(text("facet",code)+": "+", ".join(row["facet_terms"]))}</p>'
            body+=f'<blockquote>{esc(row["evidence_excerpt"])}</blockquote><h4>{esc(text("related_papers",code))}</h4><ul>'
            body+=''.join(f'<li>{_link(paper["title"],paper.get("source_url",""))}<br><small>{esc(_comparison_text(paper["technical_comparison"],code))}</small></li>' for paper in row['papers'])+'</ul>'
            if not row['papers']: body+=f'<p>{esc(text("no_paper",code))}</p>'
            if row['applicant_companies']:
                body+=f'<h4>{esc(text("applicant_companies",code))}</h4><ul>'
                body+=''.join(f'<li>{esc(c["name"]+" ↔ "+c["matched_applicant"])}</li>' for c in row['applicant_companies'])+'</ul>'
            else: body+=f'<p>{esc(text("no_company",code))}</p>'
            if row['topic_companies']:
                body+=f'<h4>{esc(text("topic_companies",code))}</h4><ul>'
                body+=''.join(f'<li>{_link(c["name"],c.get("website",""))}<br><small>{esc(_comparison_text(c["technical_comparison"],code))}</small></li>' for c in row['topic_companies'])+'</ul>'
            body+='</article>'
        parts.append(body+'</section>')
    return ('<!doctype html><html><head><meta charset="utf-8"><title>Patent evidence supplements</title>'
            '<style>body{font:16px/1.85 system-ui,sans-serif;max-width:1060px;margin:40px auto;padding:0 20px;color:#19374b}section{margin-bottom:70px}article{border:1px solid #dbe8e8;border-radius:10px;padding:20px;margin:20px 0}blockquote{border-left:4px solid #137f75;padding-left:16px;color:#526d7b}a{color:#107e77}aside{background:#f0f6f5;padding:18px}footer{font-size:13px;border-top:1px solid #ddd;margin-top:35px;padding-top:20px}</style></head><body>'+''.join(parts)+'</body></html>')

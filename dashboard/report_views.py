"""Visitor-facing, responsive reading view for independently authored reports."""
from __future__ import annotations

import html
import json
from pathlib import Path

import streamlit as st

from dashboard.report_data import REF_PATTERN, RAW_HTML, PRIVATE_PATH, safe_source_url
from dashboard.report_navigation import restore_question_context, open_report_paper, open_report_company


def render_cited_markdown(section: dict, references: list[dict]) -> str:
    body = section['markdown']
    if RAW_HTML.search(body) or PRIVATE_PATH.search(body):
        raise ValueError('Invalid report body')
    refs = {ref['id']: ref for ref in references}
    def replace(match):
        title, ref_id = match.groups()
        ref = refs.get(ref_id)
        if not ref or not safe_source_url(ref['url']):
            raise ValueError(f'Invalid citation: {ref_id}')
        return (f'<a href="{html.escape(ref["url"], quote=True)}" target="_blank" '
                f'rel="noopener noreferrer">{html.escape(title)} ↗</a>')
    return REF_PATTERN.sub(replace, body)


REPORT_CSS = '''<style>
.st-key-report_reader{max-width:1250px;margin:auto;color:#183049}
.st-key-report_reader .report-hero{background:linear-gradient(120deg,#e8f4ef,#eef3fb);border:1px solid #dce8e7;border-radius:18px;padding:30px 34px;margin:12px 0 28px}
.st-key-report_reader .report-breadcrumb{font-size:12px;color:#137f75;letter-spacing:.04em}
.st-key-report_reader .report-hero h1{font-size:34px;line-height:1.45;margin:14px 0}
.st-key-report_reader .report-date{font-size:12px;color:#75869b}
.st-key-report_reader .report-lead{font-size:18px;line-height:1.9;margin-top:20px}
.st-key-report_reader [data-testid="stMarkdownContainer"]{line-height:1.9;overflow-wrap:anywhere}
.st-key-report_reader [data-testid="stMarkdownContainer"] p{line-height:1.95;margin-bottom:1.2rem}
.st-key-report_reader [data-testid="stMarkdownContainer"] table{display:block;overflow-x:auto;font-size:14px}
.st-key-report_reader a{color:#137f75;text-underline-offset:3px}
.st-key-report_reader .report-toc a{display:block;padding:9px 0;border-bottom:1px solid #e5eaf0;font-size:14px;text-decoration:none}
.st-key-report_reader .report-section{scroll-margin-top:85px;border-top:1px solid #dce5ed;padding-top:24px;margin-top:16px}
.st-key-report_reader .report-mobile-toc{display:none}
.st-key-report_reader h2{font-size:26px;margin-top:12px}.st-key-report_reader h3{font-size:20px}
@media(min-width:1101px){.st-key-report_reader [data-testid="stHorizontalBlock"]{align-items:flex-start}.st-key-report_reader [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:first-child{position:sticky;top:90px}}
@media(max-width:1100px){.st-key-report_reader .report-desktop-toc{display:none}.st-key-report_reader .report-mobile-toc{display:block}.st-key-report_reader .report-hero{padding:22px 20px}.st-key-report_reader .report-hero h1{font-size:27px}.st-key-report_reader .report-lead{font-size:16px}}
</style>'''


def question_report_page(report: dict | None, question: dict | None, root: Path) -> None:
    st.button('← 返回研究问题', key='report_back', on_click=restore_question_context, args=(question,))
    if not report:
        st.info('未找到对应报告。请返回研究问题列表。')
        return
    st.markdown(REPORT_CSS, unsafe_allow_html=True)
    with st.container(key='report_reader'):
        st.markdown(
            '<div class="report-hero">'
            f'<div class="report-breadcrumb">{html.escape(report["p"])} / {html.escape(report["direction"])} / {html.escape(report["question_id"])}</div>'
            f'<h1>{html.escape(report["title"])}</h1>'
            f'<div class="report-date">更新于 {html.escape(report["updated_at"])} · 资料截至 {html.escape(report["evidence_cutoff"])}</div>'
            f'<div class="report-lead">{html.escape(report["core_finding"])}</div></div>', unsafe_allow_html=True)
        toc = ''.join(f'<a href="#report-{s["id"]}" target="_self">{html.escape(s["title"])}</a>' for s in report['sections'])
        toc += '<a href="#report-sources" target="_self">来源与相关档案</a>'
        st.markdown(f'<details class="report-mobile-toc"><summary>报告目录</summary><nav class="report-toc">{toc}</nav></details>',unsafe_allow_html=True)
        nav, content = st.columns([1, 4], gap='large')
        nav.markdown(f'<div class="report-desktop-toc"><b>报告目录</b><nav class="report-toc">{toc}</nav></div>',unsafe_allow_html=True)
        with content:
            for section in report['sections']:
                st.markdown(f'<div class="report-section" id="report-{section["id"]}"><h2>{html.escape(section["title"])}</h2></div>',unsafe_allow_html=True)
                st.markdown(render_cited_markdown(section, report['references']), unsafe_allow_html=True)
            st.markdown('<div class="report-section" id="report-sources"><h2>来源与相关档案</h2></div>',unsafe_allow_html=True)
            for ref in report['references']:
                if not safe_source_url(ref['url']):
                    continue
                year = f' · {ref["year"]}' if ref.get('year') else ''
                st.markdown(f'**{html.escape(ref["id"])} · {html.escape(ref["publisher"])}{year}**')
                st.link_button(ref['title']+' ↗', ref['url'], width='stretch')
            paper_path = Path(root)/'data/cross_analysis.json'
            if report['related_paper_ids'] and paper_path.exists():
                papers = {p['id']: p for p in json.loads(paper_path.read_text(encoding='utf-8'))['papers']}
                with st.expander('查看相关论文档案'):
                    for pid in report['related_paper_ids']:
                        if pid in papers:
                            st.button(papers[pid]['title'], key=f'report_paper_{pid}',
                                      on_click=open_report_paper, args=(pid,))
            if report['related_company_ids']:
                from dashboard.enterprise_data import load_enterprises
                companies = load_enterprises(root).set_index('company_id')
                with st.expander('查看相关企业档案'):
                    for cid in report['related_company_ids']:
                        if cid in companies.index:
                            name = companies.loc[cid, 'name']
                            st.button(name, key=f'report_company_{cid}', on_click=open_report_company, args=(name,))

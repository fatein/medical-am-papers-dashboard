"""Individually authored academic reports with shared sources and three reviewed locales."""
from __future__ import annotations

from collections import Counter
from datetime import date
import base64
import html
import json
from pathlib import Path
import re

from dashboard.report_data import REF_PATTERN, RAW_HTML, PRIVATE_PATH, safe_source_url

LANGUAGES = ('zh', 'en', 'de')
HAN = re.compile(r'[\u3400-\u9fff]')
FORBIDDEN_SECTIONS = {'industry', 'intersection', 'outlook', 'summary', 'conclusion', 'core_finding'}
UI = {
    'zh': {'back': '← 返回研究问题', 'contents': '报告目录', 'sources': '论文来源',
           'updated': '更新于', 'cutoff': '资料截至', 'papers': '查看相关论文档案',
           'figure': '查看原图', 'source': '查看论文', 'missing': '未找到对应报告。'},
    'en': {'back': '← Back to research question', 'contents': 'Contents', 'sources': 'Research sources',
           'updated': 'Updated', 'cutoff': 'Sources through', 'papers': 'Related paper records',
           'figure': 'Open original figure', 'source': 'Open paper', 'missing': 'Report not found.'},
    'de': {'back': '← Zurück zur Forschungsfrage', 'contents': 'Inhalt', 'sources': 'Wissenschaftliche Quellen',
           'updated': 'Aktualisiert', 'cutoff': 'Quellenstand', 'papers': 'Zugehörige Publikationen',
           'figure': 'Originalabbildung öffnen', 'source': 'Publikation öffnen', 'missing': 'Bericht nicht gefunden.'},
}


def numeric_fingerprint(text: str) -> Counter:
    text = REF_PATTERN.sub('', text)
    return Counter(m.replace(',', '.') for m in re.findall(r'(?<![A-Za-z])\d+(?:[.,]\d+)?', text))


def safe_asset_path(value: str) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r'assets/academic_figures/P[1-7]-\d{3}/[A-Za-z0-9_-]+\.(?:png|jpg|jpeg|webp)', value))


def has_unregistered_link(body: str) -> bool:
    remaining = REF_PATTERN.sub('', body)
    return 'ref:' in remaining or bool(re.search(
        r'\]\s*[\[(]|(?m:^\s*\[[^\]]+\]:)|https?://|!\[|<[^>]+@[^>]+>', remaining))


def validate_report(report: dict) -> list[str]:
    errors = []
    fields = {'schema_version', 'question_id', 'p', 'version', 'updated_at', 'evidence_cutoff',
              'related_paper_ids', 'references', 'figures', 'locales'}
    if not isinstance(report, dict) or set(report) != fields:
        return ['Unknown or missing academic report fields']
    if PRIVATE_PATH.search(json.dumps(report, ensure_ascii=False)):
        errors.append('Private path in public report')
    if report['schema_version'] != 2 or not re.fullmatch(r'P[1-7]-\d{3}', str(report['question_id'])):
        errors.append('Invalid academic report identity')
    if report['p'] != str(report['question_id']).split('-')[0]:
        errors.append('Mismatched P layer')
    if not isinstance(report['version'], int) or report['version'] < 2:
        errors.append('Invalid academic report version')
    for key in ('updated_at', 'evidence_cutoff'):
        try:
            date.fromisoformat(report[key])
        except (ValueError, TypeError):
            errors.append('Invalid '+key)
    if not isinstance(report['related_paper_ids'], list) or not all(isinstance(p, str) and p for p in report['related_paper_ids']):
        errors.append('Invalid paper IDs')
    refs = report['references']
    if not isinstance(refs, list) or not refs or not all(isinstance(r, dict) for r in refs):
        return errors + ['Missing references']
    ids = [r.get('id') for r in refs]
    if any(not isinstance(i, str) or not re.fullmatch(r'R\d+', i) for i in ids) or len(set(ids)) != len(ids):
        errors.append('Invalid reference IDs')
    ref_ids = set(i for i in ids if isinstance(i, str))
    for ref in refs:
        if set(ref) != {'id', 'title', 'publisher', 'year', 'url', 'kind'}:
            errors.append('Invalid reference fields')
        if not safe_source_url(ref.get('url', '')):
            errors.append('Unsafe reference URL')
        if not all(isinstance(ref.get(k), str) and ref[k].strip() for k in ('title', 'publisher', 'kind')):
            errors.append('Missing reference metadata')
    figures = report['figures']
    if not isinstance(figures, list) or not all(isinstance(f, dict) for f in figures):
        return errors + ['Invalid figures']
    figure_ids = [f.get('id') for f in figures]
    if any(not isinstance(i, str) or not re.fullmatch(r'F\d+', i) for i in figure_ids) or len(set(figure_ids)) != len(figure_ids):
        errors.append('Invalid figure IDs')
    valid_figure_ids = set(i for i in figure_ids if isinstance(i, str))
    for fig in figures:
        base_fields = {'id', 'reference_id', 'original_label', 'image_url', 'source_url', 'license'}
        if set(fig) not in (base_fields, base_fields | {'asset_path'}):
            errors.append('Invalid figure fields')
        if fig.get('reference_id') not in ref_ids:
            errors.append('Unresolved figure reference')
        if (not safe_source_url(fig.get('source_url', ''))
                or (not safe_asset_path(fig.get('asset_path', '')) and not safe_source_url(fig.get('image_url', '')))
                or ('asset_path' in fig and not safe_asset_path(fig['asset_path']))):
            errors.append('Unsafe figure URL')
        if not all(isinstance(fig.get(k), str) and fig[k].strip() for k in ('original_label', 'license')):
            errors.append('Missing figure attribution')
    locales = report['locales']
    if not isinstance(locales, dict) or set(locales) != set(LANGUAGES):
        return errors + ['Incomplete locales']
    baseline = None
    figure_citations = None
    for code in LANGUAGES:
        content = locales[code]
        if not isinstance(content, dict) or set(content) != {'title', 'direction', 'sections', 'figure_texts'}:
            errors.append(f'{code}: invalid locale fields')
            continue
        if not all(isinstance(content[k], str) and content[k].strip() for k in ('title', 'direction')):
            errors.append(f'{code}: missing title/direction')
        sections = content['sections']
        if not isinstance(sections, list) or not sections or not all(isinstance(s, dict) for s in sections):
            errors.append(f'{code}: missing sections')
            continue
        structure, placed = [], []
        for section in sections:
            if set(section) != {'id', 'title', 'markdown', 'figure_ids'}:
                errors.append(f'{code}: invalid section fields')
            sid = section.get('id', '')
            if not isinstance(sid, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', sid) or sid in FORBIDDEN_SECTIONS:
                errors.append(f'{code}: invalid academic section ID')
            body = section.get('markdown', '')
            if not isinstance(body, str) or not body.strip() or not section.get('title'):
                errors.append(f'{code}: empty section')
                continue
            citations = Counter(x[1] for x in REF_PATTERN.findall(body))
            if not set(citations) <= ref_ids:
                errors.append(f'{code}: unresolved citation')
            if has_unregistered_link(body):
                errors.append(f'{code}: unregistered body link')
            assigned = section.get('figure_ids', [])
            if not isinstance(assigned, list) or not all(isinstance(i, str) and i in valid_figure_ids for i in assigned):
                errors.append(f'{code}: invalid figure placement')
                assigned = []
            placed.extend(assigned)
            structure.append((sid, tuple(assigned), citations))
        if len({s.get('id') for s in sections}) != len(sections):
            errors.append(f'{code}: duplicate section IDs')
        if Counter(placed) != Counter(figure_ids):
            errors.append(f'{code}: figure coverage mismatch')
        if baseline is None:
            baseline = structure
        elif structure != baseline:
            errors.append(f'{code}: section/citation/figure parity mismatch')
        texts = content['figure_texts']
        if not isinstance(texts, dict) or set(texts) != valid_figure_ids:
            errors.append(f'{code}: missing figure text')
        else:
            citations_for_locale = {}
            for texts_for_figure in texts.values():
                if (not isinstance(texts_for_figure, dict) or set(texts_for_figure) != {'caption', 'interpretation'}
                        or not all(isinstance(t, str) and t.strip() for t in texts_for_figure.values())):
                    errors.append(f'{code}: empty figure interpretation')
            for fid, ft in texts.items():
                if not isinstance(ft, dict):
                    continue
                body = str(ft.get('interpretation', ''))
                citations = Counter(x[1] for x in REF_PATTERN.findall(body))
                citations_for_locale[fid] = citations
                if not set(citations) <= ref_ids:
                    errors.append(f'{code}: unresolved figure citation')
                if has_unregistered_link(body):
                    errors.append(f'{code}: unregistered figure link')
            if figure_citations is None:
                figure_citations = citations_for_locale
            elif figure_citations != citations_for_locale:
                errors.append(f'{code}: figure citation parity mismatch')
        serialized = json.dumps(content, ensure_ascii=False)
        if RAW_HTML.search(serialized) or PRIVATE_PATH.search(serialized):
            errors.append(f'{code}: unsafe report text')
        if code != 'zh' and HAN.search(serialized):
            errors.append(f'{code}: untranslated Chinese')
    return errors


def validate_library(library: dict, questions: list[dict], papers: list[dict], root: Path) -> list[str]:
    """Check a complete release against the actual question and paper archive."""
    if library.get('schema_version') != 2 or not isinstance(library.get('reports'), dict):
        return ['Invalid academic library']
    expected = {q['question_id']: q for q in questions}
    archive_paper_ids = {p['id'] for p in papers}
    reports = library['reports']
    errors = []
    if set(reports) != set(expected):
        errors.append('Academic library does not cover all research questions')
    for qid, report in reports.items():
        errors.extend(f'{qid}: {e}' for e in validate_report(report))
        q = expected.get(qid)
        if not q:
            errors.append(f'{qid}: unknown question')
            continue
        zh = report.get('locales', {}).get('zh', {})
        if (report.get('question_id') != qid or report.get('p') != q['p']
                or zh.get('title') != q['question'] or zh.get('direction') != q['direction']):
            errors.append(f'{qid}: mismatched question identity')
        # New analyses may cite an archived paper beyond its original question tags.
        if not set(report.get('related_paper_ids', [])) <= archive_paper_ids:
            errors.append(f'{qid}: missing paper archive link')
        for fig in report.get('figures', []):
            asset = fig.get('asset_path')
            if asset and (not safe_asset_path(asset) or not (Path(root)/asset).is_file()
                          or not (Path(root)/asset).resolve().is_relative_to((Path(root)/'assets/academic_figures').resolve())):
                errors.append(f'{qid}: missing or unsafe figure asset')
    return errors


def load_released_reports(root: Path) -> dict | None:
    folder = Path(root) / 'data' / 'academic_questions'
    manifest = folder / 'release.json'
    if not manifest.exists():
        return None
    release = json.loads(manifest.read_text(encoding='utf8'))
    expected = release.get('question_ids', [])
    if release.get('schema_version') != 2 or not expected or any(not re.fullmatch(r'P[1-7]-\d{3}', str(i)) for i in expected):
        raise ValueError('Invalid academic release manifest')
    available = {p.stem for p in folder.glob('P*-*.json')}
    if set(expected) != available or len(expected) != len(set(expected)):
        raise ValueError('Academic report coverage mismatch')
    reports = {}
    for qid in expected:
        report = json.loads((folder / f'{qid}.json').read_text(encoding='utf8'))
        errors = validate_report(report)
        if report.get('question_id') != qid:
            errors.append('Filename/question mismatch')
        if errors:
            raise ValueError(f'{qid}: '+ '; '.join(errors))
        reports[qid] = report
    library = {'schema_version': 2, 'reports': reports}
    try:
        corpus = json.loads((Path(root)/'data/cross_analysis.json').read_text(encoding='utf8'))
        errors = validate_library(library, corpus['questions'], corpus['papers'], root)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise ValueError('Missing or invalid academic release corpus') from exc
    if errors:
        raise ValueError('; '.join(errors))
    return library


def localize_report(report: dict, code: str) -> dict:
    if code not in LANGUAGES:
        raise ValueError('Unsupported report language')
    return {**{k: v for k, v in report.items() if k != 'locales'}, **report['locales'][code]}


def cited_markdown(body: str, references: list[dict]) -> str:
    if RAW_HTML.search(body) or PRIVATE_PATH.search(body) or has_unregistered_link(body):
        raise ValueError('Invalid report body')
    refs = {r['id']: r for r in references}
    def replace(match):
        label, rid = match.groups()
        ref = refs.get(rid)
        if not ref or not safe_source_url(ref['url']):
            raise ValueError('Unresolved citation '+rid)
        return f'[{label}]({ref["url"]})'
    return REF_PATTERN.sub(replace, body)


def figure_html(figure: dict, text: dict, reference: dict, root: Path | None = None) -> str:
    if not safe_source_url(figure['source_url']):
        raise ValueError('Unsafe figure')
    image_url = figure['image_url']
    if 'asset_path' in figure:
        if root is None or not safe_asset_path(figure['asset_path']):
            raise ValueError('Unsafe local figure')
        path = Path(root) / figure['asset_path']
        if not path.resolve().is_relative_to((Path(root) / 'assets' / 'academic_figures').resolve()):
            raise ValueError('Unsafe local figure')
        kind = 'jpeg' if path.suffix.lower() in ('.jpg', '.jpeg') else path.suffix.lower()[1:]
        image_url = f'data:image/{kind};base64,' + base64.b64encode(path.read_bytes()).decode('ascii')
    elif not safe_source_url(image_url):
        raise ValueError('Unsafe figure URL')
    esc = html.escape
    license_text = esc(figure['license'])
    license_match = re.fullmatch(r'CC BY(?:-(SA|NC|ND|NC-SA|NC-ND))? ([234]\.0)', figure['license'])
    if license_match:
        suffix, version = license_match.groups()
        code = 'by' + ('-' + suffix.lower() if suffix else '')
        license_text = f'<a href="https://creativecommons.org/licenses/{code}/{version}/" target="_blank" rel="noopener noreferrer">{license_text}</a>'
    return ('<figure class="aq-figure">'
            f'<a href="{esc(figure["source_url"], quote=True)}" target="_blank" rel="noopener noreferrer">'
            f'<img src="{esc(image_url, quote=True)}" loading="lazy" '
            f'alt="{esc(text["caption"], quote=True)}"></a>'
            f'<figcaption><strong>{esc(text["caption"])}</strong><br>'
            f'{esc(reference["title"])} · {esc(str(reference["year"]))} · '
            f'{esc(figure["original_label"])} · {license_text}</figcaption></figure>')


def header_html(report: dict, code: str) -> str:
    ui = UI[code]
    esc = html.escape
    toc = ''.join(f'<a href="#aq-{s["id"]}" target="_self">{esc(s["title"])}</a>' for s in report['sections'])
    return (f'<div class="aq-hero"><div class="aq-kicker">{esc(report["p"])} / '
            f'{esc(report["direction"])} / {esc(report["question_id"])}</div>'
            f'<h1>{esc(report["title"])}</h1><div class="aq-date">'
            f'{ui["updated"]}: {esc(report["updated_at"])} · {ui["cutoff"]}: {esc(report["evidence_cutoff"])}</div></div>'
            f'<nav class="aq-toc" aria-label="{ui["contents"]}">{toc}'
            f'<a href="#aq-sources" target="_self">{ui["sources"]}</a></nav>')


CSS = '''<style>
.st-key-academic_reader{max-width:1120px;margin:auto;color:#19374b}
.st-key-academic_reader .aq-hero{padding:28px 32px;border:1px solid #dbe8e8;border-radius:18px;background:linear-gradient(120deg,#e8f4f0,#eef3fb);margin:12px 0 22px}
.st-key-academic_reader .aq-hero h1{font-size:33px;line-height:1.45;margin:14px 0}
.st-key-academic_reader .aq-kicker,.st-key-academic_reader .aq-date{font-size:12px;color:#607d8b}
.st-key-academic_reader .aq-toc{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:24px}
.st-key-academic_reader .aq-toc a{padding:8px 12px;border:1px solid #dce6ed;border-radius:7px;text-decoration:none;background:#fff;font-size:13px}
.st-key-academic_reader [data-testid="stMarkdownContainer"]{line-height:1.95;overflow-wrap:anywhere}
.st-key-academic_reader [data-testid="stMarkdownContainer"] p{line-height:1.95;margin-bottom:1.15rem}
.st-key-academic_reader [data-testid="stMarkdownContainer"] table{display:block;overflow-x:auto;font-size:14px}
.st-key-academic_reader .aq-section{scroll-margin-top:90px;border-top:1px solid #dce6ed;padding-top:23px;margin-top:22px}
.st-key-academic_reader .aq-section h2{font-size:26px;line-height:1.5}
.st-key-academic_reader a{color:#107e77;text-underline-offset:3px}
.st-key-academic_reader .aq-figure{background:#fff;padding:20px;border:1px solid #dce6ed;border-radius:12px;margin:22px 0 10px}
.st-key-academic_reader .aq-figure img{display:block;width:100%;max-height:760px;object-fit:contain;margin:auto}
.st-key-academic_reader .aq-figure figcaption{font-size:12px;line-height:1.7;color:#647b8b;margin-top:15px;overflow-wrap:anywhere}
.st-key-academic_reader .aq-figure figcaption strong{font-size:15px;color:#19374b}
@media(max-width:700px){.st-key-academic_reader .aq-hero{padding:20px}.st-key-academic_reader .aq-hero h1{font-size:26px}.st-key-academic_reader .aq-section h2{font-size:23px}.st-key-academic_reader .aq-figure{padding:8px}.st-key-academic_reader .aq-toc a{font-size:12px}.st-key-academic_reader table th,.st-key-academic_reader table td{min-width:110px;overflow-wrap:normal;word-break:normal}.st-key-academic_reader table th:last-child,.st-key-academic_reader table td:last-child{min-width:240px}}
</style>'''


def academic_question_page(report: dict, question: dict | None, root: Path, public_mode=False) -> None:
    import streamlit as st
    from dashboard.i18n import language, preserve_original_text
    from dashboard.report_navigation import restore_question_context, open_report_paper
    code = language()
    ui = UI[code]
    r = localize_report(report, code)
    refs = {ref['id']: ref for ref in r['references']}
    figures = {f['id']: f for f in r['figures']}
    from dashboard.feedback_views import report_feedback
    report_feedback(report['question_id'], report['title'], 'question', root, public_mode,
                    version=report.get('updated_at', ''))
    with preserve_original_text():
        st.button(ui['back'], key='report_back', on_click=restore_question_context, args=(question,))
        st.html(CSS)
        with st.container(key='academic_reader'):
            st.html(header_html(r, code))
            for section in r['sections']:
                st.html(f'<div class="aq-section" id="aq-{section["id"]}"><h2>{html.escape(section["title"])}</h2></div>')
                st.markdown(cited_markdown(section['markdown'], r['references']))
                for fid in section['figure_ids']:
                    fig = figures[fid]
                    ft = r['figure_texts'][fid]
                    st.html(figure_html(fig, ft, refs[fig['reference_id']], root=root))
                    st.markdown(cited_markdown(ft['interpretation'], r['references']))
                    c1, c2 = st.columns(2)
                    c1.link_button(ui['figure']+' ↗', fig['source_url'])
                    c2.link_button(ui['source']+' ↗', refs[fig['reference_id']]['url'])
            st.html(f'<div class="aq-section" id="aq-sources"><h2>{ui["sources"]}</h2></div>')
            for ref in r['references']:
                st.markdown(f'**{ref["id"]} · {ref["publisher"]} · {ref["year"]}**')
                st.link_button(ref['title']+' ↗', ref['url'], width='stretch')
            if r['related_paper_ids']:
                data = json.loads((Path(root)/'data/cross_analysis.json').read_text(encoding='utf8'))
                papers = {p['id']: p for p in data['papers']}
                with st.expander(ui['papers']):
                    for pid in dict.fromkeys(r['related_paper_ids']):
                        if pid in papers:
                            st.button(papers[pid]['title'], key=f'report_paper_{pid}', on_click=open_report_paper, args=(pid,))
        if st.session_state.pop('report_scroll_to_top', False):
            st.html('''<script>requestAnimationFrame(()=>{const main=document.querySelector('[data-testid="stMain"]');if(main)main.scrollTo({top:0,behavior:'instant'});window.scrollTo({top:0,behavior:'instant'});});</script>''', unsafe_allow_javascript=True)

# Full Dashboard localization audit implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this audit and the independently delegated content reviews.

**Goal:** Find and directly fix omitted translations, incorrect specialist terminology and language-switch display defects across the English and German public dashboard, then publish and verify the changes.

**Architecture:** Keep source records and internal widget IDs stable. Correct reviewed static catalogues and the presentation translation layer; use separate patch maps for independent content reviews. Reuse the existing isolated release checkout and preserve unrelated local changes.

**Tech Stack:** Python, Streamlit, pandas, Plotly, static JSON catalogues, pytest, Streamlit AppTest, browser verification.

**Spec:** The user's request in this chat: inspect the entire English and German dashboard, fix findings directly and update the public site.

## Global constraints

- Preserve company names, paper titles, original paper/source excerpts and source URLs.
- Keep Chinese source records and paper/company counts unchanged.
- Include paper, enterprise, cross-analysis, question-report, direction-report and feedback pages, plus filters, tables, charts, downloads and navigation.
- Publish to the existing public website and synchronize the requested local project folder.

## Review focus

- Combined dynamic labels and whitespace must not leave Chinese fragments.
- Translation must preserve medical/manufacturing terms, names, numbers, negation and research stage.
- Language changes must retain internal filter values and navigation targets.
- Chart legends, annotations, hover text and table controls must match the selected language.
- Proper-name preservation must not suppress the translation of surrounding descriptions.

## Tasks

- [x] Establish baseline tests and inventory source strings, catalogues and page routes.
- [x] Audit enterprise prose and academic summaries/question reports in parallel; record explicit patches and review scope.
- [x] Capture all pages in both languages and scan rendered UI, tables and charts for omissions; reproduce language-switch failures before correcting them.
- [x] Add meaningful regression checks for confirmed failures, fix presentation/catalogue causes, and merge reviewed content patches.
- [x] Run catalogue integrity, name/link/number checks and page/navigation tests; inspect representative browser layouts in both languages.
- [x] Publish only scoped files, restart if required, verify the public pages and synchronize code plus review records locally.

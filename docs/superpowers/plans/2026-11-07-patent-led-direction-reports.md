# Patent-led direction reports implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development. Execute the authorized edits continuously and review the resulting reports before publication.

**Goal:** Remove the dashboard relationship graph and rebuild the three requested chapters in all 35 direction reports around specific patent mechanisms connecting research and enterprises.

**Architecture:** Preserve the existing Streamlit site, linked tables, patent charts and report identities. Rewrite static trilingual report bodies and references; rebuild the hash-validated association snapshot, export complete reports, and publish a fast-forward update to the existing deployment.

**Tech Stack:** Python, JSON, Streamlit, pytest; existing Espacenet links.

**Spec:** User request of 2026-11-07 in this chat. The user has delegated presentation and association judgments and requested removal of generic defensive copy.

## Global constraints
- All 35 directions, 113 questions and 318 existing research-pathway nodes remain addressable.
- Replace the chapters about academic/enterprise links, translation/validation, and 2027–2029 scenarios in the main report body, rather than only appending supplementary patent lists.
- Describe concrete disclosed patent schemes from held title/abstract metadata; cite publication IDs and source URLs. Do not invent claims, ownership transfers, collaborations, clinical outcomes or quantitative benchmarks.
- Research papers and enterprise sources retain original citations; new patent references are identical across Chinese, English and German.
- No OPS secret access, batch full-text download, new hosting service, or change to the 5,516-record source snapshot.

## Review focus
- Unsupported paper-to-company licensing or patent ownership assertions.
- Repetitive generic forecast/validation prose lacking direction-specific variables.
- Missing citations and inconsistent trilingual report structure.
- A low-coverage direction receives a fabricated direct patent link.
- The graph remains reachable or new report files fail association-hash validation after deployment.

## Tasks
- [x] Remove relationship graph tab, module, tests and packaging references while preserving linked tables and patent charts.
- [x] Rebuild P1/P2 report chapters from source packets; review evidence and citations.
- [x] Rebuild P3/P4 report chapters from source packets; review evidence and citations.
- [x] Rebuild P5/P6/P7 report chapters, explicitly handling sparse patent coverage.
- [x] Merge validated trilingual patches, rebuild association snapshot, and export complete direction reports with source links.
- [x] Run report, bridge, packaging and application checks; review semantic examples and browser rendering.
- [ ] Publish only intended files on the verified live main parent, refresh the deployment and verify live graph removal and rewritten chapters.

## Decisions and evidence ledger
- Existing isolated public-source worktree is reused; its externally managed HEAD is older than the live main tree. Publication must seed its temporary index from the verified live SHA, never local HEAD.
- Chinese is the primary readership; English and German pages retain equivalent content and citation placement.
- The first three chapters and research pathway are retained. Where an older report has a different chapter order, preserve its enterprise evidence while reconstructing the three requested conceptual chapters.
- Graph-removal regression failed against the original four tabs, then passed against the three retained list tabs. Browser preview independently showed Papers / Patent publications / Company profiles and the unchanged 7,169 / 5,516 / 352 counts.
- Main-chapter acceptance check failed on the original report body (no patent references), while complete HTML export smoke checks passed for all 35 directions in three languages. Full verification follows the editorial merge.
- Independent review covered all 35 Chinese triplets and selected translations against held patent abstracts and original academic/company evidence. Corrections restored model-side tooth preparation, physical try-in correction followed by machining, direct antimicrobial endpoints, exact applicant naming and translated technical objects. The FDA source was checked on its official page; its March 2026 draft status is preserved and proposed screening comparisons are attributed to this report.
- Full offline association rebuild completed with unchanged 7,169 papers / 5,516 patents / 352 companies / 148 scopes. Subsequent paragraph-only edits were checked against every actual direction matching input (localized title/thesis/ordered question IDs), all other source and rule digests, and the unchanged snapshot hash before refreshing the three report-file provenance digests; the normal loader then passed.
- Fresh 818-file LF-normalized public package passed validation. Complete HTML export produced 35 directions in three languages (105 pages). The local browser displayed the rebuilt main chapters with working patent citation targets and readable two-column tables.
- Final regression: 165 tests passed in 274.03 seconds. Final candidate-tree review found no important or blocking issues; original identities, 113 questions, 318 pathway nodes, protected chapters, reference provenance and unchanged matching rules were verified. Candidate Git report blobs match the portable provenance digests.

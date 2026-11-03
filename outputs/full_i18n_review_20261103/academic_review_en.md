English academic localization audit — 2026-11-03

The deliverable is `academic_patches_en.json`: **732 exact Chinese-source → corrected-English mappings**, ready for the parent agent to merge into `data/i18n/en.json`. No shared catalogue, application code, Chinese records, paper classifications, references, titles, or DOI fields were edited by this work.

The review used the source Chinese, existing English, and actual precedence in `dashboard/i18n.py`: protected strings first, then English overrides, then the catalogue, then Chinese-span lookup. Existing 35 direction-report translations were excluded from re-audit. Enterprise-evidence and context records were excluded except where needed to understand a question report.

Scope and evidence:

| Material | Complete systematic scan |
|---|---:|
| Research questions | 113 |
| Paper/question associations | 6,722 |
| Distinct Chinese paper summaries | 4,286 |
| Existing question reports | 113 |
| Unique report-prose Chinese spans | 5,844 |
| Total unique academic Chinese spans | 10,243 |
| Rendered report sections validated | 678 |

All 113 question pairs were read. Paired semantic reading covered core findings and flagged passages across **all seven P domains**, including implant interfaces and lattices, restorative dentistry and prosthetic sockets, pharmaceutical formulation and release, surgical guides, protective equipment, training/imaging phantoms, microfluidics and tissue models. This was combined with complete all-entry scans of numbers, Latin identifiers, drug/material terms, study designs, negation, chronology, false future tense, and suspicious specialist translations. It is not a claim that all 4,286 distinct summaries received a full independent line-by-line literature review.

The controlled material/drug/study-design scan evaluated **1,079 term occurrences**. It included PEEK, PLA, PCL, hydroxyapatite, chitosan, alginate, gelatin/GelMA and methacrylate, plus named drugs such as dexamethasone, vancomycin, paracetamol, ibuprofen, warfarin, isoniazid, rifampicin, amlodipine, metformin, levetiracetam, prednisolone, diclofenac, nifedipine, hydrochlorothiazide, theophylline, caffeine, carbamazepine, fluorouracil, doxorubicin, paclitaxel, methotrexate and insulin. The first-pass 38 flags included harmless alternatives such as “in mice” for “in vivo”; they were evaluated in context rather than replaced blindly.

Across the 4,286 summary pairs, all-entry Latin-token comparison produced only two apparent missing-token flags: a harmless raspberry/raspberries inflection and NF-κB typography. Numeric scans separately checked 188 initial mismatches, most explained by spelled-out English numbers, 三维→3D, 新冠→COVID-19, or Chinese large-number units. One genuine omitted summary dimension, **3.0 mm**, was restored. Two corrupt source numbers were resolved using primary papers, as described below.

The final patch distribution is **3 question labels, 159 distinct summaries, 566 report spans, and 4 complete report sections**. Among report spans, **494 date continuations** were normalized, including **121 with invented dates**. Date numerals already sit outside the Chinese catalogue span in the original Markdown: translating `年研究…` as `A 2016 study…` fabricated a second, often wrong, year. The patch removes the fabricated year while retaining the original source year. It also removes erroneous annual/year-round/year-long interpretations and “Nian” as a supposed person’s name.

Representative semantic findings:

| Source meaning / context | Existing English error | Correction |
|---|---|---|
| A study following an explicit source year | A different invented year, often 2016/2017/2019 | Keep only the source Markdown year |
| Completed 2023/2026 experiments | “will include”, “will use” | Completed study wording |
| 枫糖尿病 | Maple Diabetes / maple syndrome | Maple syrup urine disease |
| 多巴唑嗪, title identifies doxazosin | dobazosin | Doxazosin |
| 尼福替莫, title identifies nifurtimox | niformimol | Nifurtimox |
| 尼卡唑纳米晶, title identifies niclosamide | nicazole | Niclosamide nanocrystals |
| Airway-stent antifibrotic drug | netidinib | Nintedanib |
| Tablet mass, weighing and mass uniformity | quality / quality loss | Mass / mass loss / mass uniformity |
| 对物体的无视觉识别 | visual recognition | Object recognition without vision |
| 无堵塞泄漏 in microchannels | non-clogging and leakage | Without clogging or leakage |
| 45 imaging/training model summaries | prosthesis/prostheses | Phantom/phantoms, checked against the corresponding supplied titles |
| 假肢套筒 / 接受腔 | prosthetic sleeve | Prosthetic socket |
| 体动上肢假肢 | body-moving | Body-powered |
| RPD 支架 | bracket / stent | Removable partial denture framework |
| Dental 卡环 | snap ring / retaining ring | Clasp |
| Bone/tissue-regeneration 支架 | vascular stent | Scaffold |
| Printing 丝材 | silk | Filament; genuine silk fibroin preserved |
| 防飞溅面罩 / face-shield paper titles | mask / face mask | Face shield; respiratory masks remain distinct |
| Face-shield 醋酸片 | acetic acid sheets | Acetate sheets |
| 组织 in biological context | organization / organizational | Tissue; microstructure in the alloy context |
| 内、外体吸收 heading | absorption from outside the body into the body in a timely manner | From in vitro release timing to in vivo absorption |
| 前瞻性产品比较 | forward-looking product comparison | Prospective product comparison |
| 幼恒牙根尖栓塞 / 牙髓切断 | apical embolization / pulp cutting | Apical plug placement / pulpotomy |
| Fluoroscopic cardiovascular/spine imaging | fluorescence imaging | Fluoroscopic imaging |
| Surgical 自由操作 | free operation | Freehand technique |

AM taxonomy and P/D/T/M meanings were checked as **presentation terminology**, with no recoding. Examples include fused deposition modeling, fused filament fabrication, scaffold versus vascular stent, dental framework versus orthodontic bracket, and phantom versus implanted prosthesis. A report passage that said only 光固化打印 was changed from an unnecessarily specific stereolithography claim to photopolymerization printing. Existing canonical taxonomy overrides for vat photopolymerization, material extrusion, powder bed fusion, material jetting, binder jetting, directed energy deposition, sheet lamination, material families and disease categories were inspected and retained.

The shared catalogue key `将` has several meanings and cannot safely be changed globally. Four **whole-section** patches reconstruct complete context instead: P1-008 industry, P2-023 industry, P3-057 industry, and P7-110 academic chain. These fix orphaned product/technology phrases, completed versus future actions, and the 28-day release target without affecting unrelated uses of `将`.

Override-level conflicts: **none found for the submitted English academic patches**. Six override-backed academic source strings occurred in the inventory and were inspected. Their existing translations were retained. The patch for the identical original research/direction/taxonomy labels therefore does not attempt to override higher-precedence code values.

Primary-paper checks resolved specialist ambiguity:

- Doxazosin: [author institution’s paper record](https://discovery.ucl.ac.uk/id/eprint/10207749/) confirms the drug identity for DOI `10.1007/s13346-025-01862-4`.
- Nifurtimox and benznidazole: [original paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11768318/) confirms 120/60 mg tablets, 2.8-fold dissolution efficiency and the benznidazole comparator. The supplied record has an underlying DOI/title mismatch: its DOI `10.3390/pharmaceutics14091822` refers to a different paper; the matching article has DOI `10.3390/pharmaceutics17010080`. The record DOI was left untouched.
- Niclosamide: [original paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC10220711/) confirms the drug and 180-minute canine gastroretention.
- Nintedanib: the [author institution’s original-paper PDF](https://www.research-collection.ethz.ch/server/api/core/bitstreams/250194b6-6a59-4732-acc4-de09f5c1d1d6/content) confirms the antifibrotic drug alongside levofloxacin.
- Sacrificial PVA channels: [original paper](https://www.nature.com/articles/s41598-018-21638-w) confirms **40 μm × 300 μm**. The Chinese source has `40 μm×30及`, while existing English invented `30 mm`. English was corrected from the primary paper; the Chinese source remains unchanged.
- Salivary uric acid: [original publisher article](https://pubs.acs.org/doi/full/10.1021/acsmeasuresciau.6c00046) confirms **0.09 μM in buffer and 0.1 μM in saliva**. The Chinese source has the corrupt decimal `0及1`; existing English displayed `0 and 1`. English was corrected; the source field remains unchanged.
- A complete-denture narrative-review source has `完全可摘局部义齿`, mixing complete and partial denture terms. The associated supplied English paper title identifies complete removable dental prostheses; the English summary follows that context and retains its stated clinical limitations. No classification was changed.

Validation was actually executed with `validate_academic_en.py` against the application’s effective translation function, using the patch merged **in memory**. Result: **0 errors**. The check covers all 732 entries for nonempty English, Chinese-character leakage, effective lookup, overriding-code conflicts, reference IDs and URLs, plus all 678 report sections for remaining Chinese, reference correspondence and Markdown-table structure. There are no remaining fabricated dates, annual/year-long interpretations, or Nian artifacts in scanned report date continuations. The output is recorded in `academic_validation_en.json`; paired rendered report text is available in `academic_effective_reports_en.json` for further review.

The bibliography/source-data anomalies above remain separate from translation scope. Publication, shared merge and site-level browser verification are the parent agent’s responsibility.

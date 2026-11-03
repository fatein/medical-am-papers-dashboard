# German academic localization review — 2026-11-03

## Deliverable and scope

`academic_patches_de.json` contains **726 existing Chinese catalogue keys → corrected German strings**. It is a merge-ready patch map, not a replacement catalogue. No shared catalogue, application code, Chinese records, paper classifications, English translations or direction reports were edited.

The audit used the Chinese source fields together with the **effective output of `dashboard.i18n.tr`**, including its override-before-catalogue precedence and Chinese-span substitution. This matters because report Markdown is not translated as an intact paragraph: dates, quantities, English identifiers and references often sit outside the translated Chinese spans.

Coverage:

| Source | Systematic coverage | Semantic reading |
|---|---:|---|
| `cross_analysis.questions` | 113 questions; 226 question/direction fields | All 113 question titles read against effective German; all P1–P7 domains covered |
| `cross_analysis.papers` | 6,722 linked rows; 4,286 distinct Chinese summaries; 606,544 Chinese characters across rows | Targeted paired reading of numeric/name/technical/prose flags across P1–P7; 75 distinct summaries corrected, affecting 121 linked rows |
| `question_reports` | All 113 reports; 791 fields (113 core findings plus 678 section bodies); 210,837 Chinese characters | All 113 core findings read in pairs; flagged academic chains, scope paragraphs, tables, captions/link labels and outlook statements read in context |
| Report catalogue coverage | 5,845 distinct relevant keys: 5,732 extracted report spans plus 113 direct core-finding keys | Chronology and terminology checks applied to every matched key |
| Existing 35 direction reports | Excluded | Previously reviewed; not re-audited |

This is **not a claim that all 4,286 distinct paper summaries or all 678 report sections received an unassisted sentence-by-sentence human-equivalent reading**. The complete set received systematic scanning; semantic reading concentrated on the full question/core-finding set and flagged specialist prose.

Initial summary scans produced 470 linked-row invariant flags (293 distinct summaries), narrowed numerical flags to 31 distinct summaries after removing most identifier/thousands-format false positives, 57 specialist-term flags, and 35 prose-language flags. False positives such as `MRI → MRT`, `CFU → KBE`, numbers written out in German, and valid vascular stents/orthodontic brackets were inspected rather than blindly replaced.

## Material findings corrected

### Chronology, stage and numerical meaning

The largest systemic error came from numeric years outside Chinese spans. For example, the source `2019 年异亮氨酸…` rendered as `2019 Die Studie aus dem Jahr 2016…`; `2025 年泼尼松…` rendered with an additional 2010. Across the patched year-leading fragments, **121 original translations contained invented Arabic year values**, and **173 interpreted 年 as annual/year-long wording**. The latter falsely implied repeated studies, annual regulatory events, or annual product launches.

Year-leading translations now use the original external date followed by a neutral dash and the study/event description. No replacement date is introduced. Additional year-leading fragments were normalized so external years do not run straight into capitalized prose. The former `全激光 → ganzjährige Laserforschung` was also corrected to an exclusively laser-based workflow.

Concrete numerical and design corrections include:

- **100 cycles at 500 kPa:** the original German merged this into `100.500 kPa-Druckzyklen`. The corrected sentence explicitly states `100 Druckzyklen bei 500 kPa`.
- **59% hydrogen peroxide:** the concentration disappeared from a mask-filter summary; it is restored without altering the reported ten treatment cycles.
- **Detection limit direction:** summaries described improved sensitivity as a detection limit that was 19 or 21 times *higher*. The German now describes improvement of the detection limit, retaining the given 7.4 pg/mL and <1 parasite/μL values and avoiding an unsupported re-estimation of the ratio.
- **Change versus absolute value:** a denture trial's greater *increase in retention over three months* was translated as greater absolute retention; the corrected German retains the change endpoint and the non-significant overall time comparison.
- **Training versus surgery:** resident performance assessed before/after simulation training was described as before/after surgery; the intervention and assessment sequence are corrected.
- **Preclinical versus clinical:** an in-vitro bioavailability prediction is explicitly described as a prediction, rather than an established clinical bioavailability result. Animal model species and study designs remain explicit.
- **Observed null result:** the magnetically triggered implant report had garbled the distinction between releasing a peptide and changing osteoimmune behavior. The correction preserves that no measured osteoimmunomodulatory change occurred at tested concentrations, and preserves the proposed controls.

### Specialist materials, anatomy and mechanics

- Prosthetic sockets were variously `Steckdose`, `Wadenpfanne`, `Oberschenkelpfanne`, or generic bases. They are now described as appropriate **Prothesenschäfte**. A comparator error that compared the healthy leg to the healthy leg is corrected to the prosthetic versus healthy limb.
- Tissue-engineering and bone-regeneration **scaffolds** were mislabeled as vascular **Stents**. Targeted corrections distinguish Gerüste/Trägerstrukturen from genuine aortic, carotid and TIPS stents. No global `Stent` replacement was made.
- Dental partial-denture frameworks were confused with orthodontic **Brackets**. Gerüste, Auflagen, Klammern and Pfeilerzähne are differentiated; actual orthodontic brackets were retained.
- Surgical guides were translated as documents (`Leitfäden`, `Anleitungen`) and their clinical studies as guideline studies. The corrections restore surgical **Schablonen** and the relevant positioning task.
- Radius-positioning **translation errors** were rendered as linguistic `Übersetzungsfehler`; these are now **Translationsfehler**. Kaudal hooks and cross-bracing are distinguished from tail hooks and polymer crosslinking.
- `Enophthalmus` was mistranslated as `Enotropie`; the orbit-floor reconstruction summary now describes the correct finding.
- Dogs of toy breeds were called `Spielzeughunde`; this is corrected to **Hunde aus Zwergrassen**.
- Surgical **exposure** was called `Belichtung`; operative Freilegung is restored. Extra-articular hip resection is distinguished from an “external” resection.
- A diathermy-compatible cholecystectomy trainer was called electrotherapeutic and its cystic artery a `Zystenarterie`; the correction describes the Arteria cystica and electrosurgical training.
- Moulds were translated as **Schimmelpilze**; casting forms and photos of forms are restored.
- Pull-out resistance was called **Prolapswiderstand**; it is now **Auszugsfestigkeit/Auszugskraft**.
- Material toughness was confused with strength; source-specific passages now retain **Zähigkeit**. Milling is distinguished from `Mühle`, intraoral cementation/passung from adhesion where required, and tablet mass from a generic quality attribute.

### Drugs, release terminology and orphan fragments

- Ahornsirupkrankheit was rendered `Ahornsirupitis`, `Ahornsyndrom` or `Maple-Diabetes`; the disease name is corrected without changing the source study design.
- Nifurtimox and Niclosamid are restored using the attached publication titles to disambiguate erroneous transliterations. Compound formulas and experimental identifiers such as Ti6Al4V, PCL, PLGA, PEGDA, mPCL, HSA/TA, O157:H7 and named products are retained.
- Pharmaceutical drug screening/tests and diazepam tapering were translated using illicit-drug language. They are now Wirkstoffscreening, Wirkstofftests and dose reduction before discontinuation. Genuine forensic illicit-drug detection remains unchanged.
- Sustained release, immediate release, dissolution and disintegration are differentiated where their confusion changed the scientific meaning. Regulatory batch release (`Freigabe`) is not treated as drug release (`Freisetzung`).
- Film dosage forms, tube administration, low-temperature microtablets and individual-tablet quality comparisons had been confused with film agents, enteral feeding formulations, microchips and layer-by-layer comparisons.
- Mixed English/German summaries were rewritten in German, preserving the publication title field itself. Numeric fragments and orphan link labels such as `Sharding`, `Spendemethoden`, `Organisation` for tissue, and `Veröffentlichung` for drug release were corrected in context.

## Taxonomy and override precedence

The P/D/T/M labels and direction names in `_OVERRIDES['de']` were inspected as the effective labels. No change to underlying P/D/T/M codes, paper memberships, AM-process classifications or source medical-application categories is included. In particular, “scaffold” was not globally remapped to a P category, and Multi Jet Fusion was not reclassified merely because its name contains “Jet”.

**Override conflicts for the 726 proposed keys: 0.** The companion `academic_override_conflicts_de.json` is `{}`. The validator also asserts that no proposed key is masked by a current German override.

One globally ambiguous catalogue key is deliberately not changed: standalone Chinese **`组织` currently maps to `Organisation`**. In academic tissue contexts it should be `Gewebe`; elsewhere it can mean organization/organizing. Longer tissue-specific spans have been corrected here. A future context-aware treatment of the standalone key is safer than a universal replacement. This is a catalogue-context ambiguity, not an override conflict.

## Source ambiguities left for source-data review

These were not silently “repaired” in Chinese or reclassified:

- The pediatric-tablet source contains **`丙丙醇`**, translated literally as Propylalkohol. It is likely a source transcription problem, but the intended active ingredient must be verified before changing it.
- The Nifurtimox summary's comparator is **`苯甲酸肼`**. The patch corrects the unambiguous Nifurtimox name from the attached title but retains the source comparator as Hydrazinbenzoat; deciding whether the source intended another antitrypanosomal medicine requires source-paper verification.
- **Ti6Al44V** appears in a Chinese source summary. The source identifier was preserved rather than silently normalized to Ti6Al4V.
- Some Chinese descriptions themselves combine “complete” and “partial” denture wording or contain questionable drug/material spellings. Translation edits do not establish a new scientific classification or erase these source uncertainties.

## Actual validation and merge instructions

Ran the scoped builder and `validate_academic_de.py` successfully against the release directory. Validation applies the patch map **in memory** to the real `tr` pathway; it does not edit the shared catalogue.

Results:

| Check | Result |
|---|---:|
| Patch entries | 726 |
| Changed research-question fields | 14 |
| Changed linked paper-summary fields | 121 |
| Changed report prose fields | 246 |
| Distinct question reports affected | 113 / 113 |
| Original report year values retained | Pass |
| Changed Markdown reference-ID sequences retained | Pass |
| Changed URLs retained | Pass |
| Chinese characters in changed rendered German fields | 0 |
| Non-catalogue patch keys | 0 |
| Empty/non-string patch values | 0 |
| Override conflicts | 0 |

Changed fields by P domain: P1 64, P2 80, P3 69, P4 66, P5 30, P6 26, P7 46.

Useful companion files: `academic_validation_de.json`, `academic_changed_pairs_de.json`, `academic_patch_reasons_de.json`, and `academic_override_conflicts_de.json`. The full paired inventory and intermediate flag files document the scan scope. The helpers read only shared inputs and write within this review-output directory.

Merge the final patch map into the German catalogue with normal review of overlap against other agents' maps. The patch map includes fragments that can also appear in enterprise prose within the 113 question reports, especially chronological fragments and shared labels. Those corrections preserve the original dates and remain appropriate where reused. No publication or browser verification was performed by this subagent; deployment and final integration belong to the parent task.

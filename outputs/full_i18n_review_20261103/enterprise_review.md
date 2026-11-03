# Enterprise English/German localization review — 2026-11-03

Scope: 352 company records, 117 event records, 398 observation records, 168 cross-analysis enterprise-evidence records and 10 context records. No `enterprise_cross_additions.json` is present in this checkout; additions are already consolidated in the company data. No shared catalogue, code, source record or direction-report file was changed by this audit.

The deduplicated inventory contains 1,469 Chinese-bearing strings: 663 company descriptions, 260 event values, 387 observation-specific variants, 130 enterprise-evidence values and 29 context values. Five source keys were absent from each translation catalogue. Outputs contain 331 English patches and 446 German patches, including all five absent keys per language.

Coverage method: company descriptions, event values and enterprise evidence/context were compared in grouped Chinese/English/German reading batches. Observation variants were inventoried in full, reconciled against their complete company descriptions where they differ only by whitespace or final punctuation, scanned for terminology/stage/tense/encoding/length anomalies, and subjected to targeted paired reading. These 387 variants should not be described as 387 independently rewritten full prose records. Repeated terms were corrected only under source-string guards. Existing 35 direction reports were left untouched.

Concrete corrections include:

- cervical spinal fusion rendered as uterine cervix / cervical cancer in German, including a dangerous fabricated cancer indication in an observation prefix;
- prosthetic sockets rendered as electrical sockets; orthopaedic orthoses rendered as dental braces; surgical guides rendered as manuals or guides to read;
- multi-material jetting changed to injection or spraying, subperiosteal implants changed to periosteal implants, cementless knee prostheses changed to bio-based/artificial biological knees;
- complete product descriptions lost after the words Quantum or LUMEN, including CELLINK/LUMEN X Gen 3, Quantum X bio and cross-analysis evidence;
- historical launches changed into future plans or imperatives; restored source tense while retaining actual planned launches;
- missing limiting sentences for ROSA (3D does not mean 3D printing), Kumovis (product-line continuation is not a newly approved device), Laxxon (development rather than approved medicines), VisionAir indication and Enovis entity consolidation;
- German absence-of-AM-evidence incorrectly asserted as positive evidence that AM is not used;
- prescription compounding confused with drug delivery, extemporaneous medicines described as improvised medicines, mass uniformity confused with drug-content uniformity;
- restored literal Chinese company names and Chinese registration identifiers where translations invented different names or nonsensical administrative labels; preserved English brands such as SABER-C, Brinter, Nexocyte, AI Design and optiprint.

Presentation root causes for root implementation:

1. `build_observations` creates current titles with raw Chinese `[:100]` and year clues with `[:160]`; these can split Formlabs, PEEK, clinical qualifiers and clauses. Translating the partial string creates orphan fragments or fabricated completions. Prefer deriving a title from the complete translated summary, then shorten at a word boundary with an ellipsis. Targeted critical prefix errors are patched, but this underlying title construction merits a shared-code fix.
2. `tr` correctly checks full catalogue values before segment fallback. Patch keys must remain exact source strings. Names can be protected as whole values, but full prose needs literal name preservation too.
3. FDA 510(k) language should consistently distinguish clearance / Freigabe / substantial equivalence from approval. Source quotations denying an FDA approval claim must retain that negation.
4. The GRAPE S2 event is inconsistent with its own profile: the profile labels 2026 launch as a plan, while the event source says launch. Existing future wording was intentionally retained. Current official Copner website lists the GRAPE S1 extrusion platform, not a dated completed S2 launch. A Copner-attributed 6 November 2023 release describes S2 as an Innovate UK-funded project. This is insufficient to establish a completed 2026 S2 launch, and source data were not altered.

GRAPE sources checked:
- Official current company website: https://www.copnerbiotech.com/
- Official 4D extrusion product page: https://www.copnerbiotech.com/4dExtPrt.html
- Copner-attributed release: https://www.labmate-online.com/news/laboratory-products/3/copner-biotech-ltd/cutting-edge-bioprinter-redefines-biofabrication/61535

Validation: both patch maps parse as JSON; all keys belong to the scoped inventory; all values are nonempty strings; no replacement character or MISSING sentinel remains in the patches; new absent source keys are translated. No runtime/browser test was performed by this subagent. Root handles merge, runtime checks and publication.

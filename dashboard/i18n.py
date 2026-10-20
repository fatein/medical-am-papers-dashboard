"""Presentation-only language support for the public dashboard.

The original records remain untouched.  Translations are generated ahead of
deployment and looked up when Streamlit renders a user-facing value.
"""
from __future__ import annotations

import json
import re
from contextvars import ContextVar
from contextlib import contextmanager
from functools import lru_cache, wraps
from pathlib import Path

_LANGUAGES = {'zh': '中文', 'en': 'English', 'de': 'Deutsch'}
_HAN = re.compile(r'[\u3400-\u9fff]')
_SEGMENT = re.compile(r'[\u3400-\u9fff]+(?:[ \t，。！？、／·：；（）“”「」…％%\-]+[\u3400-\u9fff]+)*')
_ACTIVE: ContextVar[str] = ContextVar('am_dashboard_language', default='zh')
_ROOT: ContextVar[Path | None] = ContextVar('am_dashboard_root', default=None)
_PROTECTED: set[str] = set()
_OVERRIDES = {
    'en': {
        '论文总览': 'Paper overview',
        '研究结构与趋势': 'Research structure & trends',
        '论文检索': 'Search papers',
        '学术与企业联系': 'Research & industry',
        '企业格局': 'Company landscape',
        '技术路线图': 'Technology roadmap',
        '企业检索': 'Search companies',
        '数据更新': 'Data updates',
        '研究方向': 'Research direction',
        '研究问题': 'Research question',
        '医疗对象': 'Medical application',
        '论文名称': 'Paper title',
        '论文数': 'Papers',
        '关联论文': 'Related papers',
        '有来源的企业': 'Companies with sources',
        '发表年份': 'Publication year',
        '制造工艺': 'Manufacturing process',
        '材料': 'Material',
        '疾病／应用': 'Disease / application',
        '查看分析报告 →': 'Read analysis report →',
        '查看论文详情与 DOI': 'View paper details and DOI',
        '在企业档案中检索': 'Find in company profiles',
        '查看企业资料来源 ↗': 'View company source ↗',
        '打开 DOI 原文入口 ↗': 'Open DOI source ↗',
        '国家／地区': 'Country / region',
        '企业／产品／技术检索': 'Search companies / products / technologies',
        '重置筛选': 'Reset filters',
        '重置企业筛选': 'Reset company filters',
        '学术趋势观察台': 'Research trends dashboard',
        '公开 · 开源 · 免费': 'Public · open source · free',
        '医疗增材制造 / 论文研究项目': 'Medical additive manufacturing / research project',
        '医疗增材制造': 'Medical additive manufacturing',
        '增材制造': 'Additive manufacturing',
        '篇': 'papers',
        '历史': 'Historical',
        '从研究产出到研究结构，观察医疗增材制造的学术演变':
            'Explore how medical additive manufacturing research has evolved in output and focus',
        '问题与应用场景': 'Research question and applications',
        '学术研究链路': 'Academic research pathway',
        '学术变化趋势': 'Research trends',
        '企业技术与产品演变': 'Evolution of company technologies and products',
        '学术与企业的实际联系': 'Links between research and industry',
        '未来判断与观察指标': 'Outlook and indicators to watch',
        '来源与相关档案': 'Sources and related records',
        '报告目录': 'Report contents',
        '更新于': 'Updated',
        '资料截至': 'Sources current to',
    },
    'de': {
        '论文总览': 'Publikationsübersicht',
        '研究结构与趋势': 'Forschungsstruktur und Trends',
        '论文检索': 'Publikationen suchen',
        '学术与企业联系': 'Forschung und Industrie',
        '企业格局': 'Unternehmenslandschaft',
        '技术路线图': 'Technologie-Zeitachse',
        '企业检索': 'Unternehmen suchen',
        '数据更新': 'Datenaktualisierung',
        '研究方向': 'Forschungsrichtung',
        '研究问题': 'Forschungsfrage',
        '医疗对象': 'Medizinischer Anwendungsbereich',
        '论文名称': 'Publikationstitel',
        '论文数': 'Publikationen',
        '关联论文': 'Zugeordnete Publikationen',
        '有来源的企业': 'Unternehmen mit Quellen',
        '发表年份': 'Erscheinungsjahr',
        '制造工艺': 'Fertigungsverfahren',
        '材料': 'Material',
        '疾病／应用': 'Erkrankung / Anwendung',
        '查看分析报告 →': 'Analysebericht lesen →',
        '查看论文详情与 DOI': 'Publikationsdetails und DOI ansehen',
        '在企业档案中检索': 'Im Unternehmensprofil suchen',
        '查看企业资料来源 ↗': 'Unternehmensquelle öffnen ↗',
        '打开 DOI 原文入口 ↗': 'DOI-Quelle öffnen ↗',
        '国家／地区': 'Land / Region',
        '企业／产品／技术检索': 'Unternehmen / Produkte / Technologien suchen',
        '重置筛选': 'Filter zurücksetzen',
        '重置企业筛选': 'Unternehmensfilter zurücksetzen',
        '学术趋势观察台': 'Dashboard für Forschungstrends',
        '公开 · 开源 · 免费': 'Öffentlich · Open Source · kostenlos',
        '医疗增材制造 / 论文研究项目': 'Additive Fertigung in der Medizin / Forschungsprojekt',
        '医疗增材制造': 'Additive Fertigung in der Medizin',
        '增材制造': 'Additive Fertigung',
        '篇': 'Publikationen',
        '历史': 'Historische Daten',
        '从研究产出到研究结构，观察医疗增材制造的学术演变':
            'Entdecken Sie, wie sich Umfang und Schwerpunkte der Forschung zur additiven Fertigung in der Medizin entwickelt haben',
        '问题与应用场景': 'Forschungsfrage und Anwendungen',
        '学术研究链路': 'Wissenschaftlicher Forschungsweg',
        '学术变化趋势': 'Forschungstrends',
        '企业技术与产品演变': 'Entwicklung von Unternehmenstechnologien und Produkten',
        '学术与企业的实际联系': 'Verbindungen zwischen Forschung und Industrie',
        '未来判断与观察指标': 'Ausblick und Beobachtungsindikatoren',
        '来源与相关档案': 'Quellen und zugehörige Einträge',
        '报告目录': 'Inhaltsverzeichnis',
        '更新于': 'Aktualisiert',
        '资料截至': 'Quellenstand',
    },
}
_DIRECTIONS = {
    '个人防护用品': ('Personal protective equipment', 'Persönliche Schutzausrüstung'),
    '个体化口服制剂': ('Personalized oral dosage forms', 'Personalisierte orale Darreichungsformen'),
    '个体化植入物': ('Patient-specific implants', 'Patientenspezifische Implantate'),
    '临床比较': ('Clinical comparisons', 'Klinische Vergleiche'),
    '临床流程与结局': ('Clinical workflows and outcomes', 'Klinische Abläufe und Behandlungsergebnisse'),
    '义齿精度与体验': ('Denture fit and patient experience', 'Passgenauigkeit von Zahnersatz und Patientenerfahrung'),
    '义齿连接与一体化': ('Denture bonding and monolithic fabrication', 'Verbindung und einteilige Fertigung von Zahnersatz'),
    '低成本实验室设备': ('Low-cost laboratory equipment', 'Kostengünstige Laborgeräte'),
    '体外细胞与组织模型': ('In vitro cell and tissue models', 'In-vitro-Zell- und Gewebemodelle'),
    '修复体材料与耐久': ('Restorative materials and durability', 'Restaurationsmaterialien und Haltbarkeit'),
    '假肢与矫形器': ('Prostheses and orthoses', 'Prothesen und Orthesen'),
    '假肢接受腔': ('Prosthetic sockets', 'Prothesenschäfte'),
    '光学与显微成像': ('Optical and microscopic imaging', 'Optische und mikroskopische Bildgebung'),
    '多孔植入物与晶格设计': ('Porous implants and lattice design', 'Poröse Implantate und Gitterstrukturen'),
    '定制手术器械': ('Custom surgical instruments', 'Patientenspezifische chirurgische Instrumente'),
    '导板稳定与安全': ('Surgical guide stability and safety', 'Stabilität und Sicherheit chirurgischer Schablonen'),
    '导板精度': ('Surgical guide accuracy', 'Genauigkeit chirurgischer Schablonen'),
    '应急供应与制造': ('Emergency supply and manufacturing', 'Notfallversorgung und Fertigung'),
    '微流控芯片': ('Microfluidic chips', 'Mikrofluidische Chips'),
    '微针递送': ('Microneedle delivery', 'Mikronadelbasierte Wirkstoffabgabe'),
    '快速检测与传感': ('Rapid diagnostics and sensing', 'Schnelldiagnostik und Sensorik'),
    '打印质量与稳定性': ('Print quality and stability', 'Druckqualität und Stabilität'),
    '放疗体模与质控': ('Radiotherapy phantoms and quality assurance', 'Strahlentherapie-Phantome und Qualitätssicherung'),
    '教学与沟通': ('Education and communication', 'Ausbildung und Kommunikation'),
    '术前规划模型': ('Preoperative planning models', 'Modelle für die präoperative Planung'),
    '植入与局部递送': ('Implants and local delivery', 'Implantate und lokale Wirkstoffabgabe'),
    '模拟与训练': ('Simulation and training', 'Simulation und Training'),
    '牙冠与固定修复': ('Dental crowns and fixed restorations', 'Zahnkronen und festsitzender Zahnersatz'),
    '药房制备与质控': ('Pharmacy preparation and quality control', 'Herstellung in Apotheken und Qualitätskontrolle'),
    '规划与误差': ('Planning and sources of error', 'Planung und Fehlerquellen'),
    '采样用品': ('Sampling devices', 'Probenahmeprodukte'),
    '释放控制': ('Controlled release', 'Kontrollierte Freisetzung'),
    '长期可靠性': ('Long-term reliability', 'Langzeitzuverlässigkeit'),
    '骨再生支架': ('Bone regeneration scaffolds', 'Gerüste zur Knochenregeneration'),
    '骨整合与抗感染': ('Osseointegration and infection control', 'Osseointegration und Infektionskontrolle'),
}
for _source, (_english, _german) in _DIRECTIONS.items():
    _OVERRIDES['en'][_source] = _english
    _OVERRIDES['de'][_source] = _german
_TAXONOMY = {
    '外科与牙科植入物': ('Surgical and dental implants', 'Chirurgische und dentale Implantate'),
    '假体与修复体': ('Prostheses and restorations', 'Prothesen und Restaurationen'),
    '药物与药物递送': ('Medicines and drug delivery', 'Arzneimittel und Wirkstoffabgabe'),
    '外科器械与手术导板': ('Surgical instruments and guides', 'Chirurgische Instrumente und Schablonen'),
    '医疗耗材与个人防护用品': ('Medical consumables and protective equipment', 'Medizinische Verbrauchsmaterialien und Schutzausrüstung'),
    '医学教育、训练与手术规划模型': ('Models for medical education, training and surgical planning', 'Modelle für medizinische Lehre, Training und Operationsplanung'),
    '实验室设备与显微镜': ('Laboratory equipment and microscopes', 'Laborgeräte und Mikroskope'),
    '未确认': ('Unconfirmed', 'Nicht bestätigt'),
    '不适用': ('Not applicable', 'Nicht zutreffend'),
    '多类确认': ('Multiple categories confirmed', 'Mehrere Kategorien bestätigt'),
    '非特异疾病／通用生物医学': ('Non-specific disease / general biomedicine', 'Unspezifische Erkrankung / allgemeine Biomedizin'),
    '口腔、牙科与颌面': ('Oral, dental and maxillofacial', 'Mund-, Zahn- und Kieferheilkunde'),
    '肌肉骨骼与结缔组织': ('Musculoskeletal and connective tissue', 'Bewegungsapparat und Bindegewebe'),
    '创伤与重建': ('Trauma and reconstruction', 'Trauma und Rekonstruktion'),
    '心血管与血管': ('Cardiovascular and vascular', 'Herz-Kreislauf- und Gefäßerkrankungen'),
    '神经与神经外科': ('Neurology and neurosurgery', 'Neurologie und Neurochirurgie'),
    '肿瘤': ('Oncology', 'Onkologie'),
    '呼吸与胸部': ('Respiratory and thoracic', 'Atemwege und Thorax'),
    '消化、肝胆与胃肠': ('Digestive, hepatobiliary and gastrointestinal', 'Verdauungstrakt, Leber und Gallenwege'),
    '皮肤、软组织与伤口愈合': ('Skin, soft tissue and wound healing', 'Haut, Weichgewebe und Wundheilung'),
    '泌尿与生殖': ('Urology and reproductive health', 'Urologie und Reproduktionsmedizin'),
    '感染与抗菌': ('Infection and antimicrobial applications', 'Infektionen und antimikrobielle Anwendungen'),
    '内分泌、代谢与系统性慢病': ('Endocrine, metabolic and systemic chronic disease', 'Endokrine, metabolische und systemische chronische Erkrankungen'),
    '眼科与耳科': ('Ophthalmology and otology', 'Augen- und Ohrenheilkunde'),
    '未指明疾病的药物治疗': ('Drug treatment without a specified disease', 'Arzneimitteltherapie ohne spezifische Erkrankung'),
    '先天与发育异常': ('Congenital and developmental disorders', 'Angeborene und Entwicklungsstörungen'),
    '应用场景未标注': ('Application not specified', 'Anwendung nicht angegeben'),
    '工艺未明确': ('Process not specified', 'Verfahren nicht angegeben'),
    '槽式光聚合': ('Vat photopolymerization', 'Bad-Photopolymerisation'),
    '材料挤出': ('Material extrusion', 'Materialextrusion'),
    '粉床熔融': ('Powder bed fusion', 'Pulverbettfusion'),
    '材料喷射': ('Material jetting', 'Material-Jetting'),
    '粘结剂喷射': ('Binder jetting', 'Binder-Jetting'),
    '定向能量沉积': ('Directed energy deposition', 'Gerichtete Energiedeposition'),
    '薄片层压': ('Sheet lamination', 'Schichtlaminierung'),
    '材料未明确': ('Material not specified', 'Material nicht angegeben'),
    '金属与合金': ('Metals and alloys', 'Metalle und Legierungen'),
    '聚合物与光聚合物': ('Polymers and photopolymers', 'Polymere und Photopolymere'),
    '陶瓷与生物活性玻璃': ('Ceramics and bioactive glasses', 'Keramiken und bioaktive Gläser'),
    '复合材料': ('Composites', 'Verbundwerkstoffe'),
    '水凝胶与生物墨水': ('Hydrogels and bioinks', 'Hydrogele und Biotinten'),
    '药物制剂': ('Pharmaceutical formulations', 'Arzneimittelformulierungen'),
    '生物与含细胞材料': ('Biological and cell-containing materials', 'Biologische und zellhaltige Materialien'),
    '多材料体系': ('Multi-material systems', 'Multimaterialsysteme'),
    '微流控与检测平台': ('Microfluidics and diagnostic platforms', 'Mikrofluidik und Diagnostikplattformen'),
    '外科导板与手术规划': ('Surgical guides and planning', 'Chirurgische Schablonen und Operationsplanung'),
    '义齿树脂与性能': ('Denture resins and performance', 'Prothesenharze und ihre Eigenschaften'),
    '药物释放与剂型': ('Drug release and dosage forms', 'Wirkstofffreisetzung und Darreichungsformen'),
    '骨与金属植入物': ('Bone and metal implants', 'Knochen- und Metallimplantate'),
    '数字化牙科与修复': ('Digital dentistry and restorations', 'Digitale Zahnmedizin und Restaurationen'),
    '疫情与个人防护': ('Pandemic response and protective equipment', 'Pandemie und persönliche Schutzausrüstung'),
    '组织工程与生物打印': ('Tissue engineering and bioprinting', 'Tissue Engineering und Bioprinting'),
    '未分配词汇主题': ('Theme not assigned', 'Thema nicht zugewiesen'),
    '核心语料': ('Core corpus', 'Kernkorpus'),
    '边界语料': ('Boundary corpus', 'Randkorpus'),
    '跨类别语料': ('Cross-category corpus', 'Kategorienübergreifender Korpus'),
    '证据有限语料': ('Limited-evidence corpus', 'Korpus mit begrenzter Evidenz'),
    '补充语料': ('Supplementary corpus', 'Ergänzungskorpus'),
    '未分类': ('Unclassified', 'Nicht klassifiziert'),
    '原始研究': ('Original research', 'Originalstudie'),
    '综述': ('Review', 'Übersichtsarbeit'),
    '其他': ('Other', 'Sonstige'),
    '社论': ('Editorial', 'Editorial'),
    '病例报告': ('Case report', 'Fallbericht'),
}
for _source, (_english, _german) in _TAXONOMY.items():
    _OVERRIDES['en'][_source] = _english
    _OVERRIDES['de'][_source] = _german

_COUNTRIES = {
    '中国': ('China', 'China'), '丹麦': ('Denmark', 'Dänemark'),
    '以色列': ('Israel', 'Israel'), '加拿大': ('Canada', 'Kanada'),
    '奥地利': ('Austria', 'Österreich'), '巴西': ('Brazil', 'Brasilien'),
    '德国': ('Germany', 'Deutschland'), '意大利': ('Italy', 'Italien'),
    '日本': ('Japan', 'Japan'), '比利时': ('Belgium', 'Belgien'),
    '法国': ('France', 'Frankreich'), '澳大利亚': ('Australia', 'Australien'),
    '瑞典': ('Sweden', 'Schweden'), '瑞士': ('Switzerland', 'Schweiz'),
    '美国': ('United States', 'Vereinigte Staaten'),
    '芬兰': ('Finland', 'Finnland'),
    '英国': ('United Kingdom', 'Vereinigtes Königreich'),
    '荷兰': ('Netherlands', 'Niederlande'),
    '葡萄牙': ('Portugal', 'Portugal'), '西班牙': ('Spain', 'Spanien'),
    '韩国': ('South Korea', 'Südkorea'),
}
_ENTERPRISE_TERMS = {
    '正常经营': ('Active', 'Aktiv'),
    '已被收购并整合': ('Acquired and integrated', 'Übernommen und integriert'),
    '被收购后继续经营': ('Operating after acquisition', 'Nach Übernahme weiter aktiv'),
    '业务已转让': ('Business transferred', 'Geschäft übertragen'),
    '停止经营': ('Ceased operations', 'Betrieb eingestellt'),
    '已注销/解散': ('Dissolved', 'Aufgelöst'),
    '已转型': ('Business pivoted', 'Geschäftsfeld geändert'),
    '破产/重整': ('Insolvency / restructuring', 'Insolvenz / Restrukturierung'),
    '有产品或技术描述': ('Product or technology described', 'Produkt oder Technologie beschrieben'),
    '资料不足': ('Limited information', 'Unzureichende Informationen'),
    '年份线索待逐条独立核验': ('Year clues awaiting verification',
                         'Jahresangaben noch einzeln zu prüfen'),
    '截至资料核查日的档案现状；不是产品发布日期':
        ('Status as of the source review; not a product launch date',
         'Archivstand zum Zeitpunkt der Quellenprüfung; kein Produktveröffentlichungsdatum'),
    '工作簿叙述年份；非发布日期':
        ('Year mentioned in workbook; not a launch date',
         'In der Arbeitsmappe genanntes Jahr; kein Veröffentlichungsdatum'),
    '工作簿整理·年份级': ('Workbook entry; year only', 'Arbeitsmappeneintrag; nur Jahresangabe'),
    '年份级': ('Year only', 'Nur Jahresangabe'),
    '具体日期': ('Exact date', 'Genaues Datum'),
    '企业公告独立核验': ('Company announcement independently verified',
                     'Unternehmensmitteilung unabhängig geprüft'),
    '官网独立核验': ('Company website independently verified',
               'Unternehmenswebsite unabhängig geprüft'),
    '监管机构独立核验': ('Regulatory source independently verified',
                   'Aufsichtsbehörde unabhängig geprüft'),
    '工作簿来源复查': ('Workbook source rechecked',
                 'Quelle aus der Arbeitsmappe erneut geprüft'),
}
for _source, (_english, _german) in {**_COUNTRIES, **_ENTERPRISE_TERMS}.items():
    _OVERRIDES['en'][_source] = _english
    _OVERRIDES['de'][_source] = _german
_OVERVIEW_TEXT = {
    '年度占比': ('Annual share', 'Jährlicher Anteil'),
    '年度数量': ('Annual count', 'Jährliche Anzahl'),
    '累计论文数': ('Cumulative papers', 'Kumulierte Publikationszahl'),
    '论文篇数': ('Paper count', 'Publikationszahl'),
    '篇数': ('Count', 'Anzahl'),
    '年份': ('Year', 'Jahr'),
    '当前筛选': ('Current selection', 'Aktuelle Auswahl'),
    '展示方式': ('Display mode', 'Darstellung'),
    '分析维度': ('Analysis dimension', 'Analysedimension'),
    '研究维度的交叉分布': ('Cross-distribution of research dimensions', 'Kreuzverteilung der Forschungsdimensionen'),
    '分类代码怎么读': ('How to read the classification codes', 'Die Klassifikationscodes verstehen'),
    '论文按四个维度描述：P 是研究的医疗对象，D 是疾病或应用场景，T 是增材制造工艺，M 是使用的材料。':
        ('Each paper is described along four dimensions: P identifies the medical application, D the disease or use case, T the additive manufacturing process, and M the material.',
         'Jede Publikation wird anhand von vier Dimensionen beschrieben: P bezeichnet den medizinischen Anwendungsbereich, D die Erkrankung oder Anwendung, T das additive Fertigungsverfahren und M das Material.'),
    '论文研究的产品或器件是什么。':
        ('The product or device studied in the paper.', 'Das in der Publikation untersuchte Produkt oder Gerät.'),
    '论文面向哪种疾病、治疗或医学用途。':
        ('The disease, treatment or medical use addressed.', 'Die untersuchte Erkrankung, Behandlung oder medizinische Anwendung.'),
    '论文采用哪一类增材制造技术。':
        ('The additive manufacturing process used.', 'Das eingesetzte additive Fertigungsverfahren.'),
    '论文使用哪一类打印材料。':
        ('The class of material used for printing.', 'Die für den Druck verwendete Materialklasse.'),
    '特殊标记：U：未确认 · NA：不适用 · MULTI：多类确认；疾病／应用中的 unassigned 表示应用场景未标注。':
        ('Special codes: U = unconfirmed, NA = not applicable, MULTI = multiple confirmed categories. In disease/application, unassigned means no application was tagged.',
         'Sondercodes: U = nicht bestätigt, NA = nicht zutreffend, MULTI = mehrere Kategorien bestätigt. Bei Erkrankung/Anwendung bedeutet unassigned, dass keine Anwendung gekennzeichnet wurde.'),
    '筛选后的论文': ('Papers in selection', 'Publikationen in der Auswahl'),
    '选择的时间范围': ('Selected period', 'Gewählter Zeitraum'),
    '生物打印相关': ('Bioprinting-related', 'Bioprinting-bezogen'),
    '研究产出的时间轨迹': ('Research output over time', 'Forschungsaktivität im Zeitverlauf'),
    '绿色柱：年度数量 · 蓝色线：所选范围内累计；来源为当前项目语料。':
        ('Green bars show annual paper counts; the blue line shows the cumulative total within the selected period.',
         'Grüne Balken zeigen die jährliche Publikationszahl; die blaue Linie die kumulierte Zahl im gewählten Zeitraum.'),
    '主要医疗对象': ('Main medical applications', 'Wichtigste medizinische Anwendungsbereiche'),
    '每篇归入一个主医疗对象类别，合计等于当前论文数。':
        ('Each paper has one primary medical application, so the categories add up to the selected paper count.',
         'Jede Publikation hat einen primären medizinischen Anwendungsbereich; die Kategorien summieren sich daher zur ausgewählten Publikationszahl.'),
    '研究对象的年度结构': ('Annual composition of medical applications', 'Jährliche Verteilung der medizinischen Anwendungsbereiche'),
    '各年份分别计算占比。': ('Shares are calculated separately for each year.', 'Die Anteile werden für jedes Jahr getrennt berechnet.'),
    '把研究规模与类别占比分开，比较技术路线的结构变化。':
        ('Compare changes in research focus separately from growth in publication volume.',
         'Vergleichen Sie Veränderungen der Forschungsschwerpunkte unabhängig vom Wachstum der Publikationszahl.'),
    '让每一个趋势，都能回到具体论文与标注证据。':
        ('Trace each trend back to individual papers and their classification evidence.',
         'Verfolgen Sie jeden Trend bis zu den einzelnen Publikationen und ihren Klassifikationsbelegen zurück.'),
}
for _source, (_english, _german) in _OVERVIEW_TEXT.items():
    _OVERRIDES['en'][_source] = _english
    _OVERRIDES['de'][_source] = _german
_EVIDENCE_TERMS = {
    '直接企业对应': ('Direct company match', 'Direkter Unternehmensbezug'),
    '相关平台/企业线索': ('Related platform or company lead', 'Hinweis auf eine verwandte Plattform oder ein Unternehmen'),
    '非企业开源案例': ('Non-company open-source case', 'Quelloffener Fall ohne Unternehmen'),
    '暂缺可核验企业对应': ('No verified company match yet', 'Derzeit kein verifizierter Unternehmensbezug'),
    '直接技术对应': ('Direct technology match', 'Direkte technologische Übereinstimmung'),
    '相关平台/验证线索': ('Related platform or validation lead', 'Verwandte Plattform oder Validierungshinweis'),
    '企业产品/技术': ('Company product or technology', 'Unternehmensprodukt oder -technologie'),
    '非企业开源项目': ('Non-company open-source project', 'Quelloffenes Projekt ohne Unternehmen'),
    '监管器械记录': ('Regulatory device record', 'Regulatorischer Produkteintrag'),
    '研究机构授权与企业制造': ('Research institution licensing and company manufacturing', 'Lizenzierung durch Forschungseinrichtung und Fertigung im Unternehmen'),
    '企业网站收录技术论文': ('Technical paper on company website', 'Fachartikel auf einer Unternehmenswebsite'),
    '已展示产品或服务': ('Product or service demonstrated', 'Produkt oder Dienstleistung vorgestellt'),
    '研究设备': ('Research equipment', 'Forschungsgerät'),
    '研发平台': ('R&D platform', 'Forschungs- und Entwicklungsplattform'),
    '开源硬件': ('Open-source hardware', 'Quelloffene Hardware'),
    '企业参与多中心研究': ('Company participates in multicenter study', 'Unternehmen an multizentrischer Studie beteiligt'),
    '临床转化阶段': ('Clinical translation stage', 'Phase der klinischen Übertragung'),
    '药物发现平台': ('Drug-discovery platform', 'Plattform zur Wirkstoffforschung'),
    '研发与临床试验申请': ('R&D and clinical-trial application', 'Forschung und Antrag auf klinische Prüfung'),
    '临床研究阶段': ('Clinical research stage', 'Phase der klinischen Forschung'),
}
for _source, (_english, _german) in _EVIDENCE_TERMS.items():
    _OVERRIDES['en'][_source] = _english
    _OVERRIDES['de'][_source] = _german
_COMPANY_STATES = {
    '正常经营': ('Operating', 'Aktiv'),
    '被收购后继续经营': ('Operating after acquisition', 'Nach Übernahme weiter aktiv'),
    '已被收购并整合': ('Acquired and integrated', 'Übernommen und integriert'),
    '已注销/解散': ('Deregistered or dissolved', 'Gelöscht oder aufgelöst'),
    '破产/重整': ('Insolvency or restructuring', 'Insolvenz oder Restrukturierung'),
    '停止经营': ('Ceased operations', 'Betrieb eingestellt'),
    '业务已转让': ('Business transferred', 'Geschäft übertragen'),
    '已转型': ('Pivoted', 'Geschäftsmodell geändert'),
    '可打开': ('Accessible', 'Erreichbar'),
    '无法读取': ('Unavailable', 'Nicht abrufbar'),
    '补充来源已核验': ('Additional source verified', 'Zusätzliche Quelle geprüft'),
    '无原表来源': ('No source in original workbook', 'Keine Quelle in der ursprünglichen Tabelle'),
}
for _source, (_english, _german) in _COMPANY_STATES.items():
    _OVERRIDES['en'][_source] = _english
    _OVERRIDES['de'][_source] = _german
_OVERRIDES['en'][
    '颅颌面个体化重建正由缺损外形匹配，向结构稳定、组织整合和长期功能恢复发展。学术研究逐步连接设计、制造和临床评价；企业则以不同材料路线、规划服务及医院制造支持承接这些需求。'
] = ('Patient-specific craniomaxillofacial reconstruction is moving beyond shape matching '
     'toward structural stability, tissue integration and long-term functional recovery. '
     'Research increasingly connects design, manufacturing and clinical evaluation, while '
     'companies respond through distinct material platforms, planning services and support '
     'for hospital-based manufacturing.')
_OVERRIDES['de'][
    '颅颌面个体化重建正由缺损外形匹配，向结构稳定、组织整合和长期功能恢复发展。学术研究逐步连接设计、制造和临床评价；企业则以不同材料路线、规划服务及医院制造支持承接这些需求。'
] = ('Die patientenspezifische kraniomaxillofaziale Rekonstruktion entwickelt sich von der '
     'reinen Anpassung an die Defektform hin zu struktureller Stabilität, Gewebeintegration '
     'und langfristiger Wiederherstellung der Funktion. Die Forschung verknüpft zunehmend '
     'Konstruktion, Fertigung und klinische Bewertung; Unternehmen greifen diese Anforderungen '
     'mit verschiedenen Materialplattformen, Planungsdiensten und Unterstützung für die '
     'Fertigung in Kliniken auf.')


def set_language(code: str, root: Path) -> None:
    if code not in _LANGUAGES:
        raise ValueError(f'Unsupported language: {code}')
    _ACTIVE.set(code)
    _ROOT.set(Path(root))


def language() -> str:
    return _ACTIVE.get()


def year_papers_label(year: int) -> str:
    return {'zh': f'{year} 年论文', 'en': f'Papers in {year}',
            'de': f'Publikationen {year}'}[language()]


def hero_metadata(first: int, last: int, count: int, future: bool) -> str:
    period = f'{first}–{last}'
    if language() == 'en':
        source = 'historical + supplemental data' if future else 'historical data before 2026'
        return f'{period} · {count:,} papers selected · {source}'
    if language() == 'de':
        source = 'historische und ergänzte Daten' if future else 'historische Daten vor 2026'
        return f'{period} · {count:,} Publikationen ausgewählt · {source}'
    source = '历史 + 补充数据' if future else '2026 年之前的历史基线'
    return f'{period} · 当前筛选 {count:,} 篇 · {source}'


@contextmanager
def preserve_original_text():
    """Render source excerpts verbatim in every visitor language."""
    token = _ACTIVE.set('zh')
    try:
        yield
    finally:
        _ACTIVE.reset(token)


def protect_names(values) -> None:
    """Keep company names, paper titles and original source text unchanged."""
    _PROTECTED.update(str(value) for value in values if isinstance(value, str) and value)


@lru_cache(maxsize=8)
def _catalogue(root: str, code: str) -> dict[str, str]:
    path = Path(root)/'data'/'i18n'/f'{code}.json'
    if not path.exists():
        return {}
    catalogue = json.loads(path.read_text(encoding='utf-8'))
    curated_path = Path(root)/'scripts'/f'question_titles_{code}.json'
    cross_path = Path(root)/'data'/'cross_analysis.json'
    if curated_path.exists() and cross_path.exists():
        curated = json.loads(curated_path.read_text(encoding='utf-8'))
        cross = json.loads(cross_path.read_text(encoding='utf-8'))
        catalogue.update({row['question']: curated[row['question_id']]
                          for row in cross['questions'] if row['question_id'] in curated})
    return catalogue


def tr(value: str, *, code: str | None = None, root: Path | None = None) -> str:
    code = code or language()
    if code == 'zh' or not isinstance(value, str) or not _HAN.search(value):
        return value
    if value in _PROTECTED:
        return value
    catalogue = _catalogue(str(root or _ROOT.get()), code)
    overrides = _OVERRIDES[code]
    if value in overrides:
        return _western_punctuation(overrides[value])
    if value in catalogue:
        return _western_punctuation(catalogue[value])
    # Catalogue extraction strips the surrounding whitespace of source
    # fields. Preserve that whitespace when rendering the original record.
    stripped = value.strip()
    if stripped != value:
        if stripped in _PROTECTED:
            return value
        translated = overrides.get(stripped, catalogue.get(stripped))
        if translated is not None:
            start = value.find(stripped)
            return value[:start] + _western_punctuation(translated) + value[start+len(stripped):]
    # Dynamic numbers, names and HTML markup appear between stable UI phrases.
    # Translate only exact, pre-reviewed Chinese fragments; never call a live API.
    def translate_segment(match):
        phrase = match.group()
        if phrase in overrides:
            return overrides[phrase]
        if phrase in catalogue:
            return catalogue[phrase]
        return re.sub(r'[\u3400-\u9fff]+',
                      lambda word: overrides.get(word.group(), catalogue.get(word.group(), word.group())),
                      phrase)
    return _western_punctuation(_SEGMENT.sub(translate_segment, value))


def _western_punctuation(value: str) -> str:
    """Remove Chinese sentence marks left outside translated prose spans."""
    value = re.sub(r'([.!?])\s*。', r'\1', value)
    value = re.sub(r'([,;:])\s*[，；：]', r'\1', value)
    return (value.replace('。', '.').replace('，', ', ')
                 .replace('；', '; ').replace('：', ': ')
                 .replace('？', '?').replace('！', '!'))


def _translate_frame(frame):
    import pandas as pd

    if isinstance(frame, pd.Series) and language() != 'zh':
        result = frame.copy()
        if isinstance(result.name, str):
            result.name = tr(result.name)
        if isinstance(result.index.name, str):
            result.index.name = tr(result.index.name)
        if pd.api.types.is_object_dtype(result.dtype) or pd.api.types.is_string_dtype(result.dtype):
            result = result.map(lambda value: tr(value) if isinstance(value, str) else value)
        return result
    if not isinstance(frame, pd.DataFrame) or language() == 'zh':
        return frame
    result = frame.copy()
    result.columns = [tr(str(column)) for column in result.columns]
    for column in result.select_dtypes(include=['object', 'string']).columns:
        result[column] = result[column].map(lambda value: tr(value) if isinstance(value, str) else value)
    return result


def _translate_figure(figure):
    if language() == 'zh':
        return figure
    try:
        figure = figure.__class__(figure.to_dict())
        def translate_values(values):
            if isinstance(values, str):
                return tr(values)
            if isinstance(values, (list, tuple)):
                return [translate_values(value) for value in values]
            try:
                import numpy as np
                if isinstance(values, np.ndarray):
                    return [translate_values(value) for value in values.tolist()]
            except ImportError:
                pass
            return values
        for trace in figure.data:
            if isinstance(trace.name, str):
                trace.name = tr(trace.name)
            if isinstance(trace.hovertemplate, str):
                trace.hovertemplate = tr(trace.hovertemplate)
            for field in ('x', 'y', 'labels', 'text', 'theta', 'r',
                          'hovertext', 'customdata'):
                values = getattr(trace, field, None)
                if values is not None and not isinstance(values, (str, bytes)):
                    try:
                        setattr(trace, field, translate_values(values))
                    except (TypeError, ValueError):
                        pass
        for axis in ('xaxis', 'yaxis', 'xaxis2', 'yaxis2'):
            item = getattr(figure.layout, axis, None)
            if item and item.title and isinstance(item.title.text, str):
                item.title.text = tr(item.title.text)
            if item and item.ticktext is not None:
                item.ticktext = translate_values(item.ticktext)
        if figure.layout.title and isinstance(figure.layout.title.text, str):
            figure.layout.title.text = tr(figure.layout.title.text)
        if figure.layout.annotations:
            for annotation in figure.layout.annotations:
                if isinstance(annotation.text, str):
                    annotation.text = tr(annotation.text)
    except (AttributeError, TypeError, ValueError):
        return figure
    return figure


def install_streamlit_translation(st) -> None:
    """Translate presentation arguments without changing widget keys or data IDs."""
    from streamlit.delta_generator import DeltaGenerator

    if getattr(st, '_am_i18n_installed', False):
        return
    labels = {
        'markdown', 'caption', 'title', 'header', 'subheader', 'info', 'warning',
        'error', 'success', 'button', 'link_button', 'checkbox', 'selectbox',
        'multiselect', 'radio', 'slider', 'number_input', 'text_input',
        'expander', 'download_button', 'metric', 'tabs', 'write', 'dataframe',
        'table', 'plotly_chart', 'html', 'text', 'file_uploader', 'json',
    }
    original_module = {name: getattr(st, name, None) for name in labels}
    original_class = {name: getattr(DeltaGenerator, name, None) for name in labels}

    def make_wrapper(method_name, original):
        @wraps(original)
        def translated(*args, **kwargs):
            if language() == 'zh':
                return original(*args, **kwargs)
            args = list(args)
            first = 1 if args and isinstance(args[0], DeltaGenerator) else 0
            if method_name in ('dataframe', 'table'):
                if len(args) > first:
                    args[first] = _translate_frame(args[first])
                elif 'data' in kwargs:
                    kwargs['data'] = _translate_frame(kwargs['data'])
            elif method_name == 'plotly_chart':
                if len(args) > first:
                    args[first] = _translate_figure(args[first])
                elif 'figure_or_data' in kwargs:
                    kwargs['figure_or_data'] = _translate_figure(kwargs['figure_or_data'])
            elif method_name == 'tabs':
                if len(args) > first:
                    args[first] = [tr(x) for x in args[first]]
            elif method_name == 'write':
                args[first:] = [tr(x) if isinstance(x, str) else _translate_frame(x)
                                for x in args[first:]]
            else:
                if len(args) > first and isinstance(args[first], str):
                    args[first] = tr(args[first])
                if isinstance(kwargs.get('label'), str):
                    kwargs['label'] = tr(kwargs['label'])
                for key in ('help', 'placeholder', 'icon', 'delta', 'body'):
                    if isinstance(kwargs.get(key), str):
                        kwargs[key] = tr(kwargs[key])
                if method_name == 'download_button' and isinstance(kwargs.get('file_name'), str):
                    filename = kwargs['file_name']
                    stem, separator, extension = filename.rpartition('.')
                    kwargs['file_name'] = (tr(stem)+separator+extension
                                           if separator else tr(filename))
                if method_name == 'metric' and len(args) > first+2 and isinstance(args[first+2], str):
                    args[first+2] = tr(args[first+2])
                if method_name in ('selectbox', 'multiselect', 'radio'):
                    original_format = kwargs.get('format_func', str)
                    active_code, active_root = language(), _ROOT.get()
                    kwargs['format_func'] = lambda option, f=original_format, c=active_code, r=active_root: tr(f(option), code=c, root=r)
            return original(*args, **kwargs)
        return translated

    for name in labels:
        if original_class[name] is not None:
            setattr(DeltaGenerator, name, make_wrapper(name, original_class[name]))
        if original_module[name] is not None:
            setattr(st, name, make_wrapper(name, original_module[name]))
    st._am_i18n_installed = True


LANGUAGE_OPTIONS = _LANGUAGES

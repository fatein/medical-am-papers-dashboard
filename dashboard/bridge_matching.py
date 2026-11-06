"""Explicit medical-object and question-facet screening; no ownership inference."""
from __future__ import annotations
import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

METHOD_VERSION = 'medical-object-and-question-facet-1.0'
D = 'dental'
I = 'implants_and_prostheses'
T = 'tissue_engineering_and_bioprinting'
P = 'pharmaceuticals_and_drug_delivery'
S = 'surgical_tools_and_anatomical_models'
M = 'medical_devices_and_rehabilitation'
APPLICATIONS = [
    {'id': D, 'labels': dict(zh='口腔与牙科', en='Dental', de='Zahnmedizin')},
    {'id': I, 'labels': dict(zh='植入物与假体', en='Implants and prostheses', de='Implantate und Prothesen')},
    {'id': T, 'labels': dict(zh='组织工程与生物打印', en='Tissue engineering and bioprinting', de='Gewebezüchtung und Bioprinting')},
    {'id': P, 'labels': dict(zh='药物与递送', en='Pharmaceuticals and drug delivery', de='Arzneimittel und Wirkstoffabgabe')},
    {'id': S, 'labels': dict(zh='手术工具与解剖模型', en='Surgical tools and anatomical models', de='Chirurgische Instrumente und anatomische Modelle')},
    {'id': M, 'labels': dict(zh='医疗器械与康复', en='Medical devices and rehabilitation', de='Medizinprodukte und Rehabilitation')},
]


def _topic(ident, apps, zh, en, de, *groups):
    return {'id': ident, 'applications': apps, 'labels': dict(zh=zh, en=en, de=de),
            'matching_terms': [g.split('|') for g in groups]}


_BONE = 'bone|orthopedic|orthopaedic|spinal|vertebral|osseointegration|骨|脊柱|椎'
_IMPLANT = 'implant|prosthesis|prostheses|植入|假体'
_GUIDE = 'guide plate|surgical guide|surgical template|surgical jig|drill guide|drilling guide|cutting guide|osteotomy guide|定位导板|手术导板|手术导向|截骨导板|钻孔导板'
TOPICS = [
    _topic('porous_implant', [I,D], '多孔骨接触植入物', 'Porous bone-contact implants', 'Poröse knochenkontaktierende Implantate', _IMPLANT, 'porous|porosity|lattice|pore|trabecular|多孔|孔隙|晶格|骨小梁', _BONE+'|dental|牙'),
    _topic('custom_implant', [I,D], '个体化骨重建植入物', 'Patient-specific reconstruction implants', 'Patientenspezifische Rekonstruktionsimplantate', _IMPLANT, 'patient-specific|patient specific|custom|craniomaxillofacial|cranial|mandibular|spinal|intervertebral|个体化|定制|颅|椎|下颌'),
    _topic('implant_interface', [I,D], '骨植入物表面与感染控制', 'Bone implant surfaces and infection control', 'Knochenimplantatoberflächen und Infektionskontrolle', _IMPLANT, _BONE+'|dental|牙', 'coating|surface|antibacterial|antimicrobial|infection|immune|表面|涂层|抗菌|感染|免疫'),
    _topic('implant_reliability', [I,D], '骨植入物可靠性', 'Bone implant reliability', 'Zuverlässigkeit von Knochenimplantaten', _IMPLANT, _BONE+'|dental|牙', 'fatigue|fracture|corrosion|wear|heat treatment|cleaning|residual|defect|疲劳|断裂|腐蚀|磨损|清洗|热处理|残粉|缺陷'),
    _topic('bone_scaffold', [T,I], '骨再生支架', 'Bone regeneration scaffolds', 'Gerüste zur Knochenregeneration', 'scaffold|matrix|支架', 'bone|osteogen|osteoblast|骨再生|成骨|骨修复'),
    _topic('dental_crown', [D], '牙冠与固定修复', 'Crowns and fixed dental restorations', 'Kronen und festsitzender Zahnersatz', 'dental crown|tooth crown|dental bridge|dental restoration|fixed restoration|牙冠|冠桥|固定修复|牙科修复'),
    _topic('denture', [D], '可摘义齿与基托', 'Removable dentures and bases', 'Herausnehmbarer Zahnersatz und Basen', 'denture|removable partial|义齿|假牙|基托'),
    _topic('dental_material', [D], '牙科树脂与咬合夹板', 'Dental resins and occlusal splints', 'Dentalharze und Aufbissschienen', 'dental|tooth|occlusal|牙科|牙齿|咬合', 'resin|splint|restoration|树脂|夹板|修复'),
    _topic('denture_interface', [D], '义齿结合与修复界面', 'Denture bonding and repair interfaces', 'Verbund- und Reparaturflächen bei Zahnersatz', 'denture|义齿|假牙', 'bond|adhesive|integral|integrated|monolithic|reline|repair|tooth socket|牙槽窝|一体|粘接|黏接|衬垫|重衬|修补'),
    _topic('prosthetic_socket', [I,M], '残肢假肢接受腔', 'Residual-limb prosthetic sockets', 'Prothesenschäfte für Stümpfe', 'socket|接受腔', 'residual limb|residual-limb|amputee|prosthetic limb|prosthetic socket|stump|残肢|假肢'),
    _topic('upper_prosthesis', [I,M], '上肢与手假肢', 'Upper-limb and hand prostheses', 'Arm- und Handprothesen', 'prosthe|假肢', 'hand|finger|upper limb|upper-limb|grasp|上肢|手指|抓握'),
    _topic('lower_orthosis', [I,M], '下肢假肢与个体化矫形器', 'Lower-limb prostheses and customized orthoses', 'Beinprothesen und individuelle Orthesen', 'orthosis|orthoses|orthotic|prosthetic foot|prosthetic leg|prosthetic knee|ankle-foot|矫形|支具|足垫|下肢假肢'),
    _topic('facial_prosthesis', [I,M], '颌面与眼假体', 'Facial and ocular prostheses', 'Gesichts- und Augenprothesen', 'prosthe|假体|义眼', 'facial|ocular|eye|ear|nose|orbital|颌面|眼|耳|鼻'),
    _topic('oral_dosage', [P], '口服片剂与个体化剂量', 'Oral tablets and personalized doses', 'Orale Tabletten und individuelle Dosierung', 'tablet|oral dosage|oral pharmaceutical|口服|片剂|药片', 'drug|pharmaceut|active ingredient|medicament|药|制剂'),
    _topic('oral_film', [P], '口服药膜', 'Oral pharmaceutical films', 'Orale Arzneimittelfilme', 'oral film|orodispersible|buccal film|口腔膜|口溶膜|口服薄膜'),
    _topic('capsule', [P], '药物胶囊与多药分区', 'Pharmaceutical capsules and multidrug compartments', 'Arzneikapseln und Mehrwirkstoffkammern', 'capsule|polypill|multi-drug|multidrug|胶囊|复方', 'drug|pharmaceut|active ingredient|medicament|药|制剂'),
    _topic('drug_release', [P], '制剂释药材料与结构', 'Drug-release materials and structures', 'Materialien und Strukturen zur Wirkstofffreisetzung', 'drug|pharmaceut|medicament|dosage form|药物|制剂', 'release|dissolution|disintegrat|dissolv|释药|释放|溶出|崩解'),
    _topic('microneedle', [P,M], '微针递送', 'Microneedle delivery', 'Mikronadelabgabe', 'microneedle|micro-needle|微针'),
    _topic('local_delivery', [P,I], '植入与局部给药', 'Implantable and localized drug delivery', 'Implantierbare und lokale Wirkstoffabgabe', 'drug|pharmaceut|medicament|药物|给药', 'implant|local delivery|localised|localized|tumor|tumour|植入|局部|肿瘤'),
    _topic('wound_delivery', [P,T,M], '创面敷料与给药水凝胶', 'Wound dressings and delivery hydrogels', 'Wundauflagen und wirkstoffabgebende Hydrogele', 'wound|dressing|创面|伤口|敷料', 'hydrogel|drug|delivery|antimicrobial|gel|水凝胶|药物|给药|抗菌'),
    _topic('mucosal_delivery', [P], '阴道环与眼部给药装置', 'Vaginal rings and ocular drug inserts', 'Vaginalringe und okulare Wirkstoffinserts', 'vaginal ring|intravaginal|ocular insert|ocular drug|ophthalmic drug|阴道环|阴道给药|眼部给药|眼内给药'),
    _topic('pharmacy', [P], '药房按需制剂与质量控制', 'On-demand pharmaceutical production and quality control', 'Bedarfsgerechte Arzneimittelherstellung und Qualitätskontrolle', 'pharmaceut|drug|dosage|medicament|药物|制剂|药房', 'on-demand|on demand|pharmacy|hospital|quality control|spectroscop|dose|按需|医院|药房|质量控制|剂量|光谱'),
    _topic('dental_guide', [D,S], '牙种植手术导板', 'Dental implant surgical guides', 'Chirurgische Schablonen für Dentalimplantate', _GUIDE+'|dental guide|种植导板', 'dental|tooth|teeth|牙|齿'),
    _topic('osteotomy_guide', [S,D], '截骨与切割导板', 'Osteotomy and cutting guides', 'Osteotomie- und Schnittschablonen', 'osteotomy guide|cutting guide|resection guide|cutting template|截骨导板|切割导板|截骨导向|截骨模板'),
    _topic('drill_guide', [S,D], '钻孔与螺钉导向', 'Drilling and screw guides', 'Bohr- und Schraubenschablonen', 'drill guide|drilling guide|screw guide|pedicle guide|钻孔导板|螺钉导板|导向套筒'),
    _topic('surgical_guide', [S,D], '患者匹配手术导板', 'Patient-matched surgical guides', 'Patientenangepasste Operationsschablonen', _GUIDE),
    _topic('custom_instrument', [S], '个体化手术器械', 'Patient-specific surgical instruments', 'Patientenspezifische chirurgische Instrumente', 'surgical instrument|surgical tool|osteotome|retractor|手术器械|截骨刀|牵开器', 'custom|patient-specific|patient specific|anatom|个体化|定制|解剖'),
    _topic('protective_mask', [M], '防护口罩与贴合配件', 'Protective masks and fit accessories', 'Schutzmasken und Passformzubehör', 'respirator|face mask|facemask|口罩|呼吸防护'),
    _topic('face_shield', [M], '防护面屏', 'Protective face shields', 'Gesichtsschutzschilde', 'face shield|facial shield|防护面屏|防护面罩'),
    _topic('sampling_swab', [M], '临床采样拭子', 'Clinical sampling swabs', 'Klinische Probenahmeabstriche', 'swab|nasopharyngeal sampling|拭子|鼻咽采样'),
    _topic('respiratory_support', [M], '呼吸支持装置', 'Respiratory support devices', 'Geräte zur Atemunterstützung', 'ventilator|respiratory support|resuscitat|breathing circuit|respiratory valve|ventilation mask|呼吸机|呼吸支持|复苏器|呼吸阀'),
    _topic('emergency_supply', [M], '紧急医用耗材供应', 'Emergency medical supplies', 'Medizinische Notfallversorgung', 'medical|clinical|hospital|healthcare|医用|医疗|医院', 'emergency|shortage|pandemic|distributed manufactur|紧急|应急|短缺|分布式制造'),
    _topic('anatomical_model', [S], '术前解剖实体模型', 'Anatomical planning models', 'Anatomische Planungsmodelle', 'anatomical model|anatomic model|organ model|physical model|patient-specific model|解剖模型|术前模型|器官模型', 'surg|anatom|cardi|cranio|解剖|手术|心血管|颅'),
    _topic('training_model', [S], '手术训练模拟器', 'Surgical training simulators', 'Chirurgische Trainingssimulatoren', 'surgical train|surgical simulat|medical train|medical simulat|suture train|手术训练|手术模拟|医学训练|缝合训练'),
    _topic('teaching_model', [S], '解剖教学与患者沟通模型', 'Anatomy teaching and patient-communication models', 'Modelle für Anatomielehre und Patientenkommunikation', 'anatom|surg|patient|解剖|手术|患者', 'model|模型', 'teach|educat|communicat|informed consent|教学|教育|沟通|知情同意'),
    _topic('medical_phantom', [S,M], '医学成像与放疗体模', 'Medical imaging and radiotherapy phantoms', 'Phantome für Bildgebung und Strahlentherapie', 'phantom|体模', 'radiotherap|radiation|dosimetr|tomograph|ultrasound|ultrasonic|tissue mimick|tissue-mimick|medical|放疗|剂量|超声|成像|组织模拟'),
    _topic('microfluidic', [M], '医用微流控芯片', 'Medical microfluidic chips', 'Medizinische Mikrofluidikchips', 'microfluidic|micro-fluidic|lab-on-chip|lab-on-a-chip|微流控|微流体'),
    _topic('cell_model', [T,M], '体外细胞与组织模型', 'In vitro cell and tissue models', 'In-vitro-Zell- und Gewebemodelle', 'cell|tissue|organ|细胞|组织|器官', 'in vitro|in-vitro|organ-on-chip|organ on chip|organoid|disease model|tumor model|tumour model|cell culture device|culture chamber|cell culture system|体外|器官芯片|疾病模型|培养装置|培养腔|类器官'),
    _topic('microscopy', [M], '显微观察与光学组件', 'Microscopy and optical components', 'Mikroskopie und optische Komponenten', 'microscope|microscopy|显微镜|显微成像'),
    _topic('medical_sensor', [M], '临床快速检测与传感', 'Rapid medical detection and sensing', 'Medizinische Schnelldiagnostik und Sensorik', 'biosensor|electrochemical sensor|point-of-care|point of care|diagnostic chip|pathogen detect|生物传感|电化学传感|即时检测|病原检测|床旁检测'),
    _topic('laboratory_device', [M], '医学实验设备与自动化', 'Medical laboratory devices and automation', 'Medizinische Laborgeräte und Automatisierung', 'laboratory|lab equipment|pipett|centrifug|incubat|microplate|实验室|移液|离心|培养箱|微孔板', 'device|equipment|automat|robot|仪器|设备|自动化|机器人'),
]

# OR facets inside each question; object-topic AND facet are both required.
_QUESTION_RULES = {
    'P1-001': ('porous_implant', 'pore|porosity|interconnect|bone ingrowth|孔径|孔形|连通|骨长入'),
    'P1-002': ('porous_implant', 'lattice|topolog|stress|load|stiffness|晶格|拓扑|应力|承载'),
    'P1-003': ('porous_implant,implant_interface', 'nano|microstructure|texture|roughness|微纳|粗糙|纹理'),
    'P1-004': ('custom_implant', 'cranial|craniomaxillo|mandib|maxill|orbital|颅|颌|眶'),
    'P1-005': ('custom_implant', 'orthop|spinal|vertebr|acetabul|pelvic|骨科|脊柱|椎|髋臼|骨盆'),
    'P1-006': ('custom_implant', 'image|imaging|segment|fit|scan|影像|分割|适配|扫描'),
    'P1-007': ('implant_interface', 'coating|surface modification|osseointegrat|hydroxyapatite|涂层|表面改性|骨整合|羟基磷灰石'),
    'P1-008': ('implant_interface', 'bacter|antimicrob|infection|biofilm|抗菌|感染|细菌|生物膜'),
    'P1-009': ('bone_scaffold,implant_interface,local_delivery', 'immune|immunomod|macrophage|inflammat|免疫|巨噬|炎症'),
    'P1-010': ('porous_implant,custom_implant,implant_reliability', 'fatigue|fracture strength|fracture resistance|fracture toughness|crack initiation|crack propagation|疲劳|断裂强度|断裂韧性|裂纹扩展'),
    'P1-011': ('implant_interface,implant_reliability', 'corrosion|wear|debris|ion release|腐蚀|磨损|碎屑|离子释放'),
    'P1-012': ('implant_reliability,porous_implant,custom_implant', 'manufacturing defect|residual powder|powder removal|cleaning|heat treatment|post-process|postprocess|制造缺陷|残粉|清洗|热处理|后处理'),
    'P1-013': ('bone_scaffold', 'composite|ceramic|polymer|degrad|复合|陶瓷|聚合物|降解'),
    'P1-014': ('bone_scaffold', 'osteoblast|osteogen|angiogen|vascular|成骨|血管'),
    'P1-015': ('bone_scaffold', 'defect|animal|in vivo|repair|骨缺损|动物|体内|修复'),
    'P2-016': ('dental_crown', 'fit|margin|intaglio|gap|accuracy|precision|适合|适配|边缘|间隙|精度'),
    'P2-017': ('dental_crown,dental_material', 'material|resin|zirconia|ceramic|polymeri|sinter|材料|树脂|氧化锆|陶瓷|聚合'),
    'P2-018': ('dental_crown', 'temporary|permanent|provisional|wear|fracture|临时|永久|磨损|断裂'),
    'P2-019': ('denture', 'base|fit|intaglio|accuracy|precision|基托|适配|精度'),
    'P2-020': ('denture', 'manufactur|workflow|process|time|制作|制造|流程|工艺|时间'),
    'P2-021': ('denture', 'retention|comfort|stability|speech|固位|舒适|稳定|语音'),
    'P2-022': ('denture', 'partial|framework|clasp|局部|支架|卡环'),
    'P2-023': ('dental_material', 'flexur|fracture|strength|splint|fatigue|弯曲|断裂|强度|夹板|疲劳'),
    'P2-024': ('dental_material,dental_crown,denture', 'aging|ageing|color|colour|roughness|thermocycl|老化|颜色|粗糙|热循环'),
    'P2-025': ('dental_material,dental_crown', 'curing|post-cur|clean|drying|post-process|固化|清洗|干燥|后处理'),
    'P2-026': ('denture_interface', 'bond|adhes|teeth|tooth|粘接|黏接|牙齿'),
    'P2-027': ('denture_interface', 'integral|integrated|monolithic|multi-material|tooth socket|一体|多材料|牙槽窝'),
    'P2-028': ('denture_interface', 'reline|repair|重衬|衬垫|修补|修复界面'),
    'P2-029': ('dental_crown', 'resin|zirconia|ceramic|fracture|wear|debond|fatigue|树脂|氧化锆|陶瓷|断裂|磨损|脱粘|疲劳'),
    'P2-030': ('denture', 'fit|comfort|retention|occlus|stability|适配|舒适|固位|咬合|稳定'),
    'P2-031': ('dental_crown,denture', 'manufactur|milling|subtractive|additive|printing|resin|zirconia|fit|retention|制造|铣削|减材|增材|打印|树脂|氧化锆|适配|固位'),
    'P2-032': ('prosthetic_socket', 'scan|fit|shape|digital|扫描|适配|形状|数字'),
    'P2-033': ('prosthetic_socket', 'pressure|comfort|contact|sensor|压力|舒适|接触|传感'),
    'P2-034': ('prosthetic_socket', 'material|lattice|load|strength|fiber|fibre|材料|晶格|承载|强度|纤维'),
    'P2-035': ('upper_prosthesis', 'grasp|finger|hand|function|抓握|手指|手|功能'),
    'P2-036': ('lower_orthosis', 'gait|ankle|foot|knee|walking|步态|踝|足|膝|行走'),
    'P2-037': ('lower_orthosis', 'custom|patient-specific|patient specific|fit|accessib|定制|个体化|适配|可及'),
    'P2-038': ('facial_prosthesis', 'colour|color|appear|fit|facial|ocular|颜色|外观|适配|颌面|眼'),
    'P3-039': ('oral_dosage,pharmacy', 'dose|dosing|personal|content|剂量|个体化|含量'),
    'P3-040': ('oral_dosage,drug_release', 'shape|geometry|porosity|cavity|swallow|形状|几何|孔隙|腔|吞咽'),
    'P3-041': ('oral_dosage,oral_film', 'child|pediatr|paediatr|swallow|taste|tube feeding|儿童|儿科|吞咽|口味|管饲'),
    'P3-042': ('oral_film', 'film|orodispers|dissolv|buccal|薄膜|口溶|溶解|颊'),
    'P3-043': ('capsule', 'capsule|polypill|multi|combination|compartment|胶囊|多药|复方|分区'),
    'P3-044': ('drug_release', 'sustained|controlled release|extended release|prolonged|缓释|控释|持续'),
    'P3-045': ('drug_release,oral_dosage', 'poorly soluble|solubility|immediate release|rapid release|disintegrat|难溶|溶解度|速释|崩解'),
    'P3-046': ('drug_release,capsule', 'layer|multidrug|multi-drug|compartment|staged|sequential|分层|多药|分区|分阶段|顺序'),
    'P3-047': ('drug_release,oral_dosage', 'gastr|intestin|pH|stimuli|stimulus|胃|肠|刺激响应'),
    'P3-048': ('oral_dosage,pharmacy', 'thermal|heat|light|stability|crystal|photoiniti|温度|热|光|稳定|晶体'),
    'P3-049': ('oral_dosage,pharmacy', 'uniform|accuracy|content|mass|precision|均匀|精度|含量|质量'),
    'P3-050': ('oral_dosage,pharmacy', 'printab|rheolog|viscosity|filament|extrusion|feed|可打印|流变|黏度|丝材|挤出'),
    'P3-051': ('microneedle', 'strength|insert|tip|penetrat|height|强度|插入|针尖|穿刺|高度'),
    'P3-052': ('microneedle', 'drug|release|deliver|dissolv|hollow|药物|释放|递送|溶解|中空'),
    'P3-053': ('microneedle', 'mold|mould|accur|precision|fabricat|模具|精度|制造'),
    'P3-054': ('local_delivery', 'implant|sustained|continuous|degrad|植入|持续|降解'),
    'P3-055': ('wound_delivery', 'wound|dressing|hydrogel|创面|伤口|敷料|水凝胶'),
    'P3-056': ('local_delivery,wound_delivery', 'tumor|tumour|cancer|infection|antibiotic|肿瘤|癌|感染|抗生素'),
    'P3-057': ('mucosal_delivery', 'vaginal|ocular|ophthalmic|阴道|眼'),
    'P3-058': ('pharmacy', 'pharmacy|hospital|on-demand|on demand|prescription|药房|医院|按需|处方'),
    'P3-059': ('pharmacy', 'spectroscop|quality control|detect|monitor|raman|infrared|光谱|质控|质量控制|检测|监测|拉曼|红外'),
    'P3-060': ('pharmacy', 'regulat|scale|manufactur|batch|control|监管|规模|制造|批次|控制'),
    'P4-061': ('dental_guide', 'implant|position|accur|placement|种植|定位|精度|植入'),
    'P4-062': ('osteotomy_guide', 'cut|osteotomy|resect|reconstruct|accuracy|截骨|切割|切除|重建|精度'),
    'P4-063': ('drill_guide,dental_guide', 'drill|screw|sleeve|stabili|钻|螺钉|套筒|稳定'),
    'P4-064': ('surgical_guide', 'image|segment|virtual|planning|影像|分割|虚拟|规划'),
    'P4-065': ('surgical_guide', 'error|accur|precision|seating|fit|tolerance|误差|精度|就位|贴合|公差'),
    'P4-066': ('surgical_guide', 'navigat|augmented reality|tracking|导航|增强现实|跟踪'),
    'P4-067': ('surgical_guide', 'mechanical|strength|stiffness|material|sleeve|力学|强度|刚度|材料|套筒'),
    'P4-068': ('surgical_guide', 'sterili|storage|biocompat|sterile|灭菌|储存|生物相容|无菌'),
    'P4-069': ('surgical_guide', 'fixation|contact|stability|support|seating|固定|接触|稳定|支撑|就位'),
    'P4-070': ('surgical_guide', 'operating time|operative time|fluoroscop|radiation|duration|手术时间|透视|辐射|时长'),
    'P4-071': ('surgical_guide', 'fixation|position|accuracy|osteotomy|drill|cutting|fit|navigat|固定|定位|精度|截骨|钻孔|切割|贴合|导航'),
    'P4-072': ('surgical_guide', 'surgery|surgical|patient|手术|患者'),
    'P4-073': ('custom_instrument,osteotomy_guide', 'orthop|bone|cutting|position|骨科|骨|切割|定位'),
    'P4-074': ('custom_instrument', 'complex|anatom|retract|access|osteotome|复杂|解剖|牵开|入路|截骨刀'),
    'P4-075': ('custom_instrument', 'manufactur|sterili|material|fabricat|制造|灭菌|材料'),
    'P5-076': ('protective_mask', 'fit|filter|leak|breath|pressure|贴合|过滤|泄漏|呼吸|压力'),
    'P5-077': ('face_shield', 'wear|reuse|comfort|assembl|view|佩戴|复用|舒适|装配|视野'),
    'P5-078': ('protective_mask,face_shield', 'disinfect|sterili|reuse|material|消毒|灭菌|复用|材料'),
    'P5-079': ('protective_mask,face_shield', 'custom|scan|adjust|fit|定制|扫描|可调|贴合'),
    'P5-080': ('sampling_swab', 'sampl|collect|release|test|采样|收集|释放|检测'),
    'P5-081': ('sampling_swab', 'mechanical|strength|bend|fracture|torsion|material|力学|强度|弯曲|断裂|扭转|材料'),
    'P5-082': ('emergency_supply,protective_mask,face_shield,sampling_swab,respiratory_support', 'emergency|shortage|pandemic|distributed|应急|短缺|疫情|分布式'),
    'P5-083': ('emergency_supply,protective_mask,face_shield,sampling_swab,respiratory_support', 'quality|validat|test|traceab|clinical|质量|验证|检测|追溯|临床'),
    'P5-084': ('emergency_supply,protective_mask,face_shield,sampling_swab,respiratory_support', 'cost|capacity|supply|production|成本|产能|供应|生产'),
    'P5-085': ('respiratory_support', 'valve|pressure|flow|ventilat|respirat|阀|压力|流量|通气|呼吸'),
    'P6-086': ('anatomical_model', 'surg|planning|patient-specific|手术|规划|个体化'),
    'P6-087': ('anatomical_model', 'cardi|heart|vascular|cranio|maxill|心|血管|颅|颌'),
    'P6-088': ('anatomical_model', 'virtual|visuali|physical|reality|screen|虚拟|可视化|实体|现实|屏幕'),
    'P6-089': ('training_model', 'tactile|elastic|soft|tissue|haptic|feel|触觉|弹性|软|组织|手感'),
    'P6-090': ('training_model', 'skill|learn|performance|assessment|train|技能|学习|表现|评价|训练'),
    'P6-091': ('training_model', 'reus|repeat|replace|surg|重复|更换|手术'),
    'P6-092': ('teaching_model', 'anatom|teach|educat|解剖|教学|教育'),
    'P6-093': ('teaching_model', 'patient|communicat|consent|患者|沟通|知情'),
    'P6-094': ('teaching_model', 'cost|time|manufactur|fabricat|成本|时间|制造'),
    'P6-095': ('medical_phantom', 'density|attenuation|tomograph|ultrasound|image|密度|衰减|断层|超声|图像'),
    'P6-096': ('medical_phantom', 'radiotherap|dose|dosimetr|radiation|放疗|剂量|辐射'),
    'P6-097': ('medical_phantom', 'patient-specific|patient specific|custom|personalized|personalised|individualized|individualised|treatment plan|quality|个体化|定制|治疗计划|质量'),
    'P7-098': ('microfluidic', 'channel|resolut|material|通道|分辨率|材料'),
    'P7-099': ('microfluidic', 'droplet|flow|valve|fluid control|液滴|流动|阀|流体控制'),
    'P7-100': ('microfluidic', 'sample|separat|preparat|filter|样品|分离|制备|过滤'),
    'P7-101': ('microfluidic', 'mold|mould|replica|cast|模具|复制|浇注'),
    'P7-102': ('cell_model', 'culture|microenvironment|perfusion|cell|培养|微环境|灌流|细胞'),
    'P7-103': ('cell_model', 'organ-on-chip|organ on chip|organoid|tumor model|tumour model|disease model|tumor|tumour|器官芯片|类器官|肿瘤|疾病模型'),
    'P7-104': ('cell_model', 'scaffold|tissue formation|matrix|支架|组织形成|基质'),
    'P7-105': ('microscopy', 'structure|frame|cost|open-source|open source|结构|框架|成本|开源'),
    'P7-106': ('microscopy', 'optical|lens|resolution|image|光学|透镜|分辨率|图像'),
    'P7-107': ('microscopy', 'portable|field|smartphone|便携|现场|手机'),
    'P7-108': ('microfluidic,medical_sensor', 'pathogen|molecul|detect|diagnos|病原|分子|检测|诊断'),
    'P7-109': ('medical_sensor', 'electrochemical|electrode|电化学|电极'),
    'P7-110': ('medical_sensor,microfluidic', 'point-of-care|point of care|portable|即时|床旁|便携'),
    'P7-111': ('laboratory_device', 'open-source|open source|cost|开源|成本'),
    'P7-112': ('laboratory_device', 'modular|automat|robot|模块|自动|机器人'),
    'P7-113': ('laboratory_device', 'reproduc|validat|calibrat|performance|重复|验证|校准|性能'),
}

_STEMS = set('prosthe orthop vertebr mandib maxill craniomaxillo osseointegrat osteogen bacter antimicrob immunomod inflammat angiogen flexur thermocycl polymeri pharmaceut disintegrat dissolv paediatr pediatr orodispers gastr intestin photoiniti printab rheolog penetrat fabricat spectroscop regulat navigat stabili sterili fluoroscop resuscitat surg anatom cardi cranio teach educat communicat radiotherap dosimetr tomograph microscop pipett centrifug incubat automat retract manufactur visuali reus resolut separat preparat replica molecul diagnos reproduc validat calibrat ventilat respirat degrad interconnect post-cur post-process postprocess accur crystal acetabul reconstruct topolog segment scan custom coating surface lattice stress load fracture fatigue pore bone implant crown denture resin capsule dose material patient clinical train learn repeat sampl collect insert deliver design'.split())


@lru_cache(maxsize=4096)
def _pattern(term):
    # Boundaries prevent socket/photomask/backbone/spore substring collisions.
    norm = unicodedata.normalize('NFKC', term).casefold()
    escaped = re.escape(norm)
    if re.match(r'^[a-z0-9]', norm):
        escaped = r'(?<![a-z0-9])' + escaped
    is_stem = norm in _STEMS or norm.endswith((' train',' simulat'))
    if re.search(r'[a-z0-9]$', norm) and not is_stem:
        escaped += r'(?:s|es)?(?![a-z0-9])'
    return re.compile(escaped)


def matching_terms(text, terms):
    folded = unicodedata.normalize('NFKC', text).casefold()
    return [term for term in terms if _pattern(term).search(folded)]


def entity_applications(text, p_codes, *, disease='', bioprinting=False, topic_ids=()):
    """Conservative broad mapping; dental/tissue always require object evidence."""
    dental = disease == 'D1' or bool(matching_terms(text, ['dental','denture','tooth','teeth','orthodont','牙科','牙齿','义齿','种植牙','口腔','齿科']))
    tissue = bool(bioprinting or matching_terms(text, ['bioprint','tissue engineering','cell-laden','bioink','生物打印','组织工程','载细胞','生物墨水'])
                  or set(topic_ids).intersection({'bone_scaffold','cell_model'}))
    base = {'P1': [I], 'P2': [D] if dental else [I], 'P3': [P],
            'P4': [S], 'P5': [M], 'P6': [S], 'P7': [M]}
    apps = {a for code in p_codes for a in base.get(code,[])}
    if dental:
        apps.add(D)
    if tissue:
        apps.add(T)
    for rule in TOPICS:
        if rule['id'] in topic_ids:
            apps.update(a for a in rule['applications'] if (a != D or dental) and (a != T or tissue))
    return sorted(apps)


def association_eligibility(text):
    """A precise negative context, preserving ambiguous medical/food dual uses."""
    food = matching_terms(text, ['cultured meat','cultivated meat','vegetable protein meat','food processing',
                                'food printing','植物蛋白肉','培养肉','食品加工','食品打印'])
    medical = matching_terms(text, ['drug','pharmaceut','medicament','implant','treatment','diagnos','therap',
                                   'tissue regeneration','organ transplant','wound','clinical',
                                   '药物','治疗','诊断','组织再生','器官移植','创面','临床','植入'])
    if food and not medical:
        return 'excluded_nonmedical_context', 'Explicit food-only context: '+', '.join(food)
    return 'eligible', ''


def excerpt(text, terms=(), limit=360):
    text = re.sub(r'\s+', ' ', str(text)).strip()
    folded = unicodedata.normalize('NFKC', text).casefold()
    starts = [m.start() for term in terms if (m := _pattern(term).search(folded))]
    start = max(0, min(starts)-90) if starts else 0
    value = text[start:start+limit]
    if start:
        value = '…' + value[1:]
    if start+limit < len(text):
        value = value[:-1].rstrip() + '…'
    return value


def match_topics(text, applications=None):
    evidence = []
    for rule in TOPICS:
        if rule['id'] == 'microscopy' and not matching_terms(text.split('\n',1)[0], ['microscope','microscopy','显微镜']):
            if not matching_terms(text, ['microscope frame','microscope body','microscope stage','portable microscope','lens holder','microscope housing','显微镜支架','显微镜结构']):
                continue
        if applications is not None and not set(applications).intersection(rule['applications']):
            continue
        groups = [matching_terms(text, terms) for terms in rule['matching_terms']]
        if all(groups):
            terms = list(dict.fromkeys(term for group in groups for term in group))
            evidence.append({'topic_id': rule['id'], 'matched_terms': terms, 'excerpt': excerpt(text, terms)})
    return evidence


def question_profiles(root):
    localized = {lang: json.loads((Path(root)/'data/direction_reports'/f'{lang}.json').read_text(encoding='utf8'))
                 for lang in ('zh','en','de')}
    profiles = {}
    for did, direction in localized['zh'].items():
        for q in direction['questions']:
            qid = q['id']
            topic_ids, terms = _QUESTION_RULES[qid]
            questions = {lang: next(v for v in localized[lang][did]['questions'] if v['id'] == qid)
                         for lang in localized}
            profiles[qid] = {
                'id': qid, 'direction_id': did, 'scope': 'question', 'title': q['question'],
                'labels': {lang: v['question'] for lang,v in questions.items()},
                'focus': {lang: v.get('focus') or v['question'] for lang,v in questions.items()},
                'topic_ids': topic_ids.split(','), 'facets': terms.split('|'),
                'clinical_comparison': qid in {'P2-018','P2-021','P2-029','P2-030','P2-031','P4-070','P4-071','P4-072','P6-088','P6-090','P6-092','P6-093'},
            }
    return profiles


def match_report(profile, text, topic_evidence):
    relevant = [e for e in topic_evidence if e['topic_id'] in profile['topic_ids']]
    if not relevant:
        return None
    facet_terms = matching_terms(text, profile.get('facets', []))
    if profile.get('facets') and not facet_terms:
        return None
    return {'score': min(100, 50 + 5*len(relevant) + 3*len(facet_terms)),
            'topic_ids': [e['topic_id'] for e in relevant],
            'matched_terms': list(dict.fromkeys(t for e in relevant for t in e['matched_terms'])),
            'facet_terms': facet_terms, 'evidence_excerpt': excerpt(text, facet_terms or relevant[0]['matched_terms']),
            'evidence_role': 'technical_context_only' if profile.get('clinical_comparison') else 'technical_scheme_candidate'}


def normalize_applicant(name):
    text = unicodedata.normalize('NFKC', str(name)).casefold().replace('&', ' and ')
    for dotted, canonical in [(r'n\s*\.\s*v', 'nv'),(r'b\s*\.\s*v', 'bv'),
                              (r's\s*\.\s*p\s*\.\s*a','spa'),(r's\s*\.\s*r\s*\.\s*l','srl'),(r's\s*\.\s*a','sa')]:
        text = re.sub(r'\b'+dotted+r'\s*\.?$', canonical, text)
    text = re.sub(r'[^\w\s]', ' ', text, flags=re.UNICODE)
    tokens = text.split()
    legal_forms = {'inc':'incorporated','corp':'corporation','co':'company','ltd':'limited'}
    return ' '.join(legal_forms.get(token, token) for token in tokens)


def applicant_name_matches(company_name, applicant_name):
    left, right = normalize_applicant(company_name), normalize_applicant(applicant_name)
    # Short brands/acronyms need independent identity evidence. No subsidiaries,
    # inferred ownership, fuzzy aliases or substring matching are accepted.
    substantive = re.sub(r'\b(?:incorporated|corporation|company|limited|gmbh|ag|nv|bv|llc|llp|plc|sa|sarl|srl|spa|kg|pte|pty)\b', '', left)
    return bool(left == right and len(substantive.replace(' ','')) >= 6 and substantive.strip() not in {'medical','systems','solutions','technology','technologies'})

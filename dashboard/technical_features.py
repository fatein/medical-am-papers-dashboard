"""Literal source mentions, including alternatives; no inferred claims or efficacy."""
import re
# Ambiguous PLA/PCL/SLS/SLA abbreviations alone are deliberately omitted.
FEATURES=[
 ('titanium','material','钛','Titanium','Titan','titanium|钛'),
 ('tantalum','material','钽','Tantalum','Tantal','tantalum|钽'),
 ('cobalt_chromium','material','钴铬','Cobalt–chromium','Kobalt–Chrom','cobalt chromium|cobalt-chromium|钴铬'),
 ('peek','material','聚醚醚酮','Polyetheretherketone','Polyetheretherketon','polyetheretherketone|聚醚醚酮'),
 ('polycaprolactone','material','聚己内酯','Polycaprolactone','Polycaprolacton','polycaprolactone|聚己内酯'),
 ('polylactic_acid','material','聚乳酸','Polylactic acid','Polymilchsäure','polylactic acid|poly(lactic acid)|polylactide|聚乳酸'),
 ('hydroxyapatite','material','羟基磷灰石','Hydroxyapatite','Hydroxylapatit','hydroxyapatite|羟基磷灰石'),
 ('zirconia','material','氧化锆','Zirconia','Zirkonoxid','zirconia|zirconium dioxide|氧化锆'),
 ('hydrogel','material','水凝胶','Hydrogel','Hydrogel','hydrogel|水凝胶'),
 ('gelatin','material','明胶','Gelatin','Gelatine','gelatin|gelatine|明胶'),
 ('alginate','material','海藻酸盐','Alginate','Alginat','alginate|海藻酸'),
 ('silk_fibroin','material','丝素蛋白','Silk fibroin','Seidenfibroin','silk fibroin|丝素蛋白'),
 ('collagen','material','胶原','Collagen','Kollagen','collagen|胶原'),
 ('laser_powder_bed','process','激光粉末床熔融','Laser powder bed fusion','Laser-Pulverbettfusion','laser powder bed fusion|selective laser melting|激光粉末床熔融|选择性激光熔化'),
 ('fused_deposition','process','熔融沉积','Fused deposition','Schmelzschichtung','fused deposition|fused filament fabrication|熔融沉积'),
 ('stereolithography','process','立体光刻','Stereolithography','Stereolithografie','stereolithography|立体光刻'),
 ('digital_light_processing','process','数字光处理','Digital light processing','Digitale Lichtverarbeitung','digital light processing|数字光处理'),
 ('binder_jetting','process','粘结剂喷射','Binder jetting','Binder-Jetting','binder jetting|粘结剂喷射'),
 ('two_photon','process','双光子聚合','Two-photon polymerization','Zwei-Photonen-Polymerisation','two-photon polymerization|two photon polymerization|双光子聚合'),
 ('porous_structure','design','孔隙与多孔结构','Pores and porous structures','Poren und poröse Strukturen','porous|porosity|pore|pores|多孔|孔隙|孔径'),
 ('lattice_structure','design','晶格结构','Lattice structures','Gitterstrukturen','lattice|lattices|晶格'),
 ('scaffold_design','design','支架设计','Scaffold design','Gerüstdesign','scaffold|scaffolds|支架'),
 ('surface_coating','design','表面涂层','Surface coatings','Oberflächenbeschichtungen','surface coating|coating|coatings|表面涂层'),
 ('multilayer','design','多层结构','Multilayer structures','Mehrschichtstrukturen','multilayer|multi-layer|layered structure|多层结构'),
 ('microchannel','design','微流道','Microchannels','Mikrokanäle','microchannel|microchannels|micro-channel|微流道|微通道'),
 ('bone_ingrowth','focus','骨长入／骨整合关注点','Bone ingrowth / osseointegration focus','Fokus Knocheneinwachsen / Osseointegration','bone ingrowth|osseointegration|骨长入|骨整合'),
 ('controlled_release','focus','控释关注点','Controlled-release focus','Fokus kontrollierte Freisetzung','controlled release|sustained release|controlled-release|sustained-release|控释|缓释'),
 ('fatigue','focus','疲劳关注点','Fatigue focus','Fokus Ermüdung','fatigue|疲劳'),
 ('sterilization','focus','灭菌关注点','Sterilization focus','Fokus Sterilisation','sterilization|sterilisation|灭菌'),
 ('dosimetry','focus','剂量测量关注点','Dosimetry focus','Fokus Dosimetrie','dosimetry|dosimetric|剂量测量'),
]
_INDEX={r[0]:r for r in FEATURES}

def feature_label(ident,code='zh'):
    return _INDEX[ident][{'zh':2,'en':3,'de':4}[code]]

def _pattern(term):
    before=r'(?<![A-Za-z0-9])' if re.match('[a-zA-Z]',term) else ''
    after=r'(?![A-Za-z0-9])' if re.search('[a-zA-Z]$',term) else ''
    return re.compile(before+re.escape(term)+after,re.I)

_RULES=[(row,[(t,_pattern(t)) for t in row[-1].split('|')]) for row in FEATURES]

def extract_technical_features(text):
    text=re.sub(r'\s+',' ',str(text)).strip(); rows=[]
    for feature,patterns in _RULES:
        hits=[(term,m) for term,pattern in patterns if (m:=pattern.search(text))]
        if not hits: continue
        first=min(m.start() for _,m in hits); start=max(0,first-75); quote=text[start:start+280]
        if start: quote='…'+quote[1:]
        if start+280<len(text): quote=quote[:-1]+'…'
        rows.append(dict(id=feature[0],group=feature[1],matched_terms=[t for t,_ in hits],excerpt=quote))
    return rows

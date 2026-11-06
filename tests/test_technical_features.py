from dashboard.technical_features import extract_technical_features,feature_label

def test_specific_material_and_process_mentions_are_literal_and_traceable():
    rows=extract_technical_features('A titanium porous implant made by selective laser melting; pore size is varied.')
    assert {'titanium','laser_powder_bed','porous_structure'} <= {r['id'] for r in rows}
    assert all(r['matched_terms'] and len(r['excerpt'])<=280 for r in rows)
    assert feature_label('titanium','zh')=='钛'

def test_generic_printing_and_ambiguous_abbreviations_do_not_invent_process_or_material():
    rows=extract_technical_features('A printed device. PCL reconstruction of a knee; PLA assay and a peek inside.')
    assert not rows

def test_cross_resource_features_keep_materials_separate_from_measured_effects():
    rows=extract_technical_features('A polycaprolactone scaffold for controlled release and bone ingrowth.')
    assert {r['group'] for r in rows}=={'material','design','focus'}

import gzip
import json
from pathlib import Path

import pandas as pd
import pytest

from dashboard.patent_data import (PUBLIC_PATENT_FIELDS, build_snapshot, filter_patents,
                                   load_patents, project_patent)


def source_record(ident='EP1A1', year=2020, applications=None, applicants=None):
    return {'publication_id':ident,'family_id':'family-'+ident,'country':'EP','kind':'A1',
            'publication_date':f'{year}-03-04' if year else None,
            'titles':[{'lang':'en','text':'Original dental implant title'}],
            'abstracts':[{'lang':'en','text':'3D printed dental implant. '*50}],
            'applicants':[{'name':name} for name in (applicants or ['ACME','原始申请人'])],
            'source_url':'https://worldwide.espacenet.com/patent/search?q=pn%3D'+ident,
            'screening':{'decision':'included_direct','version':'strict-medical-am-1.2'},
            'strict_screening':{'decision':'included_direct','version':'strict-medical-am-1.2',
                                'medical_categories':applications or ['dental']},
            'private_source_path':r'E:\private\original.xml'}


def frame():
    rows=[project_patent(source_record()),
          project_patent(source_record('EP2A1',2022,['implants_and_prostheses'],['ACME GmbH'])),
          project_patent(source_record('EP3A1',None,['dental','tissue_engineering_and_bioprinting'],['UNIVERSITY']))]
    return pd.DataFrame(rows)


def test_projection_includes_only_public_display_fields_and_short_original_excerpt():
    row=project_patent(source_record())
    assert set(row)==set(PUBLIC_PATENT_FIELDS)
    assert row['title']=='Original dental implant title'
    assert row['applicants']==['ACME','原始申请人']
    assert len(row['abstract_excerpt'])<=361
    assert 'private' not in json.dumps(row,ensure_ascii=False)
    assert 'abstract' not in row


def test_unscreened_and_number_mismatched_source_links_are_rejected():
    row=source_record(); row['strict_screening']['decision']='excluded_insufficient_evidence'
    with pytest.raises(ValueError): project_patent(row)
    for url in ['javascript:alert(1)','https://worldwide.espacenet.com/patent/search?q=pn%3DEP999A1']:
        row=source_record(); row['source_url']=url
        with pytest.raises(ValueError): project_patent(row)


@pytest.mark.parametrize('ident',['TWI608928B','SG11201910191RA'])
def test_regional_publication_number_formats_remain_exact(ident):
    assert project_patent(source_record(ident))['source_url'].endswith(ident)


def test_filters_combine_dimensions_and_use_exact_applicant_membership():
    result=filter_patents(frame(),applications=['dental','implants_and_prostheses'],applicants=['ACME'],years=(2019,2021),include_unknown_year=False)
    assert result.publication_id.tolist()==['EP1A1']
    assert filter_patents(frame(),applicants=['ACME']).publication_id.tolist()==['EP1A1']
    assert set(filter_patents(frame(),applicants=['ACME','UNIVERSITY']).publication_id)=={'EP1A1','EP3A1'}


def test_multilabel_applications_and_empty_selections_have_explicit_semantics():
    assert set(filter_patents(frame(),applications=['dental']).publication_id)=={'EP1A1','EP3A1'}
    assert filter_patents(frame(),applications=[]).empty
    assert len(filter_patents(frame(),applicants=[]))==3


def test_unknown_publication_years_and_literal_search_are_handled():
    assert set(filter_patents(frame(),years=(2022,2022),include_unknown_year=True).publication_id)=={'EP2A1','EP3A1'}
    assert filter_patents(frame(),years=(2022,2022),include_unknown_year=False).publication_id.tolist()==['EP2A1']
    assert filter_patents(frame(),query='[').empty
    assert filter_patents(frame(),query='ep2a1').publication_id.tolist()==['EP2A1']


def test_snapshot_roundtrip_is_portable_and_detects_data_manifest_mismatch(tmp_path):
    source=tmp_path/'strict.jsonl'
    source.write_text(json.dumps(source_record(),ensure_ascii=False)+'\n',encoding='utf-8')
    destination=tmp_path/'site'
    manifest=build_snapshot(source,destination,expected_count=1)
    loaded=load_patents(destination)
    assert len(loaded)==manifest['publications']==1
    assert loaded.iloc[0].source_url.endswith('EP1A1')
    assert 'private_source_path' not in loaded
    path=destination/'data/patents.jsonl.gz'
    path.write_bytes(gzip.compress(b'',mtime=0))
    with pytest.raises(ValueError): load_patents(destination)


def test_real_published_snapshot_contains_only_the_strict_5516_records():
    root=Path(__file__).resolve().parents[1]
    records=load_patents(root)
    assert len(records)==5516
    assert records.publication_id.nunique()==5516
    assert records.family_id.nunique()==4862
    assert all(isinstance(value,list) for value in records.applicants)
    assert records.source_url.str.startswith('https://worldwide.espacenet.com/patent/search?q=').all()


def test_public_package_validation_rejects_corrupt_patent_snapshot_early(tmp_path, monkeypatch):
    from dashboard import public_data
    source=tmp_path/'strict.jsonl'
    source.write_text(json.dumps(source_record())+'\n',encoding='utf-8')
    site=tmp_path/'site'
    build_snapshot(source,site,expected_count=1)
    (site/'data/patents.jsonl.gz').write_bytes(gzip.compress(b'',mtime=0))
    monkeypatch.setattr(public_data,'public_package_files',lambda root:frozenset({
        'data/patents.jsonl.gz','data/patents_manifest.json'}))
    with pytest.raises(ValueError,match='integrity'):
        public_data.validate_public_package(site)

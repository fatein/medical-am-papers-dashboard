"""Apply the reviewed exact-key corrections without modifying source records."""
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'outputs/full_i18n_review_20261103'
manifest={}
for code in ('en','de'):
    target=ROOT/'data/i18n'/f'{code}.json'
    catalogue=json.loads(target.read_text('utf8'))
    merged={}
    counts={}
    for domain in ('enterprise','academic'):
        patches=json.loads((OUT/f'{domain}_patches_{code}.json').read_text('utf8'))
        counts[domain]=len(patches)
        for source,value in patches.items():
            if not isinstance(value,str) or not value.strip() or '\ufffd' in value:
                raise ValueError(f'Invalid patch: {code}/{source}')
            if source in merged and merged[source]!=value:
                raise ValueError(f'Conflicting patches: {code}/{source}')
            merged[source]=value
    followup_path=OUT/f'academic_followup_{code}.json'
    if followup_path.exists():
        followup=json.loads(followup_path.read_text('utf8'))
        counts['primary_source_followup']=len(followup)
        merged.update(followup)
    changes_path=OUT/f'changes_{code}.json'
    changed=json.loads(changes_path.read_text('utf8')) if changes_path.exists() else {}
    for key,value in merged.items():
        if catalogue.get(key)!=value or key in changed:
            changed[key]={'before':changed.get(key,{}).get('before',catalogue.get(key)),'after':value}
    catalogue.update(merged)
    target.write_text(json.dumps(catalogue,ensure_ascii=False,indent=2)+'\n','utf8')
    changes_path.write_text(json.dumps(changed,ensure_ascii=False,indent=2)+'\n','utf8')
    manifest[code]={'patches':counts,'changed':len(changed),'catalogue_entries':len(catalogue)}
(OUT/'merge_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n','utf8')
print(json.dumps(manifest,indent=2))

direction_path=OUT/'direction_followup.json'
if direction_path.exists():
    for patch in json.loads(direction_path.read_text('utf8')):
        path=ROOT/patch['path']
        data=json.loads(path.read_text('utf8'))
        keys=patch['pointer'].strip('/').split('/')
        node=data
        for key in keys[:-1]:
            node=node[int(key)] if isinstance(node,list) else node[key]
        key=int(keys[-1]) if isinstance(node,list) else keys[-1]
        if node[key] not in (patch['before'],patch['after']):
            raise ValueError(f'Direction report changed since review: {patch["pointer"]}')
        node[key]=patch['after']
        path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n','utf8')

"""Synchronize reviewed files only, retaining backups and independent changes."""
import hashlib,json,shutil,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE='46f86682e7a0da058032df18aeb456750cff5dd8'
FILES=['dashboard/i18n.py','dashboard/views.py','dashboard/enterprise_views.py',
       'data/i18n/en.json','data/i18n/de.json','data/direction_reports/de.json',
       'tests/test_i18n.py','tests/test_i18n_presentation.py','tests/test_localization_content.py',
       'scripts/audit_dashboard_rendering.py','scripts/audit_ui_catalogue.py',
       'scripts/apply_localization_review.py','scripts/sync_localization_release.py',
       'docs/localization-review-2026-11-03.md',
       'docs/superpowers/plans/2026-11-03-full-dashboard-localization-audit.md']
FILES.extend(['dashboard/cross_views.py','dashboard/feedback_views.py','app.py'])
TARGETS=[ROOT.parent/'dashboard_project_20261002',Path('E:/毕业论文——知识库/文件归档/模型训练/5、dashboard制作')]
norm=lambda value:value.replace(b'\r\n',b'\n')
for target in TARGETS:
    assert target.is_dir(),target
    prior_path=target/'outputs/full_i18n_review_20261103/release_manifest.json'
    prior=json.loads(prior_path.read_text('utf8')) if prior_path.exists() else {}
    prior_hashes={row['path']:row['sha256'] for row in prior.get('files',[])}
    for rel in [path for path in FILES if path=='app.py' or path.startswith(('dashboard/','data/direction_reports/'))]:
        dst=target/rel
        base=subprocess.check_output(['git','-c','safe.directory=*','show',BASE+':'+rel],cwd=ROOT)
        if (dst.exists() and norm(dst.read_bytes()) not in (norm(base),norm((ROOT/rel).read_bytes()))
                and hashlib.sha256(dst.read_bytes()).hexdigest()!=prior_hashes.get(str(dst))):
            raise RuntimeError('Independent local changes require merge: '+str(dst))
for target in TARGETS:
    out=target/'outputs/full_i18n_review_20261103'
    out.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for rel in FILES:
        src=ROOT/rel;dst=target/rel
        if dst.exists() and dst.read_bytes()!=src.read_bytes():
            backup=out/'before'/rel
            backup.parent.mkdir(parents=True,exist_ok=True)
            if not backup.exists():shutil.copy2(dst,backup)
        dst.parent.mkdir(parents=True,exist_ok=True)
        if rel.startswith('data/i18n/') and dst.exists():
            # Retain unused local catalogue extensions, with all reviewed
            # published keys taking precedence over older local translations.
            old=json.loads(dst.read_text('utf8'))
            reviewed=json.loads(src.read_text('utf8'))
            dst.write_text(json.dumps({**old,**reviewed},ensure_ascii=False,indent=2)+'\n','utf8')
            synchronized=json.loads(dst.read_text('utf8'))
            assert all(synchronized[key]==value for key,value in reviewed.items())
        else:
            shutil.copy2(src,dst)
            assert dst.read_bytes()==src.read_bytes()
        manifest.append({'path':str(dst),'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()})
    audit=ROOT/'outputs/full_i18n_review_20261103'
    for src in audit.iterdir():
        if src.is_file() and (src.suffix in ('.json','.md','.jpg') or src.name in ('tests_release.log','runtime_final.log')):
            shutil.copy2(src,out/src.name)
    commit=subprocess.check_output(['git','-c','safe.directory=*','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    (out/'release_manifest.json').write_text(json.dumps({'commit':commit,'files':manifest},ensure_ascii=False,indent=2),'utf8')
    print('Synchronized',len(FILES),'reviewed files to',target)

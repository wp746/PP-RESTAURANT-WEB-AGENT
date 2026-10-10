"""Command-line interface for portable AI agents. On a successful publish, stdout is ONLY the URL."""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from html import escape
from pathlib import Path

from .design import create_plan, create_site, shortlist, revise_site, scout_live_references
from .io import extract_zip, collect_text, locate_merchant_manifest, optimize_images, extract_basic_facts, InputError
from .llm import Model, ModelError
from .publish import bootstrap_existing, merge_store, deploy, protect_site_root, slug_guard, PublishError
from .quality import validate_site, audit_browser, QualityError

class WorkflowError(RuntimeError):pass

def progress(text:str):print('[ppweb] '+text,file=sys.stderr)

def safe_script(js:str):return js.replace('</script','<\\/script').replace('</SCRIPT','<\\/SCRIPT')

def build_document(parts:dict, merchant_name:str):
    html=parts['html'].strip()
    css=parts['css'].strip()
    js=parts['js'].strip()
    if not html.lower().startswith('<!doctype html>'):
        raise WorkflowError('AI did not return a complete HTML document')
    if not re.search(r'</head>',html,re.I) or not re.search(r'</body>',html,re.I):
        raise WorkflowError('HTML structure malformed')
    if re.search(r'<(?:script|style)\b',html,re.I):raise WorkflowError('Code generator returned embedded script/style in HTML instead of separated fields')
    html=re.sub(r'<html\b','<html data-pp-brand-site="true"',html,count=1,flags=re.I)
    html=re.sub(r'</head>',lambda m:'<style>\n'+css+'\n</style>\n'+m.group(0),html,count=1,flags=re.I)
    html=re.sub(r'</body>',lambda m:'<script>\n'+safe_script(js)+'\n</script>\n'+m.group(0),html,count=1,flags=re.I)
    return html


def demo_design(facts:dict,photos:list[dict]):
    """A functioning offline smoke-test only. Never eligible for public deployment."""
    title=escape(facts.get('name','演示门店'))
    category=escape(facts.get('category','餐饮体验'))
    img=photos[0]['path'] if photos else None
    hero=f'<img class="hero-image" src="{img}" alt="提供的菜品照片" loading="eager">' if img else '<div class="empty">请提供真实菜品照片</div>'
    html=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}｜离线流程测试（不可发布）</title></head><body><header class="top">PP · PREVIEW ONLY <span>非正式交付</span></header><main><section class="hero"><div><p class="eyebrow">CULTURE FIRST / TEST MODE</p><h1>{title}</h1><p class="lead">{category} · 这只是用于验证素材解压、排版渲染和质量检查的离线演示。</p><button id="toggle" aria-expanded="false" aria-controls="details">查看演示说明</button><p id="details" hidden>正式版会使用具备文本及视觉能力的模型，按门店属性和参考库原创设计。此页面不能发布。</p></div>{hero}</section></main><footer>PP WEB STUDIO · MOCK BUILD</footer></body></html>'''
    css='''*{box-sizing:border-box}body{margin:0;background:#f6f0e6;color:#192c27;font-family:system-ui,'PingFang SC',sans-serif}.top{padding:24px 6%;border-bottom:1px solid #d4caba;font-size:13px;letter-spacing:.1em;display:flex;justify-content:space-between}.hero{display:grid;grid-template-columns:1fr 1fr;gap:8%;align-items:center;max-width:1200px;margin:auto;min-height:80vh;padding:70px 6%}.hero-image{width:100%;max-height:70vh;object-fit:contain;border-radius:180px 180px 6px 6px}.eyebrow{letter-spacing:.22em;color:#bc4d32}h1{font:700 clamp(52px,8vw,104px)/1.2 'Songti SC',serif}.lead{max-width:450px;line-height:2}button{padding:18px 25px;background:#264c3e;color:white;border:0;cursor:pointer}button:focus-visible{outline:3px solid #bc4d32}.empty{border:2px dashed #999;min-height:260px;display:grid;place-items:center}footer{padding:30px 6%;font-size:12px;border-top:1px solid #d4caba}@media(max-width:700px){.hero{grid-template-columns:1fr;padding:35px 22px;gap:25px}.hero-image{max-height:50vh}h1{font-size:56px}}@media(prefers-reduced-motion:reduce){*,*:before,*:after{transition:none!important;animation:none!important}}'''
    js='''const toggle=document.getElementById('toggle');const details=document.getElementById('details');toggle.addEventListener('click',()=>{details.hidden=!details.hidden;toggle.setAttribute('aria-expanded',String(!details.hidden));});'''
    return {'html':html,'css':css,'js':js}


def write_json(path:Path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')


def package_tree(src:Path,zip_path:Path):
    zip_path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED,compresslevel=7) as z:
        for p in sorted(src.rglob('*')):
            if p.is_file():z.write(p,p.relative_to(src).as_posix())


def sync_git_sites(repo_root:Path,slug:str):
    """Optional state synchronization for agents running in a real Git clone.
    Requires preconfigured GitHub authentication. Does not upload raw ZIP inputs.
    """
    import subprocess
    git=repo_root/'.git'
    if not git.exists():raise WorkflowError('--git-sync requires a Git checkout, not a downloaded ZIP')
    commands=[
        ['git','add','--','sites'],
        ['git','commit','-m',f'Publish approved restaurant website: {slug}'],
        ['git','push','origin','HEAD'],
    ]
    for i,cmd in enumerate(commands):
        r=subprocess.run(cmd,cwd=repo_root,capture_output=True,text=True,timeout=80)
        if i==1 and r.returncode and 'nothing to commit' in r.stdout.lower():continue
        if r.returncode:
            raise WorkflowError('Cloudflare deployed but Git state was NOT synchronized! Manually reconcile before another deployment: '+r.stderr[-350:])


def execute(args):
    archive=Path(args.input_zip).resolve()
    if not archive.exists():raise WorkflowError('ZIP not found: '+str(archive))
    slug_guard(args.slug)
    w=Path(args.workdir).resolve()/args.slug
    if w.exists() and not args.replace_workdir:raise WorkflowError(f'Workdir exists: {w}. Use a new workdir or --replace-workdir.')
    if w.exists():shutil.rmtree(w)
    w.mkdir(parents=True)
    inbound=w/'input';out=w/'output';store=out/'merchant';store.mkdir(parents=True)
    progress('P0–P2: safe intake and evidence inventory')
    files=extract_zip(archive,inbound)
    docs=collect_text(files,inbound)
    manifest=locate_merchant_manifest(files)
    facts,evidence=extract_basic_facts(docs,manifest)
    photos=optimize_images(files,store/'assets')
    missing=[x for x in ('name','category') if not facts.get(x)]
    trace={'files_count':len(files),'docs_count':len(docs),'photos_count':len(photos),
           'facts':facts,'evidence':evidence,'missing_critical':missing,
           'approval':{'publish_approved':manifest.get('approved_for_publication') is True,
                       'media_rights_confirmed':manifest.get('media_rights_confirmed') is True}}
    write_json(out/'intake-report.json',trace)
    if missing:raise WorkflowError(f'Missing verified merchant fields: {missing}. See {out/"intake-report.json"}')
    if not photos and not args.demo:raise WorkflowError('No readable product/store photos; production visual design requires real imagery')
    if args.title_font_path:
        if manifest.get('font_rights_confirmed') is not True:
            raise WorkflowError('Custom title font requested without font_rights_confirmed=true in merchant.yaml')
        from .typography import render_title
        photo=render_title(facts['name'],Path(args.title_font_path),store/'assets/brand-title.png')
        photos.append(photo)
    progress('P3–P6: research selection, brand DNA, art direction, UX content')
    if args.demo:
        plan={'status':'offline_mock_not_publishable','category':facts.get('category'),'references':shortlist(facts['category'])}
        parts=demo_design(facts,photos)
    else:
        model=Model()
        image_paths=[p for p in files if p.suffix.lower() in {'.jpg','.jpeg','.png','.webp'}][:8]
        refs=shortlist(facts.get('category','餐饮'),facts.get('name',''))
        live=scout_live_references(refs) if not args.offline_references else []
        write_json(out/'reference-report.json',{'shortlist':refs,'live_metadata':live})
        plan=create_plan(model,facts,evidence,docs,photos,image_paths,live_report=live)
        parts=create_site(model,facts,plan,photos)
    write_json(out/'brand-plan.json',plan)
    allowed=[]
    for key in ('map_url','official_url','contact_url'):
        if isinstance(facts.get(key),str) and facts[key].startswith('https://'):allowed.append(facts[key])
    progress('P7–P8: assemble, static audit and real-browser QA; repair on failure')
    checked=None
    for attempt in range(3 if not args.demo else 1):
        try:
            page=build_document(parts,facts['name'])
            (store/'index.html').write_text(page,encoding='utf-8')
            write_json(store/'public-store.json',{'name':facts['name'],'category':facts['category']})
            checked=validate_site(parts['html'],parts['css'],parts['js'],store,allowed_outbound=allowed)
            if not args.demo:
                from .review import factual_review
                checked['facts_review']=factual_review(model,facts,evidence,docs,parts['html'])
            if not args.skip_browser:
                checked['browser']=audit_browser(store/'index.html',out/'screenshots')
                if not args.demo and not args.no_visual_review:
                    from .review import visual_review
                    imgs=[out/'screenshots/390x844.png',out/'screenshots/1440x900.png']
                    checked['art_direction_review']=visual_review(model,plan,imgs,facts['name'])
            else:
                checked['browser']='NOT TESTED (deployment prohibited)'
            break
        except (QualityError,WorkflowError) as err:
            if args.demo or attempt>=2:raise
            progress(f'QA repair pass {attempt+1}: {str(err)[:150]}')
            parts=revise_site(model,facts,plan,photos,parts,str(err))
    write_json(out/'quality-report.json',checked)
    # staging from previous complete site to prevent multi-tenant destruction
    base=Path(args.sites_dir).resolve()
    site_snapshot=out/'site_snapshot'
    if args.publish or args.create_snapshot:
        if not (base/'index.html').exists():
            raise WorkflowError('Existing site state absent. Run `ppweb bootstrap` first, from current production ZIP; do not overwrite merchants.')
        shutil.copytree(base,site_snapshot)
        merge_store(site_snapshot,store,args.slug,args.replace)
        package_tree(site_snapshot,out/'upload-all-stores.zip')
    write_json(out/'run-report.json',{'slug':args.slug,'preview_html':str(store/'index.html'),'publish_requested':args.publish,'can_publish':not args.demo and not args.skip_browser,'facts':facts,'quality':checked})
    if not args.publish:
        print(str(store/'index.html'))
        return
    if args.demo or args.skip_browser or args.no_visual_review:raise WorkflowError('Demo, browser-skipped or visually-unreviewed build may not publish')
    if manifest.get('approved_for_publication') is not True or manifest.get('media_rights_confirmed') is not True:
        raise WorkflowError('Owner approval & media rights missing. Set both booleans true in merchant.yaml after confirmation.')
    if not args.confirm_publish:raise WorkflowError('Pass --confirm-publish (explicit publication authorization)')
    progress('P9–P10: production deploy, verify, then sync canonical site snapshot')
    url=deploy(site_snapshot,os.getenv('CLOUDFLARE_PROJECT_NAME','pp-restaurants'),
               os.getenv('PP_SITE_BASE_URL','https://pp-restaurants.pages.dev'),args.slug,facts['name'])
    # Promote local snapshot only after actual deployment verification.
    backup=base.with_name(base.name+'.backup')
    if backup.exists():shutil.rmtree(backup)
    shutil.move(str(base),str(backup))
    try:shutil.copytree(site_snapshot,base)
    except Exception:
        if base.exists():shutil.rmtree(base)
        shutil.move(str(backup),str(base))
        raise
    # Do not publish business records / ownership docs into a public Git repository.
    if args.git_sync:
        progress('Syncing approved public site snapshots to GitHub')
        sync_git_sites(Path(__file__).resolve().parents[1],args.slug)
    print(url)


def remove(args):
    slug_guard(args.slug)
    if args.confirm!=args.slug:raise WorkflowError(f'Type --confirm {args.slug} to remove this shop')
    root=Path(args.sites_dir).resolve()
    if not (root/args.slug/'index.html').exists():raise WorkflowError('Shop not found')
    with tempfile.TemporaryDirectory(prefix='ppweb-remove-') as d:
        stage=Path(d)/'sites';shutil.copytree(root,stage)
        shutil.rmtree(stage/args.slug)
        from .publish import update_directory_index
        update_directory_index(stage)
        if args.publish:
            if not args.confirm_publish:raise WorkflowError('Use --confirm-publish to remove from live site')
            url=deploy_remove(stage,slug=args.slug)
            backup=root.with_name(root.name+'.backup')
            if backup.exists():shutil.rmtree(backup)
            shutil.move(str(root),str(backup));shutil.copytree(stage,root)
            print(url)
        else:
            package_tree(stage,Path(args.output_zip).resolve())
            print(str(Path(args.output_zip).resolve()))

def deploy_remove(stage:Path,slug:str):
    """Remove with Wrangler; production verification confirms 404 not disappearance from index only."""
    import subprocess,urllib.request,urllib.error,time
    from .publish import PublishError
    if not os.getenv('CLOUDFLARE_API_TOKEN') or not os.getenv('CLOUDFLARE_ACCOUNT_ID'):
        raise PublishError('Cloudflare credentials absent')
    project=os.getenv('CLOUDFLARE_PROJECT_NAME','pp-restaurants')
    r=subprocess.run(['npx','--yes','wrangler@4','pages','deploy',str(stage),'--project-name',project,'--branch','main'],capture_output=True,text=True,timeout=180)
    if r.returncode:raise PublishError('Failed to publish site removal: '+r.stderr[-400:])
    base=os.getenv('PP_SITE_BASE_URL','https://pp-restaurants.pages.dev')
    url=base.rstrip('/')+'/'+slug+'/'
    for _ in range(8):
        try:
            urllib.request.urlopen(url,timeout=8)
        except urllib.error.HTTPError as e:
            if e.code==404:return base.rstrip('/')+'/'
        except urllib.error.URLError:pass
        time.sleep(3)
    raise PublishError('Unable to confirm 404 after removal; inspect deployment manually')


def main(argv=None):
    ap=argparse.ArgumentParser(prog='ppweb',description='PP Restaurant Web Agent (culture-first)')
    sub=ap.add_subparsers(dest='command',required=True)
    p=sub.add_parser('run',help='ZIP -> design -> QA -> optional Cloudflare deploy')
    p.add_argument('input_zip');p.add_argument('--slug',required=True)
    p.add_argument('--workdir',default='.ppweb-work');p.add_argument('--sites-dir',default='sites')
    p.add_argument('--demo',action='store_true',help='offline smoke test only; impossible to publish')
    p.add_argument('--replace',action='store_true',help='update existing store')
    p.add_argument('--replace-workdir',action='store_true')
    p.add_argument('--skip-browser',action='store_true',help='offline diagnostic only; impossible to publish')
    p.add_argument('--no-visual-review',action='store_true',help='debug only; disables AI screenshot art-direction critique')
    p.add_argument('--offline-references',action='store_true',help='skip live reference site metadata check')
    p.add_argument('--create-snapshot',action='store_true')
    p.add_argument('--title-font-path',default=None,help='verified local font; owner rights required; creates transparent brand-title.png')
    p.add_argument('--git-sync',action='store_true',help='after successful deployment commit only sites/ and push branch to origin')
    p.add_argument('--publish',action='store_true');p.add_argument('--confirm-publish',action='store_true')
    b=sub.add_parser('bootstrap',help='Import EXACT existing production snapshot, preserving older merchants')
    b.add_argument('production_zip');b.add_argument('--sites-dir',default='sites');b.add_argument('--force',action='store_true')
    d=sub.add_parser('remove',help='Remove a merchant path after approval')
    d.add_argument('slug');d.add_argument('--sites-dir',default='sites');d.add_argument('--confirm',required=True)
    d.add_argument('--publish',action='store_true');d.add_argument('--confirm-publish',action='store_true');d.add_argument('--output-zip',default='removed-site-snapshot.zip')
    a=ap.parse_args(argv)
    try:
        if a.command=='run':execute(a)
        elif a.command=='bootstrap':
            bootstrap_existing(Path(a.production_zip),Path(a.sites_dir),a.force)
            print(str(Path(a.sites_dir).resolve()))
        elif a.command=='remove':remove(a)
    except (InputError,ModelError,QualityError,PublishError,WorkflowError) as e:
        progress('STOP: '+str(e))
        return 2
    return 0

if __name__=='__main__':sys.exit(main())

"""Publish a complete multi-merchant snapshot without destroying other stores."""
from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

class PublishError(RuntimeError):pass


def slug_guard(slug:str):
    if not re.fullmatch(r'[a-z][a-z0-9-]{1,39}',slug):
        raise PublishError('Slug must match [a-z][a-z0-9-]{1,39}')
    if slug in {'admin','api','assets','index','preview','sites','static'}:
        raise PublishError('Reserved slug')


def protect_site_root(root:Path,slug:str,replace:bool):
    slug_guard(slug)
    if not (root/'index.html').is_file():
        raise PublishError('Missing sites/index.html! First bootstrap from EXISTING production ZIP. Deploy blocked to avoid removing other stores.')
    dest=root/slug
    if dest.exists() and not replace:
        raise PublishError(f'{slug} already exists; pass --replace only after confirming update')
    return dest


def merge_store(site_root:Path,store_dir:Path,slug:str,replace:bool):
    """Never mutate production sources in-place until all design checks pass."""
    dest=protect_site_root(site_root,slug,replace)
    if not (store_dir/'index.html').exists():raise PublishError('New store has no index.html')
    if dest.exists():shutil.rmtree(dest)
    shutil.copytree(store_dir,dest)
    update_directory_index(site_root)
    return dest


def bootstrap_existing(archive:Path,target:Path,force=False):
    """One-time import: the LIVE site snapshot, not a generated empty site."""
    from .io import extract_zip
    if target.exists() and any(target.iterdir()) and not force:
        raise PublishError('sites/ already initialized; refusing to overwrite')
    if force and target.exists():shutil.rmtree(target)
    # Only copy HTML/images/CSS/JS from trusted export. ZIP extractor handles existing HTML filter separately.
    target.mkdir(parents=True,exist_ok=True)
    import zipfile
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            from pathlib import PurePosixPath
            import stat
            p=PurePosixPath(info.filename.replace('\\','/'))
            if p.is_absolute() or '..' in p.parts or (info.external_attr >> 16)&0o170000==stat.S_IFLNK:
                raise PublishError('Unsafe bootstrap ZIP path')
            if info.is_dir():continue
            if info.file_size > 25*1024*1024:raise PublishError('Bootstrap asset too large')
            if p.suffix.lower() not in {'.html','.css','.js','.json','.txt','.svg','.png','.jpg','.jpeg','.webp','.woff','.woff2','.ico'}:
                continue
            dest=target.joinpath(*p.parts);dest.parent.mkdir(parents=True,exist_ok=True)
            with z.open(info) as source,dest.open('wb') as out:shutil.copyfileobj(source,out)
    if not (target/'index.html').is_file():raise PublishError('Bootstrap ZIP must contain root index.html')
    return target


def update_directory_index(root:Path):
    """Static public directory; only store names read from public per-store manifest."""
    stores=[]
    for p in sorted(root.iterdir()):
        if not p.is_dir() or not (p/'index.html').exists():continue
        f=p/'public-store.json'
        try:
            m=json.loads(f.read_text('utf-8')) if f.exists() else {'name':p.name}
            stores.append({'slug':p.name,'name':m.get('name',p.name),'category':m.get('category','品牌网站')})
        except Exception:stores.append({'slug':p.name,'name':p.name,'category':'品牌网站'})
    from html import escape
    # Preserve the approved PP master directory's design system instead of
    # replacing it with an unrelated generic template whenever a shop is added.
    current=root/'index.html'
    if current.exists():
        from bs4 import BeautifulSoup
        soup=BeautifulSoup(current.read_text('utf-8'),'html.parser')
        catalog=soup.select_one('section.catalog')
        if catalog:
            catalog.clear()
            for i,x in enumerate(stores,1):
                card=soup.new_tag('a',attrs={'class':'shop','href':f'/{x["slug"]}/','aria-label':f'进入{x["name"]}品牌网站'})
                category=escape(str(x['category']))
                name=escape(str(x['name']))
                card.append(BeautifulSoup(f'<div class="shoptop"><span>{i:03} / {category}</span><span>BRAND EXPERIENCE ↗</span></div><div><span class="eyebrow" style="color:#e9ad71">PP · BRAND STORY</span><h2>{name}</h2><p>探索品牌文化、招牌产品与门店体验。</p><div class="go"><span>进入品牌网站</span><span aria-hidden="true">↗</span></div></div>','html.parser'))
                catalog.append(card)
            if len(stores)<3:
                catalog.append(BeautifulSoup('<div class="future"><div class="plus" aria-hidden="true">+</div><h3>下一间好店，正在路上</h3><p>更多品牌将陆续在这里拥有自己的独立网页。</p></div>','html.parser'))
            count=soup.select_one('.tools span')
            if count:count.string=f'已收录门店 / {len(stores):02}'
            current.write_text('<!doctype html>\n'+str(soup),encoding='utf-8')
            return
    from html import escape
    cards=''.join(f'<a class="card" href="/{escape(x["slug"])}/"><small>{escape(x["category"])}</small><strong>{escape(x["name"])}</strong><span>进入品牌网站 ↗</span></a>' for x in stores)
    # Directory style is independent and not intended to make all merchants look alike.
    html=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PP · 餐饮品牌线上门面</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#f3f0e8;color:#222822;font-family:system-ui,'PingFang SC','Microsoft Yahei',sans-serif}}header{{border-bottom:1px solid #ccc;padding:24px 6vw;font-weight:800;letter-spacing:.16em}}main{{max-width:1100px;margin:8vh auto;padding:0 26px}}h1{{font-family:'Songti SC',serif;font-size:clamp(42px,7vw,92px);line-height:1.22;max-width:850px}}.sub{{color:#586159}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:18px;margin-top:48px}}a.card{{display:flex;flex-direction:column;gap:20px;background:#22362e;color:#fff;padding:33px;text-decoration:none;min-height:240px;transition:transform .2s}}a.card:hover{{transform:translateY(-5px)}}.card small{{color:#b5c6b0}}.card strong{{font-size:32px;font-family:'Songti SC',serif}}.card span{{margin-top:auto;color:#f4c16e}}@media(prefers-reduced-motion:reduce){{*{{transition:none!important}}}}</style></head><body><header>PP / RESTAURANTS</header><main><p class="sub">BRAND EXPERIENCES / 门店名录</p><h1>一间好店，<br>一页好故事。</h1><p class="sub">品牌文化 · 视觉创意 · 产品探索 · 门店信息</p><section class="grid">{cards}</section></main></body></html>'''
    (root/'index.html').write_text(html,encoding='utf-8')


def deploy(root:Path,project:str,base_url:str,slug:str,expected_name:str,timeout=180):
    if not os.getenv('CLOUDFLARE_API_TOKEN') or not os.getenv('CLOUDFLARE_ACCOUNT_ID'):
        raise PublishError('Cloudflare API token/account ID absent. Set environment secrets, never use Google password.')
    if not re.fullmatch(r'[a-z0-9-]+',project):raise PublishError('Invalid project name')
    if not (root/'index.html').exists():raise PublishError('Refuse empty site snapshot')
    if not (root/slug/'index.html').exists():raise PublishError('Requested merchant missing')
    # Wrangler direct-upload is supported on dashboard-created Pages projects.
    cmd=['npx','--yes','wrangler@4','pages','deploy',str(root.resolve()),'--project-name',project,'--branch','main']
    try:
        r=subprocess.run(cmd,capture_output=True,text=True,timeout=timeout,check=False,env=os.environ.copy())
    except (FileNotFoundError,subprocess.TimeoutExpired) as e:
        raise PublishError(f'Wrangler unavailable or timed out: {e}')
    if r.returncode!=0:
        raise PublishError('Wrangler deployment failed. Check CLI output locally; do not expose credentials. '+r.stderr[-500:])
    url=base_url.rstrip('/')+'/'+slug+'/'
    # 2nd independent verification; do not print URL if site does not confirm expected marker.
    import time
    for attempt in range(8):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'PP-Web-Agent-QA/1.0'})
            with urllib.request.urlopen(req,timeout=13) as response:
                body=response.read(350000).decode('utf-8','replace')
                if response.status==200 and expected_name in body and 'data-pp-brand-site' in body:
                    return url
        except (urllib.error.URLError,TimeoutError):
            pass
        time.sleep(3)
    raise PublishError('Deployment CLI succeeded but public URL content verification failed; do not declare success. Confirm site manually.')

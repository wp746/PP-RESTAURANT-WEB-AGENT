"""Preflight and real-browser tests; fail closed on errors."""
from __future__ import annotations
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse,unquote

class QualityError(RuntimeError):pass

class AuditHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.headings=[];self.photos=[];self.links=[];self.scripts=[];self.assets=[]
        self.viewport=False;self.title=False;self.forms=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='h1':self.headings.append('h1')
        if tag=='img':self.photos.append(a)
        if tag=='script':self.scripts.append(a)
        if tag=='iframe':self.forms.append('iframe')
        if tag=='form':self.forms.append('form')
        if tag=='meta' and a.get('name')=='viewport':self.viewport=True
        if tag=='title':self.title=True
        if tag=='a':self.links.append(a.get('href',''))
        if tag in ('img','script','link'):
            key='src' if tag!='link' else 'href'
            if a.get(key):self.assets.append(a[key])


def validate_site(html:str,css:str,js:str,assets_root:Path,allowed_outbound:list[str]|None=None):
    errors=[]
    lower=html.lower()
    p=AuditHTML();p.feed(html)
    if not p.viewport:errors.append('meta viewport absent')
    if not p.title:errors.append('document title absent')
    if len(p.headings)!=1:errors.append('exactly one h1 required')
    if p.forms:errors.append('iframe/form are not allowed without a real backend')
    if any(x.get('src') for x in p.scripts):errors.append('external script blocked')
    if re.search(r'(?:@import|url\s*\(\s*[\'\"]?https?://)',css,re.I):errors.append('external CSS imports blocked')
    if re.search(r'\b(?:fetch\s*\(|XMLHttpRequest|WebSocket|sendBeacon\s*\()',js):errors.append('JavaScript network request blocked')
    if re.search(r'(?i)\b(?:eval|new Function)\s*\(',js):errors.append('dynamic code execution blocked')
    if re.search(r'(?i)<\s*(?:object|embed|iframe|base)\b',html):errors.append('forbidden html element')
    if re.search(r'(?i)document\.cookie|localStorage|sessionStorage',js):errors.append('user tracking/storage blocked')
    whitelist=set(allowed_outbound or [])
    for a in p.photos:
        if not a.get('alt'):errors.append('image without alt')
        if a.get('src','').startswith(('http:','https:','data:')):errors.append('remote or inline image not allowed')
    for url in p.assets:
        if url.startswith(('http:','https:','//','data:')):
            errors.append(f'external asset: {url[:70]}');continue
        if '..' in url.split('/'):errors.append('asset escapes site directory')
        if url.endswith(('.woff','.woff2','.jpg','.jpeg','.png','.webp','.avif')) and not (assets_root/url).exists():
            errors.append('missing asset '+url)
    for url in p.links:
        if url in {'#','javascript:void(0)'}:errors.append('dead action link')
        if url.startswith(('http:','https:')) and url not in whitelist:errors.append('unverified external URL '+url[:90])
        if url.startswith(('javascript:','data:')):errors.append('unsafe link')
    # Plain anchors should point to actual IDs, not quietly lead nowhere.
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(html,'html.parser')
    ids={x.get('id') for x in soup.find_all(id=True)}
    for href in p.links:
        if href.startswith('#') and len(href)>1 and href[1:] not in ids:
            errors.append('broken anchor '+href[:60])
    if '@media' not in css:errors.append('responsive breakpoints missing')
    if 'prefers-reduced-motion' not in css:errors.append('reduced motion handling missing')
    if errors:raise QualityError('Static checks failed: '+'; '.join(sorted(set(errors))))
    return {'static':'pass','links_checked':len(p.links),'images_checked':len(p.photos)}


def audit_browser(html_path:Path,out_dir:Path,sizes:list[tuple[int,int]]|None=None):
    """Actually load the final HTML file and verify layout + JS errors + images.
    Requires pip install playwright && python -m playwright install chromium.
    """
    try:from playwright.sync_api import sync_playwright
    except ImportError as e:raise QualityError('Playwright required. Install extras [qa]') from e
    sizes=sizes or [(390,844),(1440,900),(360,780),(768,1024)]
    out_dir.mkdir(parents=True,exist_ok=True)
    results=[]
    with sync_playwright() as p:
        import os, shutil
        browser_binary=os.getenv('PP_CHROMIUM_PATH') or shutil.which('chromium') or shutil.which('google-chrome')
        opts={'headless':True,'args':['--no-sandbox']}
        if browser_binary:opts['executable_path']=browser_binary
        try:
            browser=p.chromium.launch(**opts)
        except Exception as e:
            raise QualityError('Chromium unavailable for mandatory browser QA: '+str(e)[:350]) from e
        try:
            for width,height in sizes:
                page=browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
                errors=[]
                page.on('pageerror',lambda err:errors.append(str(err)))
                # Some sandboxed browsers block file:// and localhost. For the screenshot
                # harness only, inline verified local image assets as data URLs.
                # Production output stays path-based for Cloudflare Pages.
                from bs4 import BeautifulSoup
                import base64, mimetypes
                preview=BeautifulSoup(html_path.read_text(encoding='utf-8'),'html.parser')
                for image in preview.find_all('img',src=True):
                    src=image.get('src','')
                    if src.startswith(('http:','https:','data:','/')):continue
                    f=(html_path.parent/src).resolve()
                    if f.is_file() and f.is_relative_to(html_path.parent.resolve()):
                        mime=mimetypes.guess_type(f.name)[0] or 'application/octet-stream'
                        image['src']=f'data:{mime};base64,'+base64.b64encode(f.read_bytes()).decode('ascii')
                page.set_content(str(preview),wait_until='load',timeout=25000)
                page.wait_for_timeout(300)
                metrics=page.evaluate('''() => ({scrollWidth:document.documentElement.scrollWidth,
                   clientWidth:document.documentElement.clientWidth,
                   images:[...document.images].filter(x=>!x.complete||x.naturalWidth===0).map(x=>x.src),
                   title:document.title,
                   h1:document.querySelectorAll('h1').length,
                   visibleText:document.body.innerText.trim().length})''')
                if errors:raise QualityError('Browser errors '+str(errors))
                if metrics['scrollWidth']>metrics['clientWidth']+2:raise QualityError(f'Horizontal overflow at {width}px')
                if metrics['images']:raise QualityError(f'Broken images at {width}px: {metrics["images"][:3]}')
                if metrics['visibleText']<120:raise QualityError(f'Page too empty at {width}px')
                page.screenshot(path=str(out_dir/f'{width}x{height}.png'),full_page=True,animations='disabled')
                if width==390:
                    # Verify real buttons cause a visible DOM/state/scroll change.
                    candidates=page.locator('button')
                    if candidates.count():
                        works=False
                        for j in range(min(7,candidates.count())):
                            try:
                                before=page.evaluate('''() => document.body.innerText+'|'+document.body.outerHTML.length+'|'+window.scrollY''')
                                candidates.nth(j).click(timeout=1500,force=True)
                                page.wait_for_timeout(100)
                                after=page.evaluate('''() => document.body.innerText+'|'+document.body.outerHTML.length+'|'+window.scrollY''')
                                if after!=before:works=True;break
                            except Exception:continue
                        if not works:raise QualityError('Buttons exist but no tested button caused any state change')
                results.append({'width':width,'height':height,'status':'pass','title':metrics['title']})
                page.close()
        finally:browser.close()
    return results

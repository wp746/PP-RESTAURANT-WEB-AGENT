"""OPTIONAL localhost-only ZIP upload front-end for unattended pipeline execution.
Not a public SaaS admin. Run with:
  PP_LOCAL_UI_TOKEN=<random> uvicorn ppweb.webapp:app --host 127.0.0.1 --port 8787
API must not be exposed publicly without additional production authentication and rate limits.
"""
from __future__ import annotations
import os
import secrets
import subprocess
import sys
import threading
import uuid
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, Form, Header, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse

from .publish import slug_guard

app=FastAPI(title='PP Restaurant Web Agent',docs_url=None,redoc_url=None)
_jobs={}
_lock=threading.Lock()
_run_lock=threading.Lock()  # serializes builds/deploys, avoids two simultaneous merchant updates
ROOT=Path(__file__).resolve().parents[1]
MAX_UPLOAD=350*1024*1024

PAGE='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>PP WEB STUDIO · 门店生成</title><style>
:root{--ink:#20362e;--paper:#f5f0e7;--red:#b74e36;--muted:#697a72}*{box-sizing:border-box}body{margin:0;color:var(--ink);background:var(--paper);font-family:system-ui,"PingFang SC",sans-serif}header{height:74px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #ced3c7;padding:0 6vw;font-size:13px;letter-spacing:.16em;font-weight:700}.wrap{max-width:930px;padding:10vh 24px;margin:auto}.eyebrow{letter-spacing:.18em;color:var(--red);font-size:12px}h1{font-family:"Songti SC",serif;font-size:clamp(42px,7vw,78px);line-height:1.2;margin:23px 0}.lead{line-height:1.9;color:var(--muted);max-width:680px}.panel{background:#fffefa;border:1px solid #d6d8ce;padding:35px;margin-top:45px;box-shadow:0 20px 60px #1e352612}.fields{display:grid;grid-template-columns:1fr 1fr;gap:20px}label{font-size:14px;font-weight:600;display:flex;flex-direction:column;gap:10px}input{padding:15px;border:1px solid #c5cec2;background:#f8f8f4;font:inherit;min-width:0}input[type=file]{padding:24px}button{background:var(--ink);border:none;color:#fff;padding:18px 26px;cursor:pointer;font:600 15px system-ui}button:hover{background:#395747}button:disabled{opacity:.6;cursor:not-allowed}.row{display:flex;gap:14px;flex-wrap:wrap;align-items:center;margin-top:20px}#result{margin-top:24px;white-space:pre-wrap;line-height:1.8;color:#4f6158;word-break:break-all}a{color:var(--red);font-weight:600}.notice{font-size:12px;color:#718078;margin-top:28px}@media(max-width:680px){.fields{grid-template-columns:1fr}.wrap{padding:50px 20px}.panel{padding:23px}}@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}</style></head>
<body><header><span>PP / RESTAURANT WEB STUDIO</span><span>LOCAL SECURE UPLOAD</span></header><main class="wrap"><p class="eyebrow">CULTURE FIRST · DESIGN SYSTEM</p><h1>一间好店，<br>一页好故事。</h1><p class="lead">上传门店资料 ZIP。系统按文化 → 视觉 → 交互 → 展示进行品牌分析、网页制作与手机/电脑验收；获得资料授权后可自动发布到 Cloudflare Pages。</p><section class="panel"><div class="fields"><label>门店资料压缩包 <input id="file" type="file" accept=".zip" required></label><label>专属路径（小写英文与横杠）<input id="slug" placeholder="wangjiao" required></label><label>本机上传令牌 <input id="token" type="password" autocomplete="off" placeholder="PP_LOCAL_UI_TOKEN" required></label><label>操作方式<select id="mode" style="padding:15px;border:1px solid #c5cec2;background:#f8f8f4"><option value="preview">先生成内审预览，不发布</option><option value="publish">资料已获商家授权，正式发布</option></select></label></div><div class="row"><label style="flex-direction:row;align-items:center;font-weight:400"><input id="replace" type="checkbox" style="min-width:auto"> 更新已有同名门店</label><button id="start">开始制作网页 →</button></div><div id="result" role="status" aria-live="polite">等待上传。</div></section><p class="notice">这个入口默认仅在你的电脑 127.0.0.1 上运行，不是公网后台。请勿上传老板私人证件、密码、登录 cookie 或未获授权的资源。</p></main><script>
const $=id=>document.getElementById(id);let t=null;
$('start').onclick=async()=>{
const file=$('file').files[0],slug=$('slug').value.trim(),token=$('token').value;
if(!file||!slug||!token){$('result').textContent='请填写资料、路径与本机令牌';return;}
$('start').disabled=true;$('result').textContent='素材上传中…';
const fd=new FormData();fd.append('file',file);fd.append('slug',slug);fd.append('publish',$('mode').value==='publish'?'true':'false');fd.append('replace',$('replace').checked?'true':'false');
try{const r=await fetch('/api/jobs',{method:'POST',headers:{'X-Local-Token':token},body:fd});const data=await r.json();if(!r.ok)throw Error(data.detail||'上传失败');$('result').textContent='制作中：资料盘点 → 设计 → 浏览器验收 → 发布验证…';
t=setInterval(async()=>{const s=await fetch('/api/jobs/'+data.job_id,{headers:{'X-Local-Token':token}});const x=await s.json();if(x.status==='done'){clearInterval(t);$('result').innerHTML=x.result.startsWith('https://')?'<a target="_blank" rel="noreferrer" href="'+x.result+'">'+x.result+'</a>':x.result;$('start').disabled=false;}else if(x.status==='error'){clearInterval(t);$('result').textContent='未发布：'+x.error;$('start').disabled=false;}},1600);
}catch(e){$('result').textContent=e.message;$('start').disabled=false;}};
</script></body></html>'''


def authenticate(request:Request,token:str|None):
    expected=os.getenv('PP_LOCAL_UI_TOKEN')
    if not expected or len(expected)<12:
        raise HTTPException(503,'Local UI disabled: PP_LOCAL_UI_TOKEN (12+ chars) not configured')
    origin=request.headers.get('origin','')
    if origin and urlparse(origin).hostname not in {'localhost','127.0.0.1'}:
        raise HTTPException(403,'Non-local origin blocked')
    if not token or not secrets.compare_digest(expected,token):
        raise HTTPException(401,'Invalid local admin token')


@app.get('/',response_class=HTMLResponse)
def index():return PAGE


def work(job_id:str,zip_path:Path,slug:str,publish:bool,replace:bool):
    cmd=[sys.executable,'-m','ppweb','run',str(zip_path),'--slug',slug,'--sites-dir',str(ROOT/'sites'),
         '--workdir',str(ROOT/'.ppweb-work'/'jobs'), '--replace-workdir']
    if replace:cmd.append('--replace')
    if publish:cmd.extend(['--publish','--confirm-publish'])
    try:
        with _run_lock:
            cp=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=1500)
        with _lock:
            if cp.returncode==0:_jobs[job_id]={'status':'done','result':cp.stdout.strip().splitlines()[-1]}
            else:_jobs[job_id]={'status':'error','error':cp.stderr.strip()[-1100:] or '任务失败，请查看终端日志'}
    except subprocess.TimeoutExpired:
        with _lock:_jobs[job_id]={'status':'error','error':'任务超时；没有确认成功发布'}
    finally:
        try:zip_path.unlink(missing_ok=True)
        except Exception:pass


@app.post('/api/jobs')
async def submit(request:Request,file:UploadFile=File(...),slug:str=Form(...),publish:bool=Form(False),replace:bool=Form(False),x_local_token:str|None=Header(None)):
    authenticate(request,x_local_token)
    try:slug_guard(slug)
    except Exception:raise HTTPException(400,'门店路径格式错误')
    if not file.filename or not file.filename.lower().endswith('.zip'):
        raise HTTPException(400,'请上传ZIP文件')
    upload_dir=ROOT/'.ppweb-work'/'uploads';upload_dir.mkdir(parents=True,exist_ok=True)
    job_id=uuid.uuid4().hex
    dest=upload_dir/f'{job_id}.zip'
    size=0
    with dest.open('wb') as output:
        while chunk:=await file.read(1024*1024):
            size+=len(chunk)
            if size>MAX_UPLOAD:
                dest.unlink(missing_ok=True)
                raise HTTPException(413,'ZIP过大')
            output.write(chunk)
    with _lock:_jobs[job_id]={'status':'running'}
    threading.Thread(target=work,args=(job_id,dest,slug,publish,replace),daemon=True).start()
    return {'job_id':job_id,'status':'running'}


@app.get('/api/jobs/{job_id}')
def status(request:Request,job_id:str,x_local_token:str|None=Header(None)):
    authenticate(request,x_local_token)
    with _lock:r=_jobs.get(job_id)
    if not r:raise HTTPException(404,'Unknown job')
    return r

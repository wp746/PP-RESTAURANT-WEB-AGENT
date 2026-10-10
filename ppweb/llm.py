"""Vendor-neutral OpenAI-compatible Chat Completions adapter.
Use a text/multimodal capable model; image generation-only model IDs do NOT work here.
"""
from __future__ import annotations
import base64
import io
import json
import os
import re
from pathlib import Path
from typing import Any

import requests
from PIL import Image

class ModelError(RuntimeError): pass


def clean_json(s:str)->Any:
    s=s.strip()
    if s.startswith('```'):
        s=re.sub(r'^```(?:json)?\s*','',s)
        s=re.sub(r'\s*```$','',s)
    try:return json.loads(s)
    except json.JSONDecodeError:
        start=s.find('{');end=s.rfind('}')
        if start<0 or end<=start:raise ModelError('Model response is not a JSON object')
        try:return json.loads(s[start:end+1])
        except json.JSONDecodeError as e:raise ModelError(f'Invalid model JSON: {e}') from e

class Model:
    def __init__(self,base_url:str|None=None,model:str|None=None,key:str|None=None):
        self.base_url=(base_url or os.getenv('PP_MODEL_BASE_URL','')).rstrip('/')
        self.model=model or os.getenv('PP_MODEL_NAME','')
        self.key=key or os.getenv('PP_MODEL_API_KEY','')
        if not all([self.base_url,self.model,self.key]):
            raise ModelError('Missing PP_MODEL_BASE_URL, PP_MODEL_NAME or PP_MODEL_API_KEY. Cannot create a production-quality design without an AI model.')
        if not self.base_url.startswith('https://'):
            raise ModelError('Model endpoint must use HTTPS')

    def ask(self,system:str,user:str,images:list[Path]|None=None,max_tokens=12000):
        content=[{'type':'text','text':user}]
        for image_path in (images or [])[:8]:
            try:
                with Image.open(image_path) as im:
                    im.thumbnail((850,850),Image.Resampling.LANCZOS)
                    im=im.convert('RGB')
                    b=io.BytesIO();im.save(b,format='JPEG',quality=73)
                    content.append({'type':'image_url','image_url':{'url':'data:image/jpeg;base64,'+base64.b64encode(b.getvalue()).decode('ascii')}})
            except Exception:continue
        payload={
           'model':self.model,'temperature':0.62,'max_tokens':max_tokens,
           'messages':[{'role':'system','content':system},{'role':'user','content':content if images else user}],
        }
        r=requests.post(self.base_url+'/chat/completions',headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'},json=payload,timeout=240)
        if not r.ok:raise ModelError(f'Text model API HTTP {r.status_code}: {r.text[:250]}')
        data=r.json()
        reply=data.get('choices',[{}])[0].get('message',{}).get('content')
        if isinstance(reply,list):reply=''.join(x.get('text','') for x in reply if isinstance(x,dict))
        if not reply:raise ModelError('Model returned no content')
        return clean_json(reply)

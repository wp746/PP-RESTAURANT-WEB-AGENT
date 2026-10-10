"""LLM factual/editorial review — second pass distinct from creator."""
from __future__ import annotations
import json
from bs4 import BeautifulSoup
from .llm import ModelError
from .quality import QualityError


def factual_review(model,facts:dict,evidence:dict,docs:list[dict],html:str):
    soup=BeautifulSoup(html,'html.parser')
    for s in soup(['style','script']):s.decompose()
    public_text=soup.get_text(' ',strip=True)[:24000]
    source_text='\n'.join(f'{x["source"]}: {x["content"][:4200]}' for x in docs[:15])[:24000]
    prompt=f'''逐句核查网页即将公开的具体经营事实，不审查原创修辞或虚构情节（它们如果被说成真实历史，判定违规）。你是独立的事实审计员，不负责重写文案。
商家字段：{json.dumps(facts,ensure_ascii=False)[:10000]}
来源记录：{json.dumps(evidence,ensure_ascii=False)[:3500]}
原始资料片段：{source_text}
网页实际可见文字：{public_text}
只输出 JSON：{{"passed":true/false,"unsupported_claims":[...],"notes":[...]}}。
重点：未提供的具体年份、创始人、门店获奖、声称祖传秘方、品牌历史、产品真实售价、详细地址、联系电话、营业时间、优惠承诺、已订位成功/已领券，都不得作为事实出现。
普通修辞不等于具体事实。明写“概念设计”“示意”“待确认”的不判为已证实的经营事实，但如果对外发布则仍需可用性判断。
'''
    result=model.ask('你是审慎的事实核查员，只能从资料支持网页上的商业事实。严格输出JSON。',prompt,max_tokens=1700)
    if not isinstance(result,dict) or not isinstance(result.get('passed'),bool):
        raise QualityError('Fact review produced invalid result')
    if not result['passed'] or result.get('unsupported_claims'):
        raise QualityError('Unverified public business claims: '+json.dumps(result.get('unsupported_claims',result.get('notes')),ensure_ascii=False)[:950])
    return result


def visual_review(model,plan:dict,screenshots:list,merchant_name:str):
    from pathlib import Path
    paths=[Path(p) for p in screenshots if Path(p).exists()]
    if not paths:raise QualityError('No screenshots for design acceptance review')
    prompt=f'''作为独立网页艺术总监，审查以下同一网站的移动端和桌面端浏览器截图。
品牌：{merchant_name}
设计命题：{json.dumps({k:plan.get(k) for k in ('culture_thesis','tone','hero','palette','typography','sections')},ensure_ascii=False)[:8000]}
要求：一店一气质、文化第一、视觉第二、交互第三、展示第四；高级排版和真实产品视觉；避免标题裁切、商品消失、大片空白、信息遮挡、字体破碎、视觉风格与门店不一致；不要仅以华丽程度评分。
返回严格 JSON：{{"approved":true/false,"issues":[具体问题],"strengths":[亮点],"mobile_readable":true/false,"desktop_readable":true/false}}。
对于可能是截图缩放造成的小字问题，不要误报；只列出明确且实际可修复的问题。'''
    res=model.ask('你是严格且有审美的界面验收专家。只允许输出有效JSON。',prompt,images=paths,max_tokens=1900)
    if not isinstance(res,dict) or not isinstance(res.get('approved'),bool):
        raise QualityError('Visual model review did not produce valid approval JSON')
    if not res['approved'] or not res.get('mobile_readable',False) or not res.get('desktop_readable',False):
        raise QualityError('Visual QA failed: '+json.dumps(res.get('issues',[]),ensure_ascii=False)[:1200])
    return res

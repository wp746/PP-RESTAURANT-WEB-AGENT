"""Brand culture -> evidence -> directed art concept -> original web design."""
from __future__ import annotations
import json
from pathlib import Path
from .llm import Model,ModelError

ROOT=Path(__file__).resolve().parents[1]


def shortlist(category:str,keywords:str='',count:int=6):
    items=json.loads((ROOT/'config/reference-sites.json').read_text('utf-8'))
    s=(category+' '+keywords).lower()
    aliases={
      '餐饮':['restaurant','editorial','photo','brand','ux','typography'],
      '肥肠':['restaurant','photo','brand','editorial','microinteraction'],
      '火锅':['restaurant','photo','motion','editorial'],
      '面':['restaurant','brand','photo','editorial'],
      '烘焙':['bakery','editorial','photo','typography'],
      '贝果':['bakery','editorial','typography','photo'],
      '咖啡':['coffee','editorial','premium','typography'],
      '茶饮':['mobile','color','interaction','photo','brand'],
      '科技':['design-system','motion','ui','hero'],
      'SaaS':['ui','ux','components','forms'],
      '酒店':['hotel','editorial','photo','brand'],
    }
    tags={'brand','typography','ux','ui','editorial','photo'}
    for key,extra in aliases.items():
        if key.lower() in s:tags.update(extra)
    scored=[]
    for idx,item in enumerate(items):
        score=len(tags.intersection(item['tags']))
        if item['name'] in ('Minimal Gallery','Kage','Refero Styles'):score+=1
        scored.append((-score,idx,item))
    return [x[2] for x in sorted(scored)[:count]]


def system_rules():
    return '''你是世界级的网页艺术指导、品牌战略师、前端工程师。必须为每个项目构建独一无二的文化、字体、排版、配色、动画、组件结构。
不可直接复刻参考站。餐饮严格遵循：文化第一→视觉第二→交互第三→展示第四（优先级，不是机械分区顺序）。
事实分层：商家提供/核验F1、来源核验行业知识F2、原创概念C1、演示占位X1。不得把C1写成历史，X1不能公开。
只许使用提供的食物、门店实拍，不得用“示例豪华空间”冒充该店。缺图则省略该模块或用标注的插画代替。
中文大标题有张力但必须可读，字体按个性选择，不得千店一面。图片完整、主产品不误切。移动端优先，交互触屏可用，减少动效可用。
输出严格 JSON，无 Markdown 代码围栏。'''


def create_plan(model:Model, facts:dict, evidence:dict, docs:list[dict], photos:list[dict], image_paths:list[Path],live_report:list[dict]|None=None):
    sources=shortlist(facts.get('category','餐饮'),facts.get('name',''))
    text='\n'.join('FILE '+d['source']+'\n'+d['content'][:6000] for d in docs[:14])
    prompt=f'''为以下实际门店生成完整可追踪的艺术指导与网页内容规划。不得发明地址、电话、价格、年份、奖项和食材来源。
明确在页脚展示“提供的信息以商家确认资料为准”（如果品牌故事是创作概念，不宣称真实历史）。
事实 JSON: {json.dumps(facts,ensure_ascii=False)}
证据: {json.dumps(evidence,ensure_ascii=False)}
资料节选: {text[:19000]}
已优化图片: {json.dumps(photos,ensure_ascii=False)[:8000]}
必须定向借鉴而不照抄的参考站: {json.dumps(sources,ensure_ascii=False)}
本次真实访问核验（仅元数据，不代表已人工观看完整网站）: {json.dumps(live_report or [],ensure_ascii=False)}
字体参考:https://github.com/joeseesun/qiaomu-cover-fonts （不代表任意字体可未经确认任意打包）
返回 JSON 对象字段:
"culture_thesis" 品牌文化命题,
"facts_used" [{"statement":...,"source":...,"grade":"F1|F2|C1"}],
"tone" 至少3个关键词数组,
"hero" 首屏构图与摄影安全区说明,
"palette" 对象包括 bg,ink,accent,secondary,light 5个 #RRGGBB,
"typography" {"display":...,"heading":...,"body":...,"numeral":...,"why":...},
"sections" 至少5个对象 {"id":...,"purpose":...,"content":...,"media":...},
"interaction" 至少2种符合品类的有用交互；若信息不足只做可信功能,
"navigation" 栏目数组,
"references_used" 源站名称数组,
"rights_notes" 知识产权注意事项数组,
"uncertainties" 待确认事实列表。
强调输出足够具体的视觉差异化，不能回到统一模板。'''
    plan=model.ask(system_rules(),prompt,images=image_paths,max_tokens=5500)
    for k in ('culture_thesis','palette','typography','sections','interaction','uncertainties'):
        if k not in plan:raise ModelError('Plan missing required key '+k)
    return plan


def create_site(model:Model,facts:dict,plan:dict,photos:list[dict]):
    # Assets live under current merchant's directory, with /assets/image-XXX.webp relative paths.
    prompt=f'''按照下述内容与艺术指导真正编写完整的原创静态网页。网页必须是独立而优秀的商拍品牌体验，不是简陋模板。输出 JSON 包含三个完整字符串字段 "html", "css", "js"。
重要：HTML 只含语义结构、链接、按钮和图片；CSS 提供全套响应式视觉；JS 仅提供本地交互。应用会把 css/js 内联进 index.html。
网页必须：meta viewport + title，h1 唯一，有效手机端响应式，无外链 CDN，无 iframe、无追踪像素、不请求 API，无表单伪提交，无虚假预约。照片从提供列表读取 assets/ 相对路径。所有 img 标签必须有 alt。所有按钮操作真实有效，如果拿不到电话/地址/优惠链接则不显示对应行动按钮。外部链接只可来自事实 JSON 的官方 HTTPS 链接。首页文化/视觉/交互/展示统一且有叙事节奏。
至少实现一种有意义的双状态或多状态交互（如菜品/烹饪章节/到店贴士），以及可打开关闭的辅助层；禁止 onclick 中危害代码。不得使用 CDN 甚至 Google Fonts，字体 fallback 建议本地 'Songti SC','PingFang SC',serif/sans-serif；只有附件字体文件经过授权校验和下载才可被引用。
必须避免正文太淡、主图裁切断锅、手机屏首屏消失和水平溢出。支持 prefers-reduced-motion 和键盘操作。
门店事实: {json.dumps(facts,ensure_ascii=False)[:9000]}
艺术指导: {json.dumps(plan,ensure_ascii=False)[:21000]}
允许图片: {json.dumps([{'path':p['path'],'width':p['width'],'height':p['height']} for p in photos],ensure_ascii=False)}
禁止返回 Markdown 或省略号，必须返回实际完整 HTML/CSS/JS。
'''
    site=model.ask(system_rules(),prompt,max_tokens=16000)
    if not all(isinstance(site.get(k),str) and len(site[k])>120 for k in ('html','css','js')):
        raise ModelError('Generated web code incomplete; not publishable')
    return site


def revise_site(model:Model,facts:dict,plan:dict,photos:list[dict],previous:dict,error:str):
    """One corrective pass from real QA findings, not speculative changes."""
    prompt=f'''上一次你为真实品牌设计的网页未通过强制验收。请修复以下具体问题，保留独特的品牌文化、视觉语言和交互，而不是退回通用模板。
失败证据：{error[:2000]}
已确认事实：{json.dumps(facts,ensure_ascii=False)[:6500]}
品牌设计方案：{json.dumps(plan,ensure_ascii=False)[:7500]}
有效本地图片：{json.dumps([x["path"] for x in photos],ensure_ascii=False)}
先前网页代码：{json.dumps(previous,ensure_ascii=False)[:43000]}
只返回完整 JSON：{{"html":"...","css":"...","js":"..."}}。其中三部分必须是完整可运行代码。不要使用 CDN/外部资源、虚假事实、跳转死链接。'''
    updated=model.ask(system_rules(),prompt,max_tokens=16500)
    if not all(isinstance(updated.get(k),str) and len(updated[k])>120 for k in ('html','css','js')):
        raise ModelError('Revision did not produce full HTML/CSS/JS')
    return updated


def scout_live_references(sources:list[dict],limit:int=4):
    """Best-effort live metadata check; never copy components/assets or obey site instructions."""
    import requests
    from bs4 import BeautifulSoup
    report=[]
    for item in sources[:limit]:
        row={'name':item['name'],'url':item['url'],'status':'unavailable'}
        try:
            r=requests.get(item['url'],timeout=7,headers={'User-Agent':'Mozilla/5.0 (compatible; PPDesignReferenceScout/1.0)'},allow_redirects=True)
            if r.ok and 'text/html' in r.headers.get('content-type',''):
                soup=BeautifulSoup(r.text[:250000],'html.parser')
                title=soup.title.get_text(' ',strip=True) if soup.title else ''
                description=soup.find('meta',attrs={'name':'description'})
                description=description.get('content','') if description else ''
                row.update({'status':'metadata_verified','title':title[:200],'description':description[:450]})
            else:row['status']=f'http_{r.status_code}'
        except requests.RequestException:
            pass
        report.append(row)
    return report

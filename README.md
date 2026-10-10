# PP Restaurant Web Agent · PP 餐饮品牌线上门面智能体

> **版本：v0.1.0（可执行工程 / 待接入授权凭据的首版）**  
> 从门店真实素材 ZIP → 文化/品牌 DNA → 定向检索 25 站创意库 → 个性化网页代码 → 手机/电脑真实验收 → 多门店安全合并 → Cloudflare Pages 自动发布 → 最后只返回网址。

**重要说明**：仓库包含真实可运行的 CLI、设计提示词、资料解析、图片处理、审计与自动部署代码，**但它不是无配置的云端托管服务**。需要运行它的智能体具备 Python、联网访问文本/视觉模型、浏览器测试和 Cloudflare 发布权限。未连接这些能力时不会声称已经上线。

## 0. 你想要的结果

最终用户只需要提供完整门店素材包，在预先完成配置的可信执行环境运行：

```bash
ppweb run "门店素材.zip" --slug wangjiao --sites-dir sites --publish --confirm-publish --git-sync
```

**发布成功的标准输出只有一行，例如：**

```text
https://pp-restaurants.pages.dev/wangjiao/
```

非成功时不会生成假网址；错误/阻断原因输出到 stderr。商家真实信息、图片版权和最终公开使用授权必须在素材包中确认。

## 1. 一次性的安装与授权（无需 Google 密码）

1. `git clone <本仓库 GitHub 地址> && cd PP-RESTAURANT-WEB-AGENT`
2. 安装 Python 3.10+、Node.js 20+：
   `python -m pip install -e '.[qa,files]'`
3. 安装浏览器测试引擎：`python -m playwright install chromium`
4. 配置支持 OpenAI Chat Completions 接口的**文本与视觉模型**：
   - `PP_MODEL_BASE_URL`：例如 `https://供应商的兼容接口/v1`（实际以供应商文档为准）
   - `PP_MODEL_NAME`：支持文本 JSON、最好也支持读照片的模型
   - `PP_MODEL_API_KEY`：模型 API 令牌，放系统机密/环境变量，不能提交 GitHub
   - 云雾的 `gpt-image-2` 是图像生成模型，**不能直接当作网页代码生成文本模型**；如果选择云雾，也必须确认其文本/多模态模型及协议确实受支持。
5. Cloudflare 现有项目是 **`pp-restaurants`**；它仍是你用网页界面创建的 Pages Direct Upload 项目，无需重建。给它授权只用一个**限定 Pages 写入权限的 API Token** 和 Account ID：
   - `CLOUDFLARE_ACCOUNT_ID`
   - `CLOUDFLARE_API_TOKEN`
   - `CLOUDFLARE_PROJECT_NAME=pp-restaurants`
   - `PP_SITE_BASE_URL=https://pp-restaurants.pages.dev`
6. 把上述值安全设置在操作系统环境变量、受控智能体的 Secret 存储，或 GitHub Actions Secrets。**不要通过聊天发送 API Token，不要保存你的 Gmail 密码/浏览器 cookie/2FA 验证码。**

Cloudflare 官方 Direct Upload CI 文档：https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/  
Wrangler：https://developers.cloudflare.com/workers/wrangler/commands/pages/  

## 2. 先导入你现有的网站（最重要的防误删步骤）

因为 `pp-restaurants` 现在是**一个项目、多个门店目录**，Cloudflare 的 Pages 每次部署都是**整个目录快照**，并不是给某个目录“追加文件”。如果只部署最新一家店，会把其他已经上线的目录从生产版本中移除。

本仓库附带可选的 `sites/` 已知基线。如果使用新克隆的干净仓库、没有 `sites/index.html`，必须先把**目前真实线上版本的完整网站 ZIP** 下载或导出，然后运行：

```bash
ppweb bootstrap 当前已上线的完整网站包.zip --sites-dir sites
```

如果还没有生产包的可信副本，**停止自动发布**，不要用空目录、演示 ZIP 或只有新店页面的 ZIP 冒险覆盖线上 `pp-restaurants`。

在不同机器/智能体之间协作，**`sites/` 必须作为唯一的版本化发布状态**（推荐放在受权限控制的 GitHub 仓库中，只有已批准公开的站点资源可以提交）。不要把商家上传的原始 ZIP、保密资料、证件或密钥提交进去。

> 若你从下载的本仓库 ZIP 运行，仓库中已经包含一份根据此前 V2 实际线上上传包还原的参考 `sites/`。它只是历史基线，**不保证与当前线上完全同步**。首次自动发布前请以 Cloudflare 当前生产部署的实际内容为准，防止覆盖后续其他人做的更新。

## 3. 素材输入格式

老板/采集人员制作一个 ZIP，内含 `merchant.yaml` 或 `merchant.json`，以及 `txt/md/docx/pdf/xlsx/csv`、`jpg/png/webp` 等。

参照 [`docs/门店素材包约定.md`](docs/门店素材包约定.md) 和 [`knowledge/门店采集与生成SOP.md`](knowledge/门店采集与生成SOP.md)。

示例 `merchant.yaml`：

```yaml
name: 旺角肥肠鸡
category: 川渝肥肠鸡
address: 商家确认的门店详细地址
phone: 商家确认的联系电话
opening_hours: 商家确认的营业时间
story: 商家确认的真实开店故事（可以留空）
menu:
  - name: 招牌肥肠鸡
    price: 由商家填写的真实数字
    description: 商家确认的菜品说明
map_url: https://商家已验证的地图链接
approved_for_publication: false
media_rights_confirmed: false
```

正式上线前**由商家确认**两个布尔值为 `true`（网页文案/资料和影像使用权）。初次演示可保持 `false`，使用本地预览而不发布。

## 4. 完整自动化 SOP

```text
门店ZIP
  ├── P0 压缩包安全检测（目录穿越、symlink、解压炸弹、数量大小限制）
  ├── P1 资料识别：文本/表格/图片，不运行任何上传代码
  ├── P2 事实台账（每个事实对应输入文件，缺失内容不能编造）
  ├── P3 品牌 DNA：文化与品类属性、客群、价位、地域、影像与真实店况
  ├── P4 从25个站定向取“设计方法”，从字体库选风格/角色；不照抄
  ├── P5 AI 艺术指导：文化母题、色彩、字体、摄影构图、交互逻辑
  ├── P6 AI 生成门店定制 HTML、CSS、JavaScript + 优化后的实拍照片
  ├── P7 审计：禁用虚假信息、未授权外链、远程脚本、演示功能冒充生产功能
  ├── P8 Chromium 真渲染：360 / 390 / 768 / 1440px + 点击/响应式检查
  ├── P9 从版本库完整旧站复制到临时目录 → 合并新门店 → 构建网站总目录
  ├── P10 凭 Cloudflare Pages API Token 使用 Wrangler 部署整个快照
  └── P11 验证公网 URL 的实际内容 → 更新本地完整站状态 → stdout URL
```

- **文化第一**：历史/企业文化不凭空编造；可创作概念品牌命题，必须是 C1 不是 F1。
- **视觉第二**：一店一气质；图片完整优先、字体按品牌调性，支持原创标题字 PNG/WebP，但需有生成该资产的实际工具。
- **交互第三**：根据品类做有意义的选项切换和吃法建议，不能“按钮只好看不干活”。
- **展示第四**：菜单、价格、门头、地址、电话、营业时间必然清晰可找；展示第四是设计优先级，不是埋到页面最末才可发现。

### 来源与授权

`knowledge/` 完整收录：设计总纲、采集 SOP、25 站参考检索方法、开源字体搭配与授权/部署清单。设计 Agent 必须先读取这些，选择与品类相关的来源；**不能断言实时访问了未访问的网站**。本版本按本地已核实的索引检索，未实现对全部站点的逐页自动爬取或自动购买素材。

字体仓库：https://github.com/joeseesun/qiaomu-cover-fonts  
没有随仓库分发第三方字体文件；如果要自托管字体，必须下载具体字形、校验 OFL/保留字体名，检查中文缺字后存入 `assets/`，不能只引用境外 CDN。

## 5. 运行方式

### A｜没有模型密钥，先做离线完整管线冒烟测试

```bash
ppweb run examples/demo-site.zip --slug smoke-store --demo --replace-workdir
```

返回本地 HTML 路径，含醒目的「非正式交付」提示，绝对不会发布。此模式只证明 ZIP、图片处理、页面、测试流程能跑，**不代表 AI 设计成品**。

### B｜真实资料，生成网页并预览，不部署

```bash
ppweb run /path/to/真实门店.zip --slug brand-slug --replace-workdir
```

输出：`.ppweb-work/brand-slug/output/merchant/index.html`、`brand-plan.json`、`intake-report.json`、`quality-report.json`、电脑手机截图。

### C｜允许公开发布的资料，一条命令自动上传

```bash
ppweb run /path/to/已批准素材.zip --slug brand-slug --sites-dir sites --publish --confirm-publish --replace-workdir
```

更新原店（不创建重名目录）：额外加 `--replace`。

用户在对话或输入资料中明确授权发布，并且 `merchant.yaml` 确认事实与版权后，可信 Agent 才可使用 `--confirm-publish`。**不能靠模型自作主张改审批字段**。`--skip-browser` 或 `--demo` 均强制禁止发布。

### D｜删除/下线一家店

```bash
ppweb remove wangjiao --sites-dir sites --confirm wangjiao --publish --confirm-publish
```

删除是明确的用户动作，不能从“未出现在目录”推断应该删除。生产删除后历史部署仍可能保留旧副本，涉及真正删除历史数据需要另行清理。

## 6. GitHub 多智能体调用

任何具备 Git clone、Shell、Python 和安全密钥的智能体可读取：

- `README.md`：安装/运行/授权/产品说明
- `READMEC.md`：兼容用户要求的文件名，指向 README
- `AGENTS.md`：跨智能体行为与防错约束
- `SKILL.md`：Skill 风格触发与执行契约
- `knowledge/*`：设计总纲、采集 SOP、参考库、字体库
- `ppweb/*`：可运行 CLI/模型 adapter/浏览器 QA/Cloudflare Wrangler 发布

**重点**：`git clone` 只下载代码，不会让任意 AI 凭空获得你的 Cloudflare 登录权限。每个执行环境必须单独安全连接（或运行在你已配置 Secrets 的可信执行器里）。

只需要返回网址不等于没有实际审批和错误。系统仍在 stderr 和构建日志记录验证，只有成功发布且验证后 stdout 才返回网址。

## 7. GitHub Actions 自动发布（可选）

仓库附带 `.github/workflows/ci.yml` 和 `.github/workflows/deploy-pages.yml`，可在受控仓库通过手动 `workflow_dispatch` 发布 `sites/` 目录。它适合已经由可信 Agent 生成、测试、检查并保存进 `sites/` 的静态成品；**并不通过 GitHub Actions 从零设计网页**。

将 `CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID` 存成 GitHub Repository Secrets，并在 Actions 中输入 `DEPLOY` 确认后部署。避免将包含门店隐私原始资料的 ZIP 推送到公共仓库。

## 8. 已知限制 / v0.1.0 诚实披露

1. **这是可执行脚手架，不是经大量门店生产验证的成熟 SaaS。** 大模型生成的原创网页具有随机性，严格验证会让不合格结果停止发布；后续可加自动修复重试。
2. 生产模式需要用户自己接入文本/视觉模型；视觉模型的真实表现要按模型能力评估。`gpt-image-2` 不能替代文本/视觉理解模型。
3. 本版不会自动登录你的 Google 邮箱，因为云端登录需要 OAuth/2FA、人为交互，自动化部署的正确通道是 Cloudflare Pages Write 权限 API Token。
4. 当前版本不会自动上网抓取全部 25 个站点，也不自动复制网页代码和照片。站点资料与许可实时变化。
5. HTML/CSS/JS 生成与浏览器 QA 可以本地/云端执行；是否能连接第三方平台由运行环境的工具权限决定。
6. Pages 中多个门店需要完整版本化 `sites/`；所有并发发布应串行，其他执行器在发布前必须同步最新快照，否则可能覆盖同事刚改的内容。此版不含分布式锁或正式多租户管理后台。
7. 当前提供网页文件与部署过程，不负责核对商家的财务、营业执照、商标权属，也不自动制造缺失的真实门店照片。
8. 发布到公网时真实商家电话和地址属于公开内容；素材包中的私人原始材料不能存公开仓库。

## 9. 目录结构

```text
PP-RESTAURANT-WEB-AGENT/
├── README.md / READMEC.md / AGENTS.md / SKILL.md
├── knowledge/           # 文化视觉 SOP + 25 站 + 字体与授权规则
├── config/              # 项目策略 + 25站机器索引
├── ppweb/               # ZIP → 规划 → 网页 → QA → 安全部署
├── sites/               # 全站可发布静态快照，必须以线上最新状态为准
├── examples/            # 演示资料与离线冒烟测试
├── tests/               # 防损坏/安全/渲染单测
├── docs/                # 真实门店采集规范、授权操作、发布手册
└── .github/workflows/   # CI + 可选手动部署
```

## 10. 给任意支持工具调用的智能体的启动指令

> 请先完整阅读该仓库的 `AGENTS.md`、`SKILL.md`、`README.md` 与 `knowledge/`，然后以 `ppweb` CLI 执行商家素材 ZIP → 文化优先的品牌网站 → 浏览器 QA → 完整多店快照部署。项目名称 `pp-restaurants`。不要套模板、捏造事实、覆盖其他门店或获取谷歌登录密码；模型密钥及 Cloudflare API Token 必须从可信 Secrets 读取。成功时只回复经过上线验证的商家网址，遇到缺资料、授权或测试失败必须明确报错。

## 11. 测试与许可

`python -m pytest -q`；`python -m compileall -q ppweb`；`ppweb run examples/demo-site.zip --slug smoke-store --demo --replace-workdir`。

本仓库原创源码采用 MIT License；**外部参考站、字体与商家图片不因为本项目使用 MIT 就获得同样的许可**。商家自带图片、Logo 和菜单的权利由具体商家确认。

## 12. 文字与视觉复核的发布闸门

正式模式默认使用两级 AI 验收：
- 网页可见文案的商业事实检查（独立于创作模型角色），检出未经源数据支持的创立年份、菜单价格、获奖及优惠等；
- 使用 Chromium 的 390px/1440px 截图进行视觉评审，检查文化一致性、字体、裁切和 UI。

有明确错误则自动最多重新生成 2 次，再失败则停止。`--no-visual-review` 仅供调试，**禁止正式发布**。视觉审核对模型图片理解能力有要求，不能把主观评价当成百分之百保证。

为了跨智能体维护多个门店，正式部署建议增加 `--git-sync`：发布确认成功后仅提交 `sites/` 已批准的公开网页文件到你的 GitHub 仓库。同步失败会明确报错，不会谎称整个流水线完成。

首次创建独立仓库的说明：[`docs/GitHub新建仓库和推送.md`](docs/GitHub新建仓库和推送.md)。

## 13. 可选本地网页上传入口（不需要额外付费服务器）

除了 ChatGPT/Codex 等 Agent 直接调用 CLI，本仓库还附带一个**可选的本地 ZIP 上传面板**。

```bash
python -m pip install -e '.[qa,files,web]'
export PP_LOCAL_UI_TOKEN='在你本机设置至少12位随机字符串'
uvicorn ppweb.webapp:app --host 127.0.0.1 --port 8787
```

打开 `http://127.0.0.1:8787/`，就可以在本机拖入 ZIP、填写门店英文路径、选择预览或正式发布、查看结果链接。它不是公网后台，浏览器端不能把令牌写死进仓库。需要你电脑（或可信运行器）保持开机运行期间才能处理任务；不影响最后的 Cloudflare 静态网站免费托管。

上传接口仅监听本机，令牌验证、文件大小限制、临时 ZIP 清理已实现；如果未来要开放公网，则必须重新设计账户权限、HTTPS、限流、任务队列与持久化，不要直接将 localhost 面板绑定到 `0.0.0.0`。

## 14. 实时参考网站的边界

真实生成模式会根据品牌/品类先匹配 25 站参考索引，并尝试访问前 4 个匹配站点的**公开标题与描述元数据**，保存 `reference-report.json`。动态站点可能因 JS、网络或反爬限制无法读取，届时标记不可用，不会声称已研究其每个组件。可以传入 `--offline-references` 仅使用知识库索引。借鉴设计方法不等于复制品牌源图或付费组件，也不等于这 25 站自动提供完整商用授权。

真实餐饮文化与品牌历史优先来自商家的 `merchant.yaml`、老板文字及能核验的原始资料；缺少来源的地域/历史陈述不允许生成为确定的企业事实。任何需要外部事实研究的门店，都应先由有联网检索能力的执行 Agent 收集来源供事实审核。
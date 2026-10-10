# AGENTS.md — Universal runner contract

Before making changes, read `README.md`, `SKILL.md`, `knowledge/品牌网站设计总纲.md`, `knowledge/门店采集与生成SOP.md`, `knowledge/25站设计参考索引.md`, `knowledge/设计参考调用SOP.md`, `knowledge/开源字体选择规则.md`.

User intent: one ZIP of genuine merchant data -> one category-specific, culture-first, high-design, interactive static site, fully QA'd -> preserve every other merchant in the shared `pp-restaurants` Pages project -> only final URL on successful run.

Contract:
1. Reconstruct evidence and keep fact grades F1/F2/C1/X1 separate. Never hallucinate history or menu data.
2. Art direction is original and specific. Culture > visual > meaningful interaction > complete information. Avoid generic repeated templates.
3. Choose from 25 design reference sites as needed; references are for methods, not unlicensed copying.
4. Choose fonts per category. Check glyph coverage, license and file size. No critical third-party CDN dependency.
5. Never handle Google passwords, cookies, 2FA, or open Cloudflare login with unattended browser. `CLOUDFLARE_API_TOKEN` + account ID in environment / secrets only. Never embed credentials in public site.
6. Multi-tenant safety: production Pages upload REPLACES the whole deployed snapshot. Bootstrap existing site first, then stage complete snapshot. Missing current site -> STOP.
7. Browser QA is mandatory for production. No live deploy from `--demo`, `--skip-browser`, or without merchant approval and media rights. Stop on verification failure.
8. Never disclose merchant private source ZIP in public repository. Commit only approved public site artifacts. Avoid uploading private business docs to repo.
9. On success, final response MUST be only the verified URL. On failure, state precise blocker and do not invent URLs.

Supported command after setup:
`ppweb run /path/to/merchant.zip --slug merchant-slug --sites-dir sites --publish --confirm-publish`

Cloudflare project: `pp-restaurants`, URL prefix `https://pp-restaurants.pages.dev`.

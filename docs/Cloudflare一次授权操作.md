# Cloudflare：一次授权后自动更新 `pp-restaurants`

## 为什么不用 Google 邮箱自动登录？

你的 Cloudflare 曾通过 Google 邮箱登入，但这只是人的身份验证方式。无人值守自动发布**不需要也不应该**保存 Google 密码、Cookie 或绕过二步验证。正确方法：Cloudflare **API Token** + **Account ID**，用 Wrangler 发布。

## 一次性人工配置（在 Cloudflare 网页中完成）

1. 登录 Cloudflare → **My Profile / API Tokens**。
2. **Create Token** → Custom Token：名称如 `pp-pages-deploy`；限制至指定账户，Account 权限至少 `Cloudflare Pages: Edit`（Cloudflare 页面权限显示的名称可能略变，按官方文档核对）。不要使用 Global API Key，也不要给予 DNS、Billing 等不需要的权限。
3. 找到你的 Cloudflare **Account ID**：在账号页面、Workers & Pages 账户页或 API 文档指引的位置复制。
4. 将 Token 和 Account ID 安全写入本地运行环境或 GitHub Actions Secrets：`CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`。不要发给聊天助手。
5. 项目名称固定 `pp-restaurants`，不是邮箱名；Pages Project 仍然用最初建好的项目。
6. 模型的 Key 则用单独的 `PP_MODEL_*` 环境变量，与 Cloudflare 令牌完全隔离。

官方资料：https://developers.cloudflare.com/pages/how-to/use-direct-upload-with-continuous-integration/

## 发布原理

```bash
CLOUDFLARE_ACCOUNT_ID=... CLOUDFLARE_API_TOKEN=... \
 npx wrangler@4 pages deploy sites --project-name pp-restaurants --branch main
```

**重要**：这里的 `sites` 是全部餐饮店的完整快照，不是单个商家的文件夹！否则会使其他商家页面在新部署中消失。

## GitHub Actions Secrets

在属于你自己的 Agent 仓库 Settings → Secrets and variables → Actions 添加上面两个密钥。仓库内的 `.github/workflows/deploy-pages.yml` 可手动运行。还需要正确维护 `sites/`，并确认该仓库不会暴露私人源素材。

## 免费计划与国内访问

Cloudflare Pages Free 可托管纯静态资源，但中国大陆不同地区/运营商可访问性不保证。上线 URL 经过服务器外网验证仍不能替代国内移动网络、微信和抖音环境的真机抽样。图片/字体本地化，以降低外部 CDN 故障。

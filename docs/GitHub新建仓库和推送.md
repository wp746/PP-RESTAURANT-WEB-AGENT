# 一次性的 GitHub 上库操作

当前 GitHub 连接绑定账号：`wp746`。建议建立**单独仓库** `PP-RESTAURANT-WEB-AGENT`，不要将网站智能体混入既有海报/小程序仓库。

## 最简单步骤
1. 打开 https://github.com/new ，确认账号是 `wp746`。
2. Repository name 输入 `PP-RESTAURANT-WEB-AGENT`，选择 **Private** 或 **Public**：
   - 推荐 Private：源代码包含可公开的工具，但你若打算把商家素材/网站状态放同仓库，Private 更稳妥。其他智能体须有权限才可拉取。
   - 若设 Public：本项目只提交代码和**已批准公开**的网页成品，不得提交老板的原始素材包、合同和密钥。
3. 创建**空仓库**（可不勾选自动生成 README，因为本地已有完整 README）。
4. 用终端进入解压的 `PP-RESTAURANT-WEB-AGENT` 目录，执行：

```bash
git init
git branch -M main
git add .
git commit -m "feat: culture-first PP restaurant web agent v0.1"
git remote add origin https://github.com/wp746/PP-RESTAURANT-WEB-AGENT.git
git push -u origin main
```

GitHub Desktop 用户也可以 **File → Add Local Repository / Create Repository from Existing Folder → Publish repository**，不需要输入终端命令。授权由 GitHub 自己管理，**不要把 GitHub Token 发送给 ChatGPT**。

## 以后任意具备执行环境的智能体

```bash
git clone https://github.com/wp746/PP-RESTAURANT-WEB-AGENT.git
cd PP-RESTAURANT-WEB-AGENT
python -m pip install -e '.[qa,files]'
python -m playwright install chromium
# 导入安全密钥后
ppweb run /path/to/门店.zip --slug new-store --sites-dir sites --publish --confirm-publish --git-sync
```

真实自动执行的权限边界：GitHub clone ≠ 自动获得 Google / Cloudflare 账号。已在可信执行器设好 Cloudflare Pages scoped Token、Model Token 与 Git push 身份后，才能无人值守。

**GitHub 并不提供免费的通用 AI 推理执行器。** ChatGPT Work 等具备文件/代码/网页工具的智能体环境，可拉取此仓库执行；GitHub Actions 可以运行已有构建/部署任务，但设计模型调用和图片素材所需密钥/限额另行配置。

# 迁移指南：仓库转私有 + Pages 迁移

> 本文档记录云端为主架构（GitHub Actions 每日 4 次 + 状态文件随 repo 持久化）下的
> 隐私迁移思路。当前仓库保持 PUBLIC（用户决策：先跑通，以后再迁移）。
> 原因：GitHub Free 账户的私有仓库**没有 GitHub Pages**，只有 Public 仓库才有。
> 迁移到私有后，仪表盘需要换托管方案（推荐 Cloudflare Pages，免费且支持私有 repo）。

## 一、为什么当前是 Public

| 方案 | Pages 支持 | 费用 |
|------|-----------|------|
| GitHub Free + Public repo | 有 | 免费 |
| GitHub Free + Private repo | 无 | 免费 |
| GitHub Pro + Private repo | 有 | $4/月 |

## 二、迁移步骤（仓库转私有）

1. **预检**
   - 确认 Cloudflare 账号已注册（免费版即可）
   - 确认本地 `git pull` 已同步到最新（`ticktick_sync_state.json` 等状态文件齐全）
2. **GitHub 仓库转私有**
   - Settings → General → Danger Zone → Change visibility → Private
   - 转私有后 GitHub Pages 立即失效（仪表盘 404）
3. **迁移 Secrets（新仓库或原仓库均可）**
   - Settings → Secrets and variables → Actions，逐项确认：
     - `EMAILS_JSON`（多邮箱配置，含密码，**最敏感**）
     - `EMAIL_ADDRESS` / `EMAIL_PASSWORD` / `IMAP_SERVER` / `IMAP_PORT`（单邮箱回退）
     - `TICKTICK_API_KEY`
     - `FEISHU_WEBHOOK_URL`
   - 建议迁移时轮换一次 TickTick API Key 与飞书 Webhook（防历史泄露）
4. **历史数据清理（可选但建议）**
   - 转私有只影响未来访问，git 历史里的敏感信息（如曾误提交的 config.json）
     仍留在历史中。若确有泄露风险：
     - 用 `git filter-repo` 清洗历史（破坏性操作，先备份）
     - 或干脆新建空仓库重新推 main（状态文件都在，历史日志 run_log.jsonl 可选择保留）
5. **Pages 迁移到 Cloudflare Pages（免费，支持私有 repo）**
   - Cloudflare Dashboard → Workers & Pages → Create → Pages → Connect to Git
   - 授权 GitHub，选择本仓库（私有也可）
   - 构建配置：**无需构建**，直接部署静态文件
     - Framework preset: None
     - Build command: 留空
     - Build output directory: `gh-pages`
   - 但注意：GitHub Actions 里生成的 `gh-pages/` 目前是本地忽略、Pages artifact 方式部署的。
     迁移 Cloudflare 有两种做法：
     - **做法 A（推荐，改动最小）**：Cloudflare Pages 用 Direct Upload 模式，
       在 deploy.yml 里把 `actions/deploy-pages` 步骤换成
       `cloudflare/wrangler-action@v3`，`wrangler pages deploy gh-pages --project-name=bank-bill`。
       Secret 需加 `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID`。
     - **做法 B**：让 Cloudflare 自己拉仓库构建。需要把 `gh-pages/` 提交进 repo
       （去掉 .gitignore 里的 `gh-pages/`），Cloudflare 每次推送自动部署。
       缺点：每次运行产生额外 commit，日志噪音大。
6. **验证清单**
   - [ ] Actions 4 次 schedule 正常跑（转私有不影响 Actions）
   - [ ] 状态文件 commit 回推正常（`chore: append run log [skip ci]`）
   - [ ] 新仪表盘 URL 可访问（Cloudflare Pages `*.pages.dev`）
   - [ ] 飞书推送正常（时段守卫 07:00-22:30）
   - [ ] TickTick 任务无重复创建

## 三、Actions Secrets 迁移清单（速查）

| Secret | 用途 | 敏感度 |
|--------|------|--------|
| `EMAILS_JSON` | 多邮箱 IMAP 配置 | 高（含密码） |
| `EMAIL_ADDRESS` / `EMAIL_PASSWORD` | 单邮箱回退 | 高 |
| `IMAP_SERVER` / `IMAP_PORT` | 邮箱服务器 | 低 |
| `TICKTICK_API_KEY` | 滴答清单任务同步 | 高 |
| `FEISHU_WEBHOOK_URL` | 飞书群推送 | 中 |
| `CLOUDFLARE_API_TOKEN` | 迁移后 Pages 部署 | 高 |
| `CLOUDFLARE_ACCOUNT_ID` | 迁移后 Pages 部署 | 低 |

## 四、本地测试注意事项

本地已降级为测试环境（2026-10-10 起）：

- 本地计划任务 `BankBillDaily` 已禁用，云端为生产主力
- 本地测试入口：`python daily_run.py`（会真实写 TickTick + 飞书推送，
  测试时注意时段守卫会自动拦截凌晨推送）
- 本地 `auto-sync`（AutoGitHubSync-R BANK 计划任务）保留：每 10 分钟把本地
  修改推送 GitHub，作为云端状态的补充通道
- **注意**：本地测试运行会更新 `ticktick_sync_state.json` 等状态文件，
  auto-sync 推送后云端下次运行会以推送后的状态为基准——这是预期行为（状态闭环）

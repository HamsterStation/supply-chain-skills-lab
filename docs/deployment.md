# 部署、账号和恢复

最终架构遵循用户后续选择：GitHub Pages 托管 React 静态前端；Cloudflare Worker 负责 GitHub App 登录与个人仓库同步；D1 只保存会话、加密的 GitHub token 和所选仓库元数据。没有自建服务器、Docker、真实业务系统连接或 AI 接口。

## 1. 本地学习预览

在项目目录：

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m scripts.generate.bundle
npm ci --prefix frontend
npm run dev --prefix frontend
```

本地地址 `http://127.0.0.1:5187`。Vite 开发模式在未配置登录服务时允许本地课程预览，明确不模拟真实身份；生产构建始终要求真实登录，未配置时显示配置未完成而不是放开私人界面。

## 2. 准备 GitHub App

在 GitHub Developer settings → GitHub Apps → New GitHub App 创建应用。管理员只做一次；每个学习者自行登录并授权所选仓库。

- App 名称使用可用的 `Supply Chain Skills Lab` 变体。
- Homepage URL：GitHub Pages 网站地址。
- Callback URL：`https://你的-worker.workers.dev/auth/callback`。
- 不启用 webhook（不需要业务事件）。
- Repository permissions：Contents Read and write、Pull requests Read and write；Metadata 是必要的只读权限。不要授权 Administration、Actions、Secrets 或 Workflows。
- Account permissions 留空；只请求默认身份资料。启用用户 token 到期，保持 8 小时过期。
- Where can this GitHub App be installed：Any account，才能供其他学习者使用。
- 保存 Client ID、应用 slug；在服务端配置 Client secret，绝不可填写进 Pages 前端、源码或聊天。

依据：[GitHub App 用户登录流程](https://docs.github.com/en/apps/creating-github-apps/authenticating-with-a-github-app/generating-a-user-access-token-for-a-github-app)、[注册说明](https://docs.github.com/en/apps/creating-github-apps/registering-a-github-app/registering-a-github-app)。用户 token 受 App 和用户权限交集约束。

## 3. 部署登录服务

进入 auth-worker 并安装依赖后：

```bash
npm ci
npx wrangler login
npx wrangler d1 create supply-chain-auth
```

将返回的 database_id 写入 `wrangler.jsonc`；配置 SITE_URL（必须是网站完整固定地址，以 `/` 结尾）、GITHUB_CLIENT_ID、GITHUB_APP_SLUG。这三项不是密钥。

```bash
npx wrangler secret put GITHUB_CLIENT_SECRET
npx wrangler secret put TOKEN_ENCRYPTION_KEY
```

TOKEN_ENCRYPTION_KEY 使用本机密码管理工具生成的随机 32 字节 Base64 值。也可以用 `openssl rand -base64 32` 生成，直接存入服务端 secret 和自己的密码管理器，不提交到 Git。

```bash
npx wrangler d1 migrations apply supply-chain-auth --remote
npx wrangler deploy
```

`/health` 应返回 `ready:true`。Worker 的请求日志默认关闭，代码也不输出 token、个人记录或 GitHub 响应正文。GitHub OAuth token 用 AES-GCM 加密存储。OAuth state 有浏览器绑定、PKCE、10 分钟有效期；传给 Pages 的票据一次性、60 秒且绑定前端 verifier。浏览器只保留应用自己的短期会话标识在 sessionStorage，原始 GitHub token 从不进入浏览器。API 对固定网站 origin 校验，并限制频率与大小。

## 4. 发布 Pages

仓库 Settings → Pages 的 Source 选 GitHub Actions。仓库变量 `AUTH_SERVICE_URL` 填 Worker HTTPS 地址，不带尾部斜杠。运行 Publish learning site。只有发布 job 持有 Pages 权限；构建和校验没有发布权限。生产默认登录关闭，直到这个变量和 Worker 均正确配置。

需要给 Actions 创建内容 PR 时，按 update-workflow.md 设置仓库开关与分支保护；不要为绕过保护改用宽权限长期 token。其他 GitHub App 方案须明确单独权限。

## 5. 每位学习者第一次进入

1. 使用自己的 GitHub 登录，界面显示该账号。
2. 在 GitHub 自己的个人账户建立私有记录仓库，勾选添加 README。当前不支持组织共享库，避免团队成员可见性与“个人”含义混淆。
3. 安装 GitHub App 时选 Only select repositories，仅选这个记录仓库。
4. 在个人空间刷新仓库列表，选择这个仓库，先拉取，再同步。
5. 本机保存不会立即发网络请求。点击同步后创建/更新单一私有 PR，学习者自行审核合并。新的设备可从待合并 PR 读取最新版，因此不必每次编辑后立即合并。

同一记录 ID 不得被重写；冲突先拉取并合并。其他设备的笔记或作答未合并时服务端拒绝同步。仓库公开、不是本人拥有、无写权限、被归档或 token 已撤销均拒绝。文本不执行；路径固定，不可选择任意仓库文件。每份远程状态上限 750 KB，超出时先导出归档。

## 6. 备份、升级与回滚

个人空间可导出全部 JSON，包含题目/案例快照与历史记录。恢复合并，不清空本机记录；同 ID 不同内容拒绝导入。也可从自己的私有仓库保留的 Git 历史恢复数据。切换账号按 GitHub 数字 ID 分开浏览器数据库；退出清除当前界面和应用会话，保留该账号本机缓存以便下次使用。共用设备需要关闭浏览器会话并管理本机存储。

课程更新只发布静态内容；不重建 D1、不清空本机数据库或私人仓库。要回滚课程，可 revert 对应内容提交并重新发布。D1 schema 迁移只在 auth-worker 维护步骤单独运行。

D1 运维备份可以使用 `wrangler d1 export supply-chain-auth --remote --output 私有路径/auth-backup.sql`；备份包含加密凭据，仍是敏感文件，不进 Git。恢复到新 D1 数据库后核查迁移版本和密钥配置，再切换绑定。TOKEN_ENCRYPTION_KEY 必须独立安全备份；如果遗失则使旧会话失效并要求所有人重新登录，不尝试解密或导出原 token。

2026-09-22 已部署 GitHub Pages、Cloudflare Worker 和 D1，并完成 HamsterStation 的真实 GitHub 登录、私有仓库选择和记录 PR 保存。GitHub App 安装权限已核对为仅选择 supply-chain-learning-records。两个不同真实账号、真实多设备和撤销授权后的全链路验证仍待补充；本地两账号 Mock 测试不能替代这些验证。

当前网站：https://hamsterstation.github.io/supply-chain-skills-lab/

当前服务：https://supply-chain-auth.supply-chain-auth.workers.dev

GitHub App：https://github.com/apps/supply-chain-skills-lab-hs

部署回归可运行 Check deployed login service 工作流；它只检查健康状态、匿名拒绝和授权跳转，完整登录仍以真实浏览器结果为准。OAuth 与 GitHub API 请求使用 manual 重定向并拒绝 3xx，避免不受 workerd 支持的 redirect:error，也防止凭据被转发到其他地址。

本机 scripts/setup/github_app.py 可通过官方 manifest 流程登记新安装，不需要在聊天中复制密钥。生成的 private/github-app-secret.json 仅限本机读取并已忽略；请按密钥文件管理，不要加入公共仓库。

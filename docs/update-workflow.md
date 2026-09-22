# 内容更新、权限与审核

2026-09-22 核查 GitHub 官方文档：

- [GITHUB_TOKEN 的触发规则](https://docs.github.com/en/actions/concepts/security/github_token)：机器人创建或更新 PR 后，opened/synchronize/reopened 可产生等待批准的检查，写权限人员须点击 Approve workflows to run；其他 token 触发事件一般不会递归运行。不能假定 push 自动继续发布。
- [仓库 Actions 设置](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/enabling-features-for-your-repository/managing-github-actions-settings-for-a-repository)：允许 GitHub Actions 创建 PR 的开关受仓库及组织策略控制。新个人仓库默认可能不允许。
- [Pages 自定义工作流](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)：构建与部署分开；部署 job 才持有 pages:write 和 id-token:write。

## 自动流程

`content-update.yml` 每周一 UTC 02:17 检查，也可手动运行。`publish=false` 只产生预览 artifact，不提交或发布。默认上限 3 项实质变化，可在配置和受信任写入器同步调整。

1. 采集 job 只有 contents:read。从状态分支恢复检查点，按来源配置和 robots 获取允许的公开正文，去掉导航、广告、页面时间等噪声，计算指纹。
2. 独立 validate job 没有任何发布、模型或写入密钥，校验内容与提案。
3. propose job 才拥有 contents:write、pull-requests:write；重新校验提案；用固定路径构造 Git tree，不执行外部生成的命令或 PR 代码。
4. 人工检查草稿、按需批准检查并审核内容，决定合并。main 分支 push 后运行 `pages.yml`。不自动审核或合并。

每个已启用来源的首次合法获取建立基线，不宣称资料是新发布。只有后续正文发生变化才产生待核查草稿。没有可靠 RSS/API 的来源不假装有；目前实现受控公开页面 provider。搜索 API 与模型生成均 disabled。新增 provider 要独立实现、验证条款和密钥边界。

## 持久状态与恢复

状态保存在远程 `automation/collector-state` 分支的 `content/updates/collector-state.json`，只保存公开来源指纹、检查时间、失败队列、拒绝指纹与待审核 PR 头部。这个分支不发布、不含个人数据。不能只依赖 runner 临时目录或 Actions 缓存。构建源分支仍只读状态。

每次写状态前比较预期远程 SHA；并发变化直接拒绝。工作流不并发执行。失败来源保留旧指纹与内容；重跑从旧状态继续。上限之外的来源保持旧指纹，下次重新处理。

仅维护一个自动内容 PR。检测到人类修改（head 不符）、任何 review 或 comment 时停止追加，等待维护者处理。自动 PR 被关闭拒绝后，相同来源指纹进入拒绝集合。关闭的分支不会强制覆盖；后续有新材料时，维护者先归档并删除旧自动分支后重跑。合并后的自动分支也由维护者删除，避免重写历史。此保守边界优先保护人工内容。

注意：propose 的检查点写入发生在 PR 提案操作完成后。若中断在“内容分支已写但状态未写”窗口，重跑会识别未知 head 并停下，不会覆盖；维护者应核查分支并恢复状态或删除无人修改的未审核分支后重跑。这是有意的人工恢复点，不宣称所有外部 API 操作原子化。

## 本地 dry-run

```bash
python -m scripts.collect.pipeline --out work/collection
python -m scripts.collect.github_pr --proposal work/collection/proposal.json
```

默认不修改检查点。如要在私有本机目录保存多次采集状态，添加 `--commit-local-state`。`work/`、`state/` 不进 Git。

初始四个候选来源已配置但未自动启用。CIPS 程序访问 403，保持停用；其余来源需要按实际定时用途进一步复核条款。确认后设置 enabled 和 terms_reviewed，并配置准确 selector；不能为凑更新数量启用未知访问方式。

## 两种 PR 绝不混用

公开内容 PR 在网站仓库运行上述 Actions，不持有任何学习者 OAuth token。个人记录 PR 由登录服务使用该学习者 GitHub App 用户授权，写其本人私有仓库的 `learning/state.json`，不调用内容更新工作流，也不进入公开 artifact 或日志。

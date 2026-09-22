# 验收报告（2026-09-22）

## 实际完成

- 独立 React + TypeScript 项目；中文界面；六个学习入口与六条岗位方向；A–H 技能分类。
- 18 个来源条目，16 条具体证据，18 张技能卡，8 节完整原创课程，2 个固定种子合成实战案例。每课都有例子、步骤、题目、变式、提示、解析、评分维度、误解、来源与限制。
- 阅读/带练切换、中文/英文/同义词搜索、方向/工具/层级筛选、自由浏览、课程路线调整、可调整复习、版本化笔记与作答、实战固定计算反馈、CSV 与参考计算下载、备份导出及合并恢复。
- 每 GitHub 数字用户 ID 隔离本机数据库；生产必须真实登录。GitHub App OAuth state/PKCE、短期应用会话、服务端加密 token、本人私有仓库校验、个人记录 PR 同步与冲突保护代码已实现。
- 公开内容采集 dry-run、去噪与去重、失败队列、远程持久状态分支、单一待审核内容 PR、路径/schema 白名单、GitHub Actions 分阶段权限、Pages 构建发布。

## 已执行的本地检查

- Python：17 项通过，覆盖内容引用、案例数值、零分母/缺失/非法值、指标与预测假设、路径穿越/HTML/未知字段/符号链接拒绝、岗位与厂商范围、去重/无变化/来源失败/拒绝后不重提。
- Node：8 项通过，覆盖凭据加密、本人私有可写仓库、跨设备记录防丢失、负载限制、匿名拒绝、OAuth state/PKCE/一次性票据和过期状态冲突。另有 1 项实际 workerd + D1 测试通过，GitHub 上游响应使用 Mock；复现并防止 redirect:error 导致生产登录回调失败。
- 浏览器：6 项通过，覆盖课程阅读带练、提示来源、独立变式、笔记刷新持久、案例多次提交不覆盖、备份往返、画像保存、中英文别名搜索及手机/桌面无横向溢出均通过。
- 两账号隔离和 GitHub 同步交互使用明确的 Mock API；不冒充真实 OAuth 联调。
- TypeScript 与生产构建通过。
- 默认配置真实运行 dry-run：MIT OCW 历史课程目录产生 1 项首次收录草稿，原文定位标记均匹配；其他 4 项候选保持 disabled。首次收录明确不是新近发布。测试确认无变化重跑不再提案。

## 真正核查过的来源

MIT OCW 基础/库存/MRP/运输讲义、FPP3 预测方法与评价、Microsoft 类型/重复值/SQL 文档、CIPS 框架/TCO/寻源/风险公开页面、MIT 数字供应链研究入口。

CIPS 公开文本通过浏览工具核查，程序 HTTP 请求 403；哈希只对应已登记短摘录。其他成功程序访问来源记录 HTTP 响应字节哈希。没有绕过限制。历史讲义明确年代，不当作现行法规或当前软件教程。来源目录的研究成效数字未采用。没有未经核验的企业岗位或所谓行业共识。

## 真实服务验证与剩余边界

- 已部署 GitHub App、Cloudflare Worker、D1 与 GitHub Pages。HamsterStation 真实浏览器登录成功、显示本人界面、选择本人私有仓库、创建初始记录 PR、重复保存不新增提交、刷新后拉取该 PR 均成功。安装范围已收窄并核对为仅该记录仓库。
- 两个不同真实账号各自私有仓库、撤销授权后的完整交互、真实多设备同步仍未完成联调；对应隔离与冲突规则使用 Mock/本地测试验证，不能混淆。
- 人工审批、合并自动内容 PR 的步骤必须由用户完成；本项目不自行批准或合并自己的 PR，也不绕过分支保护。
- MIT OCW 课程目录已核查使用条件、robots 和正文 selector 并启用每周检查，其他候选保持停用。没有启用 RSS、搜索 API 或模型供应商。
- 内容仍待供应链领域专家复核，不是机构认证课程。
- AI 辅导没有启用；不存在模型密钥、付费模型接口或真实模型调用测试。

## 线上内容流程

2026-09-22 已实际运行 collect → validate → propose，三阶段均成功，创建 [内容草稿 PR #1](https://github.com/HamsterStation/supply-chain-skills-lab/pull/1)，仅新增一份 content/updates JSON。内容为 MIT OCW 历史课程目录的首次收录核查，不宣称近期行业变化。

[线上发布](https://github.com/HamsterStation/supply-chain-skills-lab/actions/runs/35730579862)、[完整自动检查](https://github.com/HamsterStation/supply-chain-skills-lab/actions/runs/35730579705)、[匿名登录服务检查](https://github.com/HamsterStation/supply-chain-skills-lab/actions/runs/35730662312) 均成功。[无变化重跑](https://github.com/HamsterStation/supply-chain-skills-lab/actions/runs/35730974219) 成功：0 项新增、仍为同一 PR、内容分支 head 未改变，远程检查点持久化正常。

机器人创建的 PR 检查实际进入 action_required，等待维护者批准工作流运行；这验证了不能假定 GITHUB_TOKEN 创建 PR 后检查会自动执行。人工批准、审核及合并尚未执行；遵守不自我批准、不自动合并的边界。

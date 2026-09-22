# Supply Chain Skills Lab

中文优先的供应链技能学习网站。18 张有可追溯来源的技能卡、8 节完整课程、2 个固定种子的原创合成案例。课程阅读、固定练习、参考解析、笔记、学习路线和备份无需模型密钥。

已部署：[进入学习网站](https://hamsterstation.github.io/supply-chain-skills-lab/)。

架构：GitHub Pages 公共课程 + GitHub App 个人登录 + 本人私有仓库学习记录 PR。轻量登录与同步服务使用 Cloudflare Worker；无需维护服务器。首次部署需完成 GitHub App 和 Worker 配置，生产版在配置完成前关闭登录，不提供假账号。

## 本地启动

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m scripts.generate.bundle
npm ci --prefix frontend
npm run dev --prefix frontend
```

打开 http://127.0.0.1:5187 。未配置登录服务时，仅开发模式使用本机预览数据；没有导入任何其他学习项目的数据。

## 验证

```bash
.venv/bin/python -m scripts.validate.content
.venv/bin/pytest -q
node --test auth-worker/test/*.test.mjs
npm ci --prefix auth-worker
npm run test:runtime --prefix auth-worker
npm run build --prefix frontend
# 另一个终端保持开发服务运行，安装 Google Chrome 后：
npm run test:e2e --prefix frontend
```

## 文档

- [部署、GitHub App、升级、回滚和备份](docs/deployment.md)
- [采集、dry-run、PR 与权限](docs/update-workflow.md)
- [内容证据规范](docs/content-policy.md)
- [教学设计与计算假设](docs/teaching-design.md)
- [验收报告](docs/acceptance-report.md)

首版来源经过公开页面核查，尚待供应链领域专家复核；不宣称认证或学习成果保证。已启用 MIT OCW 课程目录的每周检查；CIPS 等其余候选自动访问保持关闭；没有将 Mock 资料当作真实专业证据。AI、搜索 API、岗位采集与商业系统操作未启用。

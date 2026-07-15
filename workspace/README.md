# 容器工作区导航

本目录用于把 Windows 的 `25春新进度` 资料与 WiTwin 容器开发环境放在同一工作区中。

## 推荐入口

- 科研文档：`project-docs/`
- Windows 目录完整快照：`host_snapshot/`
- OptiX 修复和环境辅助材料：`support/`
- WiTwin Core/Channel 源码：`../src/`
- 环境与会话说明：`../docs/`

## 目录性质

`host_snapshot/` 是 2026-07-15 从 Windows 当前目录复制来的完整快照，包含 `.claude`、`.witwin-optix-workaround` 和主要科研文档。

`project-docs/` 与 `support/` 中的项目是符号链接，用于提供更清晰的入口，不会重复占用大体积 OptiX 文件空间。编辑链接目标会修改容器快照中的对应文件。

## 重要提示

- 这不是 Windows 目录的实时挂载；容器内修改不会自动回写 Windows。
- 不要把 `host_snapshot/` 当作可随意清理的缓存。
- Python 代码应使用 `/opt/witwin/venv/bin/python`。
- 开始新的 Codex 对话前先阅读 `/opt/witwin/docs/SESSION_CONTEXT_2026-07-15.md`；在 `/opt/witwin` 下工作时，Codex 也会自动读取 `/opt/witwin/AGENTS.md`。


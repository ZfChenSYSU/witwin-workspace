# 容器工作区导航

本目录用于把 Windows 的 `25春新进度` 资料与 WiTwin 容器开发环境放在同一工作区中。

## 推荐入口

- 当前科研与工程文档：`../docs/current/`
- 历史报告与旧计划：`../docs/history/`
- 长期参考资料：`../docs/reference/`
- Windows 目录完整快照：`host_snapshot/`
- OptiX 修复和环境辅助材料：`support/`
- WiTwin Core/Channel 源码：`../src/`
- iPhone 采集应用：`../apps/ios-recorder/`
- CSI Linux 采集端：`../capture/csi-linux/`
- 视频 SLAM/三维重建：`../pipelines/reconstruction/`
- WiTwin 实验：`../pipelines/witwin/`
- 三端公共协议：`../schemas/session-format/`
- 本地实验数据：`../datasets/`
- 文档总入口：`../docs/`

## 目录性质

`host_snapshot/` 是 2026-07-15 从 Windows 当前目录复制来的完整快照，包含 `.claude`、`.witwin-optix-workaround` 和主要科研文档。

`project-docs/` 现在只保留迁移提示；科研文档已经集中到仓库根目录的 `docs/`。`support/` 仍是 OptiX 等辅助材料入口。

## 重要提示

- 这不是 Windows 目录的实时挂载；容器内修改不会自动回写 Windows。
- 不要把 `host_snapshot/` 当作可随意清理的缓存。
- Python 代码应使用 `/opt/witwin/venv/bin/python`。
- 开始新的 Codex 对话前先阅读 `/opt/witwin/docs/current/README.md` 和对应分支状态；在 `/opt/witwin` 下工作时，Codex 也会自动读取 `/opt/witwin/AGENTS.md`。

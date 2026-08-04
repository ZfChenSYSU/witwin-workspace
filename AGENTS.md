# WiTwin 工作区指令

## 开始工作前

1. 先阅读 `/opt/witwin/docs/current/README.md` 和本次任务对应的分支状态文档。
2. 默认使用中文与用户沟通。
3. 工作目录默认是 `/opt/witwin`；全部科研与工程文档的权威入口是 `/opt/witwin/docs`。

## Python 与 GPU 环境

- WiTwin Python 环境固定为 `/opt/witwin/venv`。
- 运行 Python 前先执行 `source /opt/witwin/venv/bin/activate`，或者直接使用 `/opt/witwin/venv/bin/python`。
- 不要用系统 `python3` 安装或运行 WiTwin 依赖。
- 保留环境变量 `DRJIT_LIBOPTIX_PATH=/usr/lib/x86_64-linux-gnu/libnvoptix.so.1`。
- 完整验证命令：`/opt/witwin/venv/bin/python /opt/witwin/validate_witwin.py`。

## 源码与资料边界

- WiTwin Core 源码：`/opt/witwin/src/witwin-core`。
- WiTwin Channel 源码：`/opt/witwin/src/witwin-channel`。
- iOS 采集端：`/opt/witwin/apps/ios-recorder`。
- CSI Linux 采集端：`/opt/witwin/capture/csi-linux`。
- 视频 SLAM/三维重建：`/opt/witwin/pipelines/reconstruction`。
- WiTwin 实验与产物：`/opt/witwin/pipelines/witwin`。
- 三端公共会话、时间和坐标协议：`/opt/witwin/schemas/session-format`。
- 本地原始/处理中数据：`/opt/witwin/datasets`，默认不提交 Git。
- `/opt/witwin/workspace/host_snapshot` 是 Windows 当前目录在 2026-07-15 的完整快照。除非用户明确要求，不要批量移动、重命名或删除其中内容。
- `/opt/witwin/workspace/project-docs` 仅保留旧入口说明，不再作为文档编辑位置。
- `/opt/witwin/workspace/support` 和 `host_snapshot` 属于历史快照/辅助材料，不是当前文档源。

## 文档管理

- `docs/current/`：仍在维护的主计划、总进度和各分支最新状态；采用无日期文件名并原位更新。
- `docs/history/`：带日期的阶段报告、旧版计划、已完成实验报告和环境交接；默认只读归档。
- `docs/reference/`：长期有效的使用指南、工作流和技术调研。
- 各代码目录只保留简短 `README.md` 说明职责、运行入口和权威文档链接；`schemas/` 中与格式实现共同演进的协议规范可继续就近维护。不要在 `pipelines/`、`apps/`、`capture/` 或 `workspace/` 新建独立进度报告。
- 实验脚本、机器结果和图像继续放在 `pipelines/`；实验 Markdown 报告放在 `docs/history/branches/<branch>/experiments/`。
- 完成阶段工作时，先更新 `docs/current/branches/<branch>.md`，再归档详细报告，并同步更新 `docs/current/项目当前进展与下一步方向.md`（若影响跨分支结论）。
- 新文档不得复制维护另一份“当前状态”；应链接 `docs/current/` 中的权威文档。

## 分支职责

- `main`：已验证的集成状态和公共协议。
- `work/wsl-witwin`：WSL/GPU、重建、WiTwin 和离线分析。
- `work/csi-linux`：PicoScenes、网卡、CSI/UDP 采集和数据整理。
- `work/ios-recorder`：Mac/Xcode 上的 iPhone 采集应用。
- 三端共享字段优先修改 `schemas/session-format`，并通过 `main` 同步；不要各自维护不兼容副本。
- 大体积视频、CSI、点云和网格放在 `datasets` 或外部存储，只提交元数据、校验和、小型测试样本和处理脚本。

## 兼容性决策

- 当前已验证组合：WiTwin Core 0.0.2、WiTwin Channel 0.1.0、RayD 0.4.0、DrJit 1.3.1、PyTorch 2.10.0+cu128。
- 不要在未做兼容性评估和回归验证的情况下升级 WiTwin Channel、RayD 或 DrJit。
- 确定性信道及 LOS 路径、CIR、CFR 已通过；当前上游组合的原生反射 EPC 尚未通用通过。显式 DrJit 反射后端已有独立实验成功，但不能写成原生反射能力已经全面验证。

## 故障处理偏好

- 如果 WSL 无法访问，或 WSL/容器因代理配置导致无法联网，先停止会改变配置的操作，向用户说明证据并给出修改建议，等待用户决定。
- 诊断优先采用只读检查；不要未经确认修改 Windows 代理、WSL 网络或 Docker Desktop 网络设置。
- WSL2 OptiX 修复涉及 Windows `C:\Windows\System32\lxss\lib`。宿主备份在 `E:\Docment\科研\科研\25春新进度\.witwin-optix-workaround\lxss-lib-backup-20260714-165259`，不要擅自删除。

## Codex 环境

- `CODEX_HOME` 是 `/root/.codex`，目录已经创建且权限为 `700 root:root`。
- VS Code 容器扩展自带 Codex CLI；不要求系统全局安装 `codex`、Node.js 或 npm。
- 如果 Codex 面板显示旧的启动错误，优先让 VS Code 执行“开发人员: 重新加载窗口”。

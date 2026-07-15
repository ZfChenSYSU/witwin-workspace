# WiTwin 工作区指令

## 开始工作前

1. 先阅读 `/opt/witwin/docs/SESSION_CONTEXT_2026-07-15.md`。
2. 默认使用中文与用户沟通。
3. 工作目录默认是 `/opt/witwin`；科研资料入口位于 `/opt/witwin/workspace/project-docs`。

## Python 与 GPU 环境

- WiTwin Python 环境固定为 `/opt/witwin/venv`。
- 运行 Python 前先执行 `source /opt/witwin/venv/bin/activate`，或者直接使用 `/opt/witwin/venv/bin/python`。
- 不要用系统 `python3` 安装或运行 WiTwin 依赖。
- 保留环境变量 `DRJIT_LIBOPTIX_PATH=/usr/lib/x86_64-linux-gnu/libnvoptix.so.1`。
- 完整验证命令：`/opt/witwin/venv/bin/python /opt/witwin/validate_witwin.py`。

## 源码与资料边界

- WiTwin Core 源码：`/opt/witwin/src/witwin-core`。
- WiTwin Channel 源码：`/opt/witwin/src/witwin-channel`。
- `/opt/witwin/workspace/host_snapshot` 是 Windows 当前目录在 2026-07-15 的完整快照。除非用户明确要求，不要批量移动、重命名或删除其中内容。
- `/opt/witwin/workspace/project-docs` 和 `/opt/witwin/workspace/support` 是整理后的符号链接入口；从这些入口编辑会修改快照中的对应文件。
- 容器内生成的说明和交接文档统一放在 `/opt/witwin/docs`。

## 兼容性决策

- 当前已验证组合：WiTwin Core 0.0.2、WiTwin Channel 0.1.0、RayD 0.4.0、DrJit 1.3.1、PyTorch 2.10.0+cu128。
- 不要在未做兼容性评估和回归验证的情况下升级 WiTwin Channel、RayD 或 DrJit。
- 确定性信道及 LOS 路径、CIR、CFR 已通过；反射路径 `max_bounces > 0` 尚未通过当前上游组合验证，回答时必须保留这一限制。

## 故障处理偏好

- 如果 WSL 无法访问，或 WSL/容器因代理配置导致无法联网，先停止会改变配置的操作，向用户说明证据并给出修改建议，等待用户决定。
- 诊断优先采用只读检查；不要未经确认修改 Windows 代理、WSL 网络或 Docker Desktop 网络设置。
- WSL2 OptiX 修复涉及 Windows `C:\Windows\System32\lxss\lib`。宿主备份在 `E:\Docment\科研\科研\25春新进度\.witwin-optix-workaround\lxss-lib-backup-20260714-165259`，不要擅自删除。

## Codex 环境

- `CODEX_HOME` 是 `/root/.codex`，目录已经创建且权限为 `700 root:root`。
- VS Code 容器扩展自带 Codex CLI；不要求系统全局安装 `codex`、Node.js 或 npm。
- 如果 Codex 面板显示旧的启动错误，优先让 VS Code 执行“开发人员: 重新加载窗口”。


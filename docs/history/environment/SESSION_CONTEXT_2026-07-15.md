# WiTwin 容器会话交接

更新时间：2026-07-15（Asia/Shanghai）

## 1. 用户目标

用户希望依据原始 `WiTwin使用说明.md`，在 WSL 的 Docker 容器中获得可直接开发和验证的 WiTwin Core/Channel 环境，并能通过 VS Code 图形界面和容器内 Codex 继续提问、修改与执行。

用户特别要求：若 WSL 无法访问，或 WSL/容器出现代理配置错误导致无法联网，应先暂停配置变更，报告诊断证据和建议，再询问用户如何处理。

## 2. 当前运行状态

- 容器名：`witwin-dev-20260714`
- 容器镜像：`witwin-dev:20260714-final`
- 工作目录：`/opt/witwin`
- 重启策略：`unless-stopped`
- 共享内存：2 GiB
- GPU：NVIDIA GeForce RTX 4050 Laptop GPU，计算能力 8.9
- 容器目前使用 root 用户。

进入容器：

```bash
docker exec -it witwin-dev-20260714 bash
```

在 VS Code 中使用 Dev Containers 扩展，选择“附加到正在运行的容器”，再打开 `/opt/witwin`。

## 3. 已安装并验证的技术栈

- 基础镜像：`nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04`
- Python：3.12.3，虚拟环境 `/opt/witwin/venv`
- PyTorch：2.10.0+cu128
- DrJit：1.3.1，LLVM 和 CUDA 后端均可用
- WiTwin Core：0.0.2，源码提交 `897ee1cdee3b4f35fb0db0c153197f5ebfcce21f`
- WiTwin Channel：0.1.0，标签 `witwin-channel-v0.1.0`，源码提交 `86ec9321e1d7e9288c53ddce3beb68631f92f12d`
- RayD：0.4.0
- 其他主要包：NumPy 2.4.1、Matplotlib 3.10.8、tqdm 4.67.1、nanobind 2.9.2、scikit-build-core 1.0.3、pytest 9.1.1。

Core 和 Channel 均从 `/opt/witwin/src` 中的源码以 editable 模式安装。之所以使用 Channel 0.1.0，是因为当前 Channel 主分支要求尚不存在的 Core 0.3 系列，而输入说明对应 0.1.0 API。RayD 0.4.0 是当前栈中可运行 `rayd.Scene` API 的兼容选择。

## 4. 验证结论

以下项目已通过：

- PyTorch 能识别 RTX 4050 并执行 CUDA 张量运算。
- DrJit LLVM、CUDA 后端可用。
- 确定性信道模型输出形状为 `[1, 4, 4]`，数值有限。
- LOS 路径计算通过。
- CIR 和 CFR 计算通过，结果位于 CUDA 设备且数值有限。
- `pip check` 无损坏依赖。

重新验证：

```bash
source /opt/witwin/venv/bin/activate
python /opt/witwin/validate_witwin.py
```

或不激活虚拟环境：

```bash
/opt/witwin/venv/bin/python /opt/witwin/validate_witwin.py
```

结果文件：`/opt/witwin/logs/validation.json`。

已知限制：反射路径 EPC，即 `max_bounces > 0`，尚未在当前 Channel/RayD 组合中通过。不能把 LOS 验证扩展解释为完整反射路径已经验证。

## 5. WSL2 OptiX 处理

最初 WSL 只暴露了不完整的 OptiX 运行文件，导致求解器初始化失败。在用户明确授权后，从 NVIDIA 官方驱动包中仅提取所需运行库，没有在 WSL 中安装 Linux 显卡驱动。

关键设置：

```text
DRJIT_LIBOPTIX_PATH=/usr/lib/x86_64-linux-gnu/libnvoptix.so.1
```

Windows `C:\Windows\System32\lxss\lib` 中相关文件已更新，并恢复为 `NT SERVICE\TrustedInstaller` 所有。最终宿主备份：

```text
E:\Docment\科研\科研\25春新进度\.witwin-optix-workaround\lxss-lib-backup-20260714-165259
```

修复材料的容器快照入口：`/opt/witwin/workspace/support/optix-workaround`。

## 6. 网络和 Codex 诊断历史

容器网络检查结果：

- Docker bridge、默认路由和 DNS 正常。
- `api.openai.com` 可访问；无认证请求返回 HTTP 401，符合预期。
- GitHub 返回 HTTP 200。
- 容器中未发现异常代理环境变量。
- `auth.openai.com` 和 `chatgpt.com` 对命令行 curl 返回 Cloudflare challenge 403，但这不是当时 Codex 启动失败的直接原因。

Codex 当时无法启动的直接原因是 `CODEX_HOME=/root/.codex`，而该目录不存在。现已完成：

- 创建 `/root/.codex`。
- 设置权限 `700 root:root`。
- 扩展自带 `codex-cli 0.144.2` 已成功初始化状态数据库。
- 容器已经重启验证目录可持久保留。

VS Code Codex 扩展目录：

```text
/root/.vscode-server/extensions/openai.chatgpt-26.707.71524-linux-x64
```

## 7. 当前工作区布局

```text
/opt/witwin/
├── AGENTS.md                         # Codex 自动读取的工作规则
├── docs/
│   ├── GENERATED_CONTENT.md          # 初次环境生成说明
│   ├── SESSION_CONTEXT_2026-07-15.md # 本交接文档
│   └── WiTwin使用说明.md
├── logs/validation.json
├── src/
│   ├── witwin-core/
│   └── witwin-channel/
├── validate_witwin.py
├── venv/
└── workspace/
    ├── README.md
    ├── host_snapshot/                # Windows 当前目录完整快照
    ├── project-docs/                 # 主要科研文档便捷入口
    └── support/                      # OptiX 等辅助资料入口
```

`host_snapshot` 保留复制时的原始层次和隐藏文件。`project-docs`、`support` 使用符号链接整理入口，因此通过这些入口修改文件会同步修改快照内对应文件，但不会自动回写 Windows 宿主目录。

## 8. 后续操作原则

- 运行 WiTwin 代码时使用 `/opt/witwin/venv`，不要直接调用系统 Python。
- 修改科研内容优先从 `/opt/witwin/workspace/project-docs` 进入。
- 修改 Core/Channel 代码时直接在 `/opt/witwin/src` 对应仓库工作，并在修改前检查 Git 状态。
- 不要随意升级 Channel、RayD、DrJit；升级后至少重跑 `/opt/witwin/validate_witwin.py`。
- 不要删除 OptiX 宿主备份，也不要未经用户确认再次修改 Windows WSL 系统库。
- 容器内副本不是实时宿主挂载。若需要持续双向同步，应先与用户确定使用 bind mount、Git 或明确的复制方向，避免覆盖较新的文件。

## 9. 上下文压缩边界

本文保留了后续执行所需的事实、版本选择、路径、风险、限制和用户偏好；未保存逐字聊天记录、网页登录状态、Cookie、令牌或其他认证材料。


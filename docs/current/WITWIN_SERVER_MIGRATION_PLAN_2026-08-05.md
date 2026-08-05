# WiTwin 服务器精简迁移与环境安装计划

日期：2026-08-05  
目标服务器：`root@192.168.3.2:8048`  
目标目录：`/root/nfs/chenzhf/witwin`  
状态：**仅完成只读审计与方案设计，尚未在目标服务器创建目录、传输项目或安装环境。**

## 1. 目标与范围

不迁移当前 Docker 镜像、容器根文件系统、WSL 专用 OptiX workaround 或现有
Python 虚拟环境。只迁移对科研项目有用且不可由依赖管理器重建的源码、实验、
协议、文档和小型结果，再在服务器的独立项目目录中重建固定版本环境。

迁移和安装不得修改或删除服务器已有项目、已有 Conda 环境及其他用户的数据。

## 2. 已确认的源端内容与体积

- `/opt/witwin` 总计约 8.4 GB。
- `/opt/witwin/venv` 约 7.1 GB，可重建，不迁移。
- `workspace/host_snapshot/.witwin-optix-workaround` 约 1.2 GB，只适用于
  Windows/WSL，不迁移。
- `src/witwin-channel/build` 约 78 MB，可在目标服务器重新编译，不迁移。
- 需要迁移的源码、Git 元数据、实验、文档、小型产物预计约 100--150 MB。
- 当前工作树包含尚未提交的修改和未跟踪科研文档，迁移必须保留当前工作树，
  不能只在服务器重新 `git clone`。

计划迁移：

```text
README.md
AGENTS.md
validate_witwin.py
.git/
docs/
logs/
src/witwin-core/
src/witwin-channel/
apps/
capture/
pipelines/
schemas/
datasets/
workspace/project-docs/
```

明确排除：

```text
venv/
workspace/host_snapshot/
workspace/support/
src/witwin-channel/build/
**/__pycache__/
**/.pytest_cache/
```

`workspace/project-docs` 中的符号链接必须仅按清单复制其目标文件，不能全局跟随
符号链接，否则可能把整个 WSL OptiX 备份带入迁移包。

## 3. 目标服务器只读审计结果

- 系统：Ubuntu 22.04.5 LTS，`x86_64`。
- GPU：NVIDIA GeForce RTX 5090，32 GB，Compute Capability 12.0。
- 驱动：580.173.02。
- SSH 登录点的根文件系统是 overlay，推断当前 SSH 落点本身处于容器内。
- `/root/nfs` 是 `/dev/nvme0n1p9` 上 ext4 目录挂载，不是网络 NFS。
- `/root/nfs/chenzhf` 所在文件系统审计时约有 25 GB 可用空间。
- 目标目录当前已有 `bus`、`nerf2`、`sionna-main`，均不得修改。
- `/root/nfs/chenzhf/witwin` 当前不存在，无名称冲突。
- Miniconda 位于 `/root/miniconda`，已有多个其他项目环境，均不得修改。
- 系统已有 Python 3.10.12、GCC/G++ 11.4、CMake 3.22.1、Ninja、Git、Make
  和 pkg-config。
- 当前 PATH 中无 Docker、无 `nvcc`。
- `/usr/local/cuda` 指向 CUDA 12.9，但只发现配置及部分 CUDA 12.4 runtime
  软件包，没有可用 CUDA 编译器和完整开发工具链。
- 容器内未发现 `libnvoptix.so.1`。

服务器虽有其他环境包含 PyTorch，但没有可安全复用的完整 WiTwin 组合。尤其是
`RUBIK` 环境中的 PyTorch 2.10.0+cu128 属于其他项目，不应修改或建立跨项目依赖。

## 4. 拟建的项目隔离环境

拟在下列位置创建独立环境：

```text
/root/nfs/chenzhf/witwin/env
```

不安装系统 Python、不重新安装 Miniconda、不修改已有 Conda 环境。环境固定为：

| 组件 | 版本 |
|---|---:|
| Python | 3.12 |
| PyTorch | 2.10.0+cu128 |
| DrJit | 1.3.1 |
| RayD | 0.4.0 |
| NumPy | 2.4.1 |
| Matplotlib | 3.10.8 |
| tqdm | 4.67.1 |
| nanobind | 2.9.2 |
| scikit-build-core | 1.0.3 |
| WiTwin Core | 0.0.2 |
| WiTwin Channel | 0.1.0 |

源码版本固定为：

- Core：`897ee1cdee3b4f35fb0db0c153197f5ebfcce21f`
- Channel：`86ec9321e1d7e9288c53ddce3beb68631f92f12d`

当前 PyTorch 2.10.0+cu128 wheel 已确认包含 `sm_120`，适配 RTX 5090。

WiTwin Channel 的 CMake 项目显式启用 CUDA 语言并要求 `CUDAToolkit`，因此目标
环境还需要项目本地的 CUDA 12.8 编译器、CUDART 开发头文件和必要依赖。优先通过
独立 Conda 前缀安装最小 CUDA 编译组件，不向系统目录安装完整 CUDA Toolkit。

## 5. 空间预算与停止条件

| 内容 | 预计占用 |
|---|---:|
| 项目、Git 元数据与小型产物 | 0.1--0.2 GB |
| Python、PyTorch 与 Python CUDA 依赖 | 7--8 GB |
| CUDA 编译组件 | 1--3 GB |
| 原生扩展构建临时空间 | 1--2 GB |
| 预计最终占用 | 9--11 GB |
| 预计安装峰值 | 12--14 GB |

安装时禁用 pip 缓存，并在传输、依赖安装和编译前后检查剩余空间。可用空间低于
8 GB 时立即停止，不清理其他项目或共享 Conda 缓存来换取空间。

## 6. OptiX 前置条件

当前服务器容器可以访问 `libcuda.so.1`，但没有 `libnvoptix.so.1`。RayD 的完整
验证需要容器启动方注入 NVIDIA graphics driver capability，例如：

```text
NVIDIA_DRIVER_CAPABILITIES=compute,utility,graphics
```

或：

```text
NVIDIA_DRIVER_CAPABILITIES=all
```

标准 Linux 服务器应使用与宿主 NVIDIA 驱动匹配并由容器运行时注入的 OptiX
驱动库。不得复制当前 WSL workaround，也不得在未评估宿主容器启动配置前安装或
覆盖 NVIDIA 驱动库。

在 OptiX 未解决前，可以迁移文件并构建 Python/CUDA 环境，但 RayD、LOS、CIR、
CFR 的端到端验证预计会停在 OptiX 初始化。

## 7. 计划执行顺序

1. 再次确认目标目录不存在且空间满足安全线。
2. 创建唯一的新目录 `/root/nfs/chenzhf/witwin`，不触碰同级已有项目。
3. 生成带排除清单的源端迁移包和清单，保留未提交工作树内容。
4. 传输后核对文件数、总大小和 SHA-256 清单。
5. 在项目目录中创建独立 Conda 前缀及项目本地 CUDA 编译工具链。
6. 安装固定 Python 依赖和 editable Core/Channel 源码，限制编译并行度。
7. 运行 `pip check`、PyTorch/DrJit CUDA 探针和完整 `validate_witwin.py`。
8. 明确保留已知限制：当前组合的 `max_bounces > 0` 反射路径尚未通过验证。
9. 任务完成后，在用户确认下仅删除本次临时 SSH 公钥条目和本次生成的临时包。

## 8. 变更审批状态

截至本文日期，用户只授权了目标服务器只读审计和记录计划。尚未授权：

- 创建 `/root/nfs/chenzhf/witwin`；
- 传输项目文件；
- 创建 Conda 环境；
- 安装 Python/CUDA 依赖；
- 修改容器启动参数；
- 删除任何文件。


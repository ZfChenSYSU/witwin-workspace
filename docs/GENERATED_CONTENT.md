# WiTwin WSL 容器生成内容说明

生成日期：2026-07-14  
目标容器：`witwin-dev-20260714`  
最终镜像：`witwin-dev:20260714-final`

## 1. 任务结果

本容器根据 `E:\Docment\科研\科研\25春新进度\WiTwin使用说明.md` 创建，用于运行 WiTwin Core 与 `witwin-channel`。容器内已经完成以下工作：

- 安装 CUDA 12.8、CuDNN、Python、C/C++/CUDA 编译工具链。
- 创建独立 Python 虚拟环境 `/opt/witwin/venv`。
- 从官方源码安装 WiTwin Core 0.0.2。
- 从官方发布标签安装 `witwin-channel` 0.1.0，并在容器内编译其原生扩展。
- 安装并验证 PyTorch CUDA、Dr.Jit CUDA/LLVM、RayD 与 NVIDIA OptiX。
- 验证 deterministic radiomap。
- 验证 LOS path、CIR 与 CFR 公共接口。
- 保存可重复验证脚本和 JSON 验证报告。

## 2. 容器和硬件环境

- WSL 发行版：Ubuntu 24.04，WSL2。
- 基础镜像：`nvidia/cuda:12.8.1-cudnn-devel-ubuntu24.04`。
- 基础镜像摘要：`sha256:24c8e3581ea6330038b0d374920721983312627f8adbfcf390bdb4b399d280ed`。
- Python：3.12.3。
- GPU：NVIDIA GeForce RTX 4050 Laptop GPU。
- GPU Compute Capability：8.9。
- Windows/WSL NVIDIA 驱动报告版本：572.16。
- 容器共享内存：2 GiB。
- 容器重启策略：`unless-stopped`。
- NVIDIA 容器能力：`all`。
- OptiX 加载路径：`/usr/lib/x86_64-linux-gnu/libnvoptix.so.1`。

## 3. 已安装的主要系统组件

容器中安装了下列 Ubuntu 组件：

- `python3`、`python3-dev`、`python3-venv`、`python3-pip`。
- `git`、`git-lfs`、`ca-certificates`、`curl`、`wget`。
- `build-essential`、`cmake`、`ninja-build`、`pkg-config`。
- `libllvm18`、`libedit2`、`libbsd0`。

`libllvm18` 用于启用 Dr.Jit LLVM CPU 后端；主要 WiTwin 仿真仍使用 CUDA 后端。

## 4. Python 环境和固定版本

虚拟环境位置：

```text
/opt/witwin/venv
```

主要 Python 包：

| 包 | 版本 |
|---|---:|
| `witwin` | 0.0.2 |
| `witwin-channel` | 0.1.0 |
| `torch` | 2.10.0+cu128 |
| `drjit` | 1.3.1 |
| `rayd` | 0.4.0 |
| `numpy` | 2.4.1 |
| `matplotlib` | 3.10.8 |
| `tqdm` | 4.67.1 |
| `nanobind` | 2.9.2 |
| `scikit-build-core` | 1.0.3 |
| `pytest` | 9.1.1 |

PyTorch 来自官方 CUDA 12.8 索引：

```bash
python -m pip install "torch==2.10.0+cu128" \
  --index-url https://download.pytorch.org/whl/cu128
```

## 5. WiTwin 源码

源码目录：

```text
/opt/witwin/src/witwin-core
/opt/witwin/src/witwin-channel
```

固定版本：

- WiTwin Core 提交：`897ee1cdee3b4f35fb0db0c153197f5ebfcce21f`。
- WiTwin Channel 标签：`witwin-channel-v0.1.0`。
- WiTwin Channel 提交：`86ec9321e1d7e9288c53ddce3beb68631f92f12d`。

安装方式：

```bash
/opt/witwin/venv/bin/python -m pip install \
  --no-build-isolation -e /opt/witwin/src/witwin-core

CMAKE_BUILD_PARALLEL_LEVEL=2 MAX_JOBS=2 \
/opt/witwin/venv/bin/python -m pip install \
  --no-build-isolation --no-deps -e /opt/witwin/src/witwin-channel
```

## 6. 版本选择说明

执行时发现官方仓库存在以下版本不一致：

1. `witwin-core` 主分支仍声明 0.0.2，而 `witwin-channel` 主分支已声明 0.3.0 并要求 `witwin>=0.3,<0.4`，两者不能组成无冲突环境。
2. 官方 `witwin-channel` 0.1.0 发布版与 Core 0.0.2 的元数据兼容，因此本容器固定使用这组发布版本。
3. Channel 0.1.0 未在依赖元数据中声明 RayD，但运行时直接导入 `rayd`。
4. `rayd-drjit` 0.6.0 不提供 Channel 0.1.0 所需的 `rayd.Scene` API。
5. RayD 0.5.0 在该 Dr.Jit 1.3.1 组合中出现原生符号加载错误。
6. RayD 0.4.0 可以正常加载，并已通过 deterministic 和 LOS path/CIR/CFR 验证。

因此，本容器选择可运行、经过验证的发布组合，而未强制安装元数据互相冲突的主分支。

## 7. WSL2 OptiX workaround

RayD 需要 NVIDIA OptiX。Windows 驱动最初只向 WSL 提供了一个不完整的 72,616 字节 OptiX shim，缺少 PTX JIT、RTCore、GPUComp 和 `nvoptix.bin`，导致：

```text
RuntimeError: Could not initialize OptiX!
```

按照 Mitsuba 的 WSL2 OptiX 官方说明执行了下列操作：

1. 从 NVIDIA 官方站点下载 `NVIDIA-Linux-x86_64-570.86.16.run`。
2. 使用 NVIDIA 官方 SHA256 文件验证下载包。
3. 只执行 `-x` 解包，没有在 WSL 安装 Linux NVIDIA 驱动。
4. 提取并复制以下文件到 `C:\Windows\System32\lxss\lib`：

   - `libnvidia-gpucomp.so.570.86.16`
   - `libnvidia-ptxjitcompiler.so.1`
   - `libnvidia-rtcore.so.570.86.16`
   - `libnvoptix.so.1`
   - `nvoptix.bin`

5. 临时取得目标目录权限，复制后恢复目录及文件的 `TrustedInstaller` 所有权，并移除临时 Administrators ACE。
6. 在 WSL 中创建链接：

```text
/usr/lib/x86_64-linux-gnu/libcuda.so -> /usr/lib/wsl/lib/libcuda.so
```

7. 将相同五个文件放入容器的 `/usr/lib/x86_64-linux-gnu/`。

Windows 端安装备份：

```text
E:\Docment\科研\科研\25春新进度\.witwin-optix-workaround\lxss-lib-backup-20260714-165259
```

Windows 端安装结果：

```text
E:\Docment\科研\科研\25春新进度\.witwin-optix-workaround\install-result.json
```

如果将来升级 Windows NVIDIA 驱动，WSL 的 `lxss\lib` 可能被驱动安装器替换，应重新运行验证脚本确认 OptiX。

## 8. 容器内生成的文件

```text
/opt/witwin/docs/WiTwin使用说明.md
/opt/witwin/docs/GENERATED_CONTENT.md
/opt/witwin/validate_witwin.py
/opt/witwin/logs/validation.json
/opt/witwin/src/witwin-core/
/opt/witwin/src/witwin-channel/
/opt/witwin/venv/
```

- `WiTwin使用说明.md`：任务输入文档的容器内副本。
- `GENERATED_CONTENT.md`：本文档。
- `validate_witwin.py`：可重复的端到端验证程序。
- `validation.json`：验证程序最近一次运行结果。

## 9. 验证结果

### 9.1 Python、GPU 和 Dr.Jit

- `pip check`：无损坏依赖。
- `torch.cuda.is_available()`：`true`。
- PyTorch CUDA build：12.8。
- PyTorch GPU 运算探针：成功，结果 30.0。
- Dr.Jit LLVM 后端：可用。
- Dr.Jit CUDA 后端：可用。
- RayD `Scene`：可构造并可初始化 OptiX。

### 9.2 Deterministic radiomap

使用单墙、单发射端和 4 x 4 ReceiverGrid：

```json
{
  "shape": [1, 4, 4],
  "finite": true,
  "min": 0.0,
  "max": 7.369044760707766e-05
}
```

### 9.3 LOS path、CIR 和 CFR

使用 `max_bounces=0` 的 LOS 场景：

```json
{
  "cir_coeff_shape": [1, 1, 1, 1, 8, 1],
  "cir_delay_shape": [1, 1, 1, 1, 8],
  "cfr_shape": [1, 1, 1, 1, 1, 8],
  "cfr_finite": true,
  "cfr_device": "cuda:0"
}
```

## 10. 使用方法

在 WSL 中查看容器：

```bash
docker ps --filter name=witwin-dev-20260714
```

进入容器：

```bash
docker exec -it witwin-dev-20260714 bash
```

启用虚拟环境：

```bash
source /opt/witwin/venv/bin/activate
```

重新运行完整验证：

```bash
python /opt/witwin/validate_witwin.py
```

查看保存的验证结果：

```bash
cat /opt/witwin/logs/validation.json
```

从 Windows PowerShell 调用：

```powershell
wsl -d Ubuntu-24.04 -- docker exec \
  witwin-dev-20260714 \
  /opt/witwin/venv/bin/python /opt/witwin/validate_witwin.py
```

## 11. 已知限制

- 当前固定组合已验证 deterministic solver 和 LOS path/CIR/CFR。
- Channel 0.1.0 的反射 path EPC 在 RayD 0.4.0 下不可用；`max_bounces>0` 的反射 path solve 尚未通过。
- 不应将本环境直接升级到 Channel 主分支 0.3.0，除非官方同时发布兼容的 Core `>=0.3`。
- WiTwin Channel 是 early release，API 和依赖仍可能变化。
- WSL2 中的 OptiX 属于 workaround，官方提示其并非正式支持配置，且性能数据不应代表原生 Linux 性能。
- 本任务未安装 `witwin-maxwell`，因为输入说明明确建议第一阶段优先使用 `witwin-channel`，且用户要求的范围是 Core 与 Channel。

## 12. 安全与恢复

OptiX 覆盖前的文件已备份。若需要恢复，先停止 Docker Desktop 并执行 `wsl --shutdown`，再以管理员权限从备份目录恢复原文件。恢复后应再次执行 `wsl --shutdown`。

不要在 WSL 中运行下载的 Linux NVIDIA 驱动安装器；本任务只使用了其解包内容。

# 无 LiDAR SLAM 服务器环境实际安装记录

日期：2026-08-05
目标目录：`/root/nfs/chenzhf/witwin`
文档仓库提交：`f3f89157704adad497cbc8c6972244055bd3f15e`

## 范围

本次仅部署 iPhone RGB/ARKit → COLMAP 4.0.4 → MVS/网格处理主线，没有安装
WiTwin、RayD、DrJit、PyTorch、Docker、ROS、LiDAR/TSDF 专用环境或测试数据。

## 实际环境

- Conda 前缀：`/root/nfs/chenzhf/witwin/env`
- Python：3.12.13
- CUDA 编译器：12.8.93（CUDA 12.8）
- CUDA 目标：`sm_120` 可由 NVCC 识别；COLMAP 4.0.4 对 Blackwell 的 MVS CUDA
  目标按其源码 workaround 使用 `90-virtual` PTX，以规避 NVCC Blackwell bug。
- GPU：RTX 5090，Compute Capability 12.0，驱动 580.173.02

主要 Conda 组件：

- `cuda-compiler 12.8.1`
- `cuda-cudart-dev 12.8.90`
- `cuda-nvrtc-dev 12.8.93`
- `libcurand-dev 10.3.9.90`
- `libboost-devel 1.88.0`（Conda Forge 的实际开发包名；不是不存在的
  `boost=1.88` 元包）
- Eigen 3.4.0、OpenImageIO 2.5.18.0、Metis 5.1.0、glog 0.7.1、Ceres 2.2.0、
  SuiteSparse 7.10.1、GLEW、OpenGL/EGL、SQLite、Curl、OpenSSL、fmt 12.2.0

Python 包：

- NumPy 2.2.6、SciPy 1.16.1、pandas 2.3.1、PyYAML 6.0.2、Pillow 11.3.0
- opencv-python-headless 4.12.0、Open3D 0.19.0、trimesh 4.7.1
- scikit-learn 1.7.1、pycolmap 4.0.4

COLMAP：

- 源码：`tools/src/colmap-4.0.4`
- 官方仓库：`https://github.com/colmap/colmap.git`
- 标签：`4.0.4`
- 实际提交：`9c23f6942fe69962e06030905e77067c8673382f`
- 构建目录：`tools/build/colmap-4.0.4`
- 安装目录：`tools/colmap-4.0.4`
- 配置：GUI OFF、Tests OFF、CGAL OFF、Shared ON、CUDA ON、ONNX ON、
  `CMAKE_CUDA_ARCHITECTURES=120`，Ninja 并行度 2
- ONNX Runtime：1.24.1，由 COLMAP 配置阶段在项目构建树中获取并安装到本地前缀

## 命令与运行约束

安装命令的 HOME、缓存、临时目录、Conda 前缀和日志均限定在项目目录。构建使用
项目环境中的 CMake/Ninja/NVCC 和 Conda GCC 14.4；没有调用 apt、sudo 或修改系统目录。

COLMAP 是 shared build，运行时需保留项目库路径：

```bash
ROOT=/root/nfs/chenzhf/witwin
export PATH="$ROOT/env/bin:$ROOT/tools/colmap-4.0.4/bin:$PATH"
export LD_LIBRARY_PATH="$ROOT/env/lib:$ROOT/tools/colmap-4.0.4/lib:$ROOT/tools/colmap-4.0.4/thirdparty"
colmap -h
```

## 验证结果

- Python 全部目标包导入成功。
- `pip check`：`No broken requirements found.`
- NVCC 输出 CUDA 12.8.93，帮助中包含 `compute_120` 和 `sm_120`。
- `colmap -h` 包含：`global_mapper`、`pose_prior_mapper`、
  `patch_match_stereo`、`stereo_fusion`、`mesh_simplifier`、
  `model_orientation_aligner`。
- `ldd` 在上述项目 `LD_LIBRARY_PATH` 下未发现 `not found`；COLMAP、ONNX Runtime、
  CUDA、Boost、OpenImageIO、Ceres 和 glog 均解析到项目环境/安装前缀。
- 未下载测试数据，未运行稀疏/稠密重建。

## 空间占用（最终记录）

- Conda 环境：约 4.7 GB
- COLMAP 源码：约 48 MB
- COLMAP 构建树：约 1.0 GB
- COLMAP 安装：约 392 MB
- Conda 包缓存：约 1.9 GB
- `/root/nfs` 剩余：约 18 GB；未触发低于 8 GB 的停止阈值

## 中断与恢复

1. 初次 Conda 创建因 conda-forge `noarch/repodata.json` HTTP 000 失败，未创建环境。
2. `current_repodata.json` 重试因不含 `boost=1.88` 失败；离线缓存求解确认应使用
   `libboost-devel=1.88`。
3. 使用项目缓存索引和 `libboost-devel=1.88` 成功创建环境。
4. 首轮 pip 在 Open3D 大 wheel 下载阶段中断，未提交包；随后拆分为基础包和 Open3D
   两个连续事务，均成功。
5. 首轮 CMake 因 OpenImageIO 配置缺少 `fmt` 停止；补装项目环境 `fmt` 后原位重新
   配置成功。没有删除或清理此前构建目录、源码、缓存或日志。

## 日志与清单

完整日志位于 `/root/nfs/chenzhf/witwin/logs`，包括 Conda 创建/重试、pip 安装、
COLMAP 克隆/配置/构建/安装、验证、`conda-explicit-2026-08-05.txt`、
`conda-list-2026-08-05.txt` 和 `pip-freeze-2026-08-05.txt`。

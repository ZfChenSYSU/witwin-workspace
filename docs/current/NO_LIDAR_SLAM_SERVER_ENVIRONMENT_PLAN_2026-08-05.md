# 无 LiDAR SLAM 空间建模服务器环境计划

日期：2026-08-05  
目标服务器：`root@192.168.3.2:8048`  
计划根目录：`/root/nfs/chenzhf/witwin`  
状态：**仅完成调研、只读审计与方案设计，尚未在目标服务器创建目录、传输数据、克隆源码或安装环境。**

WiTwin 本体的迁移与安装方案单独记录在
[`WITWIN_SERVER_MIGRATION_PLAN_2026-08-05.md`](WITWIN_SERVER_MIGRATION_PLAN_2026-08-05.md)，
本文只讨论 iPhone 11 Pro 无 LiDAR 条件下的 SLAM/SfM/MVS 空间建模环境。

## 1. 方法选择

依据
[`IPHONE_SLAM_SPATIAL_MODELING_RESEARCH_2026-07-29.md`](../reference/research/IPHONE_SLAM_SPATIAL_MODELING_RESEARCH_2026-07-29.md)，
当前无 LiDAR 主方法固定为：

```text
ARKit 后置 RGB、逐帧内参、米制位姿和 CoreMotion
  -> 清晰关键帧与质量筛选
  -> COLMAP 特征提取和匹配
  -> global_mapper / mapper / pose_prior_mapper 对照
  -> 全局 Bundle Adjustment
  -> 与 ARKit 轨迹进行 RANSAC + Sim(3) 米制对齐
  -> PatchMatch MVS 与 stereo_fusion
  -> 网格化、平面拟合、Manhattan 正则化、补洞和简化
  -> WiTwin 可用的闭合低多边形房间网格与材料区域
```

首轮只安装并验证这条主线。ORB-SLAM3 是后续轨迹 baseline；MASt3R-SLAM、
VGGT、MVSFormer++、DROID-SLAM 和 VINGS-Mono 是 challenger 或可选 baseline，
均不进入首轮环境。

## 2. COLMAP 版本决策

固定使用 **COLMAP 4.0.4**，不使用 Ubuntu 22.04 仓库中的旧版本。

原因：

- COLMAP 4.0 正式集成 GLOMAP，并提供 `global_mapper`。
- COLMAP 4.0 提供 `pose_prior_mapper`、PatchMatch MVS、网格简化和
  Manhattan orientation alignment 等本项目需要的命令。
- COLMAP 4.0 已内置 ALIKED 特征和用于 SIFT/ALIKED 的 LightGlue ONNX 匹配，
  主线不必另外安装 standalone LightGlue、HLoc 或第二套 PyTorch。
- 目标 GPU 是 RTX 5090/Blackwell。COLMAP 4.0.3 修复了 Blackwell
  `sm_100+` 上 PatchMatch 输出为空的问题，因此不得使用 4.0.0--4.0.2；
  选择当前修复版本 4.0.4。

官方依据：

- <https://github.com/colmap/colmap/releases/tag/4.0.4>
- <https://colmap.github.io/install.html>
- <https://colmap.github.io/cli.html>
- <https://colmap.github.io/faq.html>

## 3. 特征与匹配策略

首轮保留两级策略：

1. 可解释基线：COLMAP CUDA SIFT + sequential/exhaustive matching。
2. 弱纹理增强：COLMAP 内置 ALIKED + LightGlue ONNX。

只有当内置前端不能满足实验需求时，才评估 standalone LightGlue/HLoc。官方
standalone LightGlue 依赖 PyTorch、Torchvision、Kornia、OpenCV 和模型权重；
HLoc 还需要 HDF5 和 PyCOLMAP。首轮安装它们会与 COLMAP 4 的内置能力重复。

相关官方资料：

- <https://github.com/cvg/LightGlue>
- <https://github.com/cvg/Hierarchical-Localization>

## 4. 服务器只读审计结果

- Ubuntu 22.04.5 LTS，`x86_64`。
- NVIDIA GeForce RTX 5090，32 GB，Compute Capability 12.0。
- NVIDIA 驱动 580.173.02。
- SSH 落点根文件系统为 overlay，推断登录点本身处于容器中。
- `/root/nfs` 是 ext4 目录挂载，不是网络 NFS。
- 审计时 `/root/nfs/chenzhf` 所在文件系统约有 25 GB 可用空间。
- 已有 `bus`、`nerf2`、`sionna-main`，本文方案不得修改这些目录。
- `/root/nfs/chenzhf/witwin` 当前不存在，无名称冲突。
- `/root/miniconda` 已安装，包含多个其他项目环境，均不得修改。
- 当前无 `colmap`、无 PATH 可见的 `nvcc`。

## 5. 可以直接复用的环境

无需重复安装：

- NVIDIA 驱动和 RTX 5090；
- `/root/miniconda`；
- GCC/G++ 11.4；
- CMake 3.22.1、Ninja、Git、Make、pkg-config；
- FFmpeg/ffprobe 4.4.2，用于视频探针和抽帧；
- rsync，用于后续受控同步；
- 系统 Eigen 3.4 开发头文件；
- Miniconda 包缓存中已有的 CUDA compiler 12.8.1、`cuda-nvcc` 12.8、
  Ceres 2.2、Eigen、glog、Metis 和 SuiteSparse。

其他项目 Conda 环境中的包只用于兼容性审计，不作为本项目生产依赖。尤其不得
修改或依赖 `RUBIK`、`BAID_5090`、`sionna_env_*`，即使其中存在相同版本的
PyTorch、Open3D、Trimesh 或 NumPy。

## 6. 需要安装的 C++/CUDA 环境

COLMAP 4.0.4 计划以 headless、CUDA、ONNX 方式从固定标签构建，并安装到：

```text
/root/nfs/chenzhf/witwin/tools/colmap-4.0.4
```

依赖安装在项目专用 Conda 前缀，不写入 `/usr/local`，包括：

- CUDA compiler/NVCC 12.8；
- CUDART、NVRTC、curand 开发组件；
- Boost graph/program_options；
- Eigen；
- OpenImageIO；
- Metis、glog、SQLite；
- Ceres Solver、SuiteSparse/CHOLMOD；
- OpenGL/GLEW 构建组件；
- Curl/OpenSSL；
- ONNX Runtime 1.24.1，由 COLMAP 4.0.4 官方 CMake 配置按固定哈希获取。

节省空间的首轮构建配置：

```text
GUI_ENABLED=OFF
TESTS_ENABLED=OFF
CGAL_ENABLED=OFF
BUILD_SHARED_LIBS=ON
CUDA_ENABLED=ON
ONNX_ENABLED=ON
CMAKE_CUDA_ARCHITECTURES=120
```

关闭 CGAL 后，首轮采用 Poisson mesher、COLMAP mesh simplifier 和 Python
平面正则化，不构建 Delaunay/advancing-front 可选路径。若后续实验确有必要，
再单独评估 `cgal-cpp`，不预装 Qt、GTest 或完整 GUI 栈。

CUDA 12.8 同时满足当前 WiTwin/PyTorch cu128 组合和 RTX 5090 `sm_120` 编译，
因此不另建 CUDA 12.9 工具链。

## 7. 需要安装的 Python 几何工具

为节省空间，建议与 WiTwin 计划共用项目 Conda 前缀：

```text
/root/nfs/chenzhf/witwin/env
```

SLAM/重建主线新增：

| 包 | 版本或约束 | 用途 |
|---|---:|---|
| PyCOLMAP | 4.0.4 | 数据库、相机模型、轨迹和模型读写 |
| OpenCV headless | 安装时固定解析版本 | 抽帧质量、模糊度和图像处理 |
| SciPy | 与 NumPy 2.4.1 兼容 | Sim(3)、旋转、优化和统计 |
| pandas | 安装时固定解析版本 | 帧清单、时间戳和指标表 |
| PyYAML | 安装时固定解析版本 | 流水线配置 |
| Pillow | 安装时固定解析版本 | 图像元数据和格式检查 |
| Open3D | 0.19.0 | 点云清理、RANSAC 平面和网格检查 |
| trimesh | 4.x 固定小版本 | 拓扑、法向、闭合性和格式导出 |
| scikit-learn | 安装时固定解析版本 | 聚类与稳健几何辅助 |

Open3D 0.19.0 官方支持 Python 3.12 和 NumPy 2，适合与 WiTwin 固定的
Python 3.12/NumPy 2.4.1 共同验证：
<https://github.com/isl-org/Open3D/releases/tag/v0.19.0>。

COLMAP 4 自带 `mesh_simplifier`，首轮不安装 PyMeshLab。Sim(3) 对齐可以由
PyCOLMAP、NumPy 和 SciPy 完成，不要求 ROS。

## 8. 首轮明确不安装

- Docker；
- ROS/ROS 2；
- ORB-SLAM3、VINS-Fusion；
- MASt3R-SLAM、VGGT、DROID-SLAM、VINGS-Mono；
- MVSFormer++；
- standalone LightGlue、HLoc；
- RTAB-Map、RoomPlan 和 LiDAR/TSDF 专用环境；
- COLMAP GUI、Qt、GTest；
- MVSNet 系列训练环境；
- PyMeshLab。

## 9. 空间预算和数据边界

在与 WiTwin 共用 CUDA/Python 前缀的前提下：

| 内容 | 预计占用 |
|---|---:|
| SLAM Python/几何工具 | 0.8--1.5 GB |
| COLMAP 持久依赖和安装 | 1.5--3 GB |
| COLMAP 源码与临时构建树 | 1--3 GB |
| SLAM 主线持久新增合计 | 2--4 GB |

完成安装并验证后，只能在用户确认下删除本次生成的构建树和项目本地安装缓存。

环境可以在审计时约 25 GB 的剩余空间中构建，但高分辨率关键帧、PatchMatch
深度/法向图、稠密点云和网格可能占用数 GB 到数十 GB。原始视频和完整稠密工作
区不应长期放在当前系统盘。首轮只运行一个受控的小型 session，并限制关键帧数
和 `PatchMatchStereo.max_image_size`；正式数据需要更大容量的数据盘或用户指定的
外部存储。

## 10. 验证门槛

获得安装授权后，应依次验证：

1. `colmap -h` 中存在 `global_mapper`、`pose_prior_mapper`、
   `patch_match_stereo`、`mesh_simplifier` 和 `model_orientation_aligner`。
2. CUDA SIFT 在 RTX 5090 上完成小型图像集的提取和匹配。
3. ALIKED + LightGlue ONNX 在同一图像集上运行成功。
4. `global_mapper`、`mapper` 和 `pose_prior_mapper` 都产生非空稀疏模型。
5. PatchMatch 产生非空深度图，防止回归 Blackwell 空结果问题。
6. `stereo_fusion`、Poisson mesher 和 mesh simplifier 产生非空产物。
7. PyCOLMAP、Open3D 和 Trimesh 能读取结果并完成 Sim(3)、平面与网格质量探针。
8. 所有产物只写入项目或数据专用目录，不写入 `bus`、`nerf2`、
   `sionna-main`。

## 11. 审批状态

本文仅为调研与安装计划。尚未授权在目标服务器：

- 克隆或构建 COLMAP；
- 创建项目 Conda 前缀；
- 安装任何 C++、CUDA 或 Python 包；
- 下载 ONNX 模型或运行时；
- 传输 iPhone session；
- 运行稀疏或稠密重建；
- 删除构建缓存或重建中间产物。


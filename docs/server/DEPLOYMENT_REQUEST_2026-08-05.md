请在当前目标服务器上继续“无 LiDAR SLAM 空间建模环境”的部署。请全程使用中文汇报，并严格遵守以下安全边界。

一.安全边界，放在后面

二、从 GitHub 获取文档

需要拉取：

- 仓库：https://github.com/ZfChenSYSU/witwin-workspace.git
- 分支：agent/no-lidar-slam-server-plan
- 固定提交：f3f89157704adad497cbc8c6972244055bd3f15e

仓库必须放到新目录：

/root/nfs/chenzhf/witwin-workspace

不要把仓库克隆到已经存在的 `/root/nfs/chenzhf/witwin` 中。

如果 `/root/nfs/chenzhf/witwin-workspace` 不存在，执行等价于：

git clone 
  --depth 1 
  --single-branch 
  --branch agent/no-lidar-slam-server-plan 
  https://github.com/ZfChenSYSU/witwin-workspace.git 
  /root/nfs/chenzhf/witwin-workspace

克隆后确认 HEAD 必须是：

f3f89157704adad497cbc8c6972244055bd3f15e

如果仓库目录已经存在，不要覆盖、reset、clean 或删除。先检查 Git 状态、remote 和当前提交；若存在本地修改或来源不一致，停止并向我报告。

三、必须阅读的文档

进入仓库后，依次完整阅读：

1. /root/nfs/chenzhf/witwin-workspace/AGENTS.md
2. /root/nfs/chenzhf/witwin-workspace/docs/SESSION_CONTEXT_2026-07-15.md
3. /root/nfs/chenzhf/witwin-workspace/docs/reference/research/IPHONE_SLAM_SPATIAL_MODELING_RESEARCH_2026-07-29.md
4. /root/nfs/chenzhf/witwin-workspace/docs/current/NO_LIDAR_SLAM_SERVER_ENVIRONMENT_PLAN_2026-08-05.md
5. /root/nfs/chenzhf/witwin-workspace/docs/current/WITWIN_SERVER_MIGRATION_PLAN_2026-08-05.md

本次安装以第 4 份“无 LiDAR SLAM 环境计划”为主要依据，以第 3 份研究文档确认技术路线。第 5 份 WiTwin 文档只用于理解目录、安全边界和可复用环境，本次不要安装 WiTwin、RayD、DrJit 或完整 PyTorch/WiTwin 环境。

文档里的旧“审批状态”已被本提示词更新：我现在授权你仅在 `/root/nfs/chenzhf/witwin` 内安装无 LiDAR SLAM 主方法所需环境，但没有授权任何系统级修改和删除操作。

四、安装前只读检查

先执行只读检查并简要汇报：

- 操作系统、GPU、NVIDIA 驱动和 Compute Capability
- `/root/nfs/chenzhf` 剩余空间
- `/root/miniconda/bin/conda` 是否可用
- GCC/G++、CMake、Ninja、Git、Make、pkg-config、FFmpeg
- `/root/nfs/chenzhf/witwin` 当前内容和占用
- 是否存在中断的 Conda/COLMAP 安装进程
- `/root/nfs/chenzhf/witwin/env` 是否完整
- 之前的安装日志和状态文件
- 当前是否已经存在 colmap、nvcc、PyCOLMAP、Open3D

不要扫描或统计其他项目的内部内容，只确认受保护目录存在即可。

安装开始前至少保留 15 GB 可用空间；安装过程中若低于 8 GB，立即停止，不得通过清理其他项目、共享缓存或系统文件释放空间。

五、本次只安装无 LiDAR 主方法环境

主线固定为：

iPhone RGB/ARKit 数据
→ COLMAP 4.0.4 特征与匹配
→ global_mapper、mapper、pose_prior_mapper
→ Bundle Adjustment
→ Sim(3) 米制对齐
→ PatchMatch MVS
→ stereo_fusion
→ Poisson 网格、简化、平面和 Manhattan 处理

本次需要：

1. 项目独立 Conda 环境：
   /root/nfs/chenzhf/witwin/env
2. Python 3.12。
3. 项目本地 CUDA 12.8 编译组件，用于 RTX 5090/sm_120：

   - cuda-compiler 12.8.1
   - cuda-cudart-dev 12.8.90
   - cuda-nvrtc-dev 12.8.93
   - libcurand-dev 10.3.9.90
4. COLMAP 4.0.4 的 C++ 依赖：

   - Boost 1.88 开发组件
   - Eigen
   - OpenImageIO 2.5.18
   - Metis
   - glog
   - Ceres Solver 2.2
   - SuiteSparse
   - GLEW/OpenGL/EGL 开发组件
   - SQLite、Curl、OpenSSL
5. Python 几何工具：

   - pycolmap 4.0.4
   - opencv-python-headless
   - scipy
   - pandas
   - PyYAML
   - Pillow
   - open3d 0.19.0
   - trimesh 4.x 的固定小版本
   - scikit-learn
   - numpy 等依赖必须选择相互兼容的固定版本
6. 从官方仓库固定克隆 COLMAP 4.0.4：
   https://github.com/colmap/colmap.git

源码、构建和安装位置分别为：

- /root/nfs/chenzhf/witwin/tools/src/colmap-4.0.4
- /root/nfs/chenzhf/witwin/tools/build/colmap-4.0.4
- /root/nfs/chenzhf/witwin/tools/colmap-4.0.4

COLMAP 构建配置：

- GUI_ENABLED=OFF
- TESTS_ENABLED=OFF
- CGAL_ENABLED=OFF
- BUILD_SHARED_LIBS=ON
- CUDA_ENABLED=ON
- ONNX_ENABLED=ON
- CMAKE_CUDA_ARCHITECTURES=120

限制编译并行度为 2，避免占用过多内存和磁盘。

七、明确不安装

不要安装：

- Docker
- ROS/ROS 2
- WiTwin Core/Channel
- RayD、DrJit、OptiX
- ORB-SLAM3、VINS-Fusion
- MASt3R-SLAM、VGGT、DROID-SLAM、VINGS-Mono
- MVSFormer++
- standalone LightGlue 或 HLoc
- COLMAP GUI、Qt、GTest
- PyMeshLab
- 训练环境或大型模型
- 项目数据集、视频、稠密重建数据

COLMAP 4.0.4 内置 ALIKED 和 LightGlue ONNX，首轮优先复用内置功能。

八、中断环境的处理原则

之前可能有一次中断的 Conda create，目标为：

/root/nfs/chenzhf/witwin/env

先判断环境是否已完整完成：

- 检查 conda-meta/history
- 检查 Python、NVCC 和主要依赖
- 检查相关日志
- 运行 conda list 或 conda doctor 类只读检查

如果能够安全续装，就在同一前缀内继续；如果必须删除或整体重建环境，不要直接删除，先向我报告并等待确认。

九、验证要求

安装完成后验证：

1. Python 3.12 和所有 Python 包可以导入。
2. `pip check` 无依赖冲突。
3. NVCC 为项目环境中的 CUDA 12.8，能识别 sm_120。
4. COLMAP 版本为 4.0.4。
5. `colmap -h` 包含：
   - global_mapper
   - pose_prior_mapper
   - patch_match_stereo
   - stereo_fusion
   - mesh_simplifier
   - model_orientation_aligner
6. 确认 COLMAP 链接到项目环境中的依赖，没有写入或依赖其他项目环境。
7. 记录最终磁盘占用和剩余空间。
8. 不下载测试数据，也不运行大规模重建；只进行不产生大型数据的环境探针。

十、过程记录

将以下内容写入：

/root/nfs/chenzhf/witwin/logs

包括：

- Conda 安装日志
- pip 安装日志
- COLMAP 配置日志
- COLMAP 构建日志
- 验证日志
- conda explicit 导出
- pip freeze
- 最终版本清单

另在仓库中新增一份实际安装记录：

/root/nfs/chenzhf/witwin-workspace/docs/current/NO_LIDAR_SLAM_SERVER_INSTALL_RECORD_2026-08-05.md

记录实际安装版本、命令、空间占用、验证结果、中断与恢复情况，但暂时不要提交或推送 Git，等待我确认。

请先完成 Git 拉取、文档阅读、只读预检和中断环境检查，然后向我报告结果。只要后续操作完全位于上述允许目录且不涉及删除，可以继续安装；一旦需要删除、覆盖、修改系统或写入允许目录之外，必须暂停并向我确认。v

一、文件写入与系统安全边界

1. 持久性写入白名单

只允许在以下目录内创建、修改、移动或删除文件：

- /root/nfs/chenzhf/witwin-workspace
- /root/nfs/chenzhf/witwin

除此之外的任何持久性写入都没有预先授权。

2. 允许的只读操作

允许只读访问和调用服务器已有资源，包括：

- /root/miniconda/bin/conda
- 系统编译器、CMake、Ninja、Git、FFmpeg
- /usr、/usr/local、/lib、/opt 下的已有程序和动态库
- NVIDIA 驱动、libcuda、GPU 设备
- /proc、/sys 中的硬件和进程信息
- Conda 已有环境的名称和版本信息

只读访问不代表可以修改这些位置。

3. 目录外修改必须单独确认

如果后续发现必须在写入白名单之外执行任何持久性修改，例如：

- apt、dpkg、sudo 或系统级软件安装
- 修改 /usr、/usr/local、/etc、/opt
- 修改 /root/.conda、/root/.config、/root/.cache、/root/.local
- 修改 /root/miniconda 或任何已有 Conda 环境
- 修改 NVIDIA 驱动、CUDA 符号链接或动态链接器配置
- 写入系统 Python
- 修改代理、SSH、Git 全局配置或容器配置
- 创建 systemd 服务、环境启动脚本或全局 PATH
- 修改 chenzhf 之外的项目和用户文件

必须立即暂停，并先向我提供：

1. 准备修改的精确路径；
2. 准备执行的完整命令；
3. 为什么无法在白名单目录中完成；
4. 对其他项目和用户的潜在影响；
5. 所需磁盘空间；
6. 回退或恢复方法；
7. 是否存在完全位于白名单目录内的替代方案。

只有收到我的明确文字确认后才能执行。不得把我对某一个路径的授权扩大到其他路径。

4. 运行时伪文件和临时资源

程序正常运行时可以只读访问 `/proc`、`/sys`、`/dev`，并使用 GPU 设备。

由内核或驱动管理的进程状态、设备通信和共享内存不视为持久性文件修改，但不得主动在这些位置保存项目数据、安装文件或配置。

所有可控制的临时文件仍必须写入：

/root/nfs/chenzhf/witwin/.tmp

5. 环境变量隔离

执行 Conda、pip、Python、CMake 或 COLMAP 前，统一设置：

ROOT=/root/nfs/chenzhf/witwin
HOME=$ROOT/.home
TMPDIR=$ROOT/.tmp
CONDA_PKGS_DIRS=$ROOT/.cache/conda-pkgs
CONDA_ENVS_PATH=$ROOT/.conda/envs
XDG_CACHE_HOME=$ROOT/.cache/xdg
XDG_CONFIG_HOME=$ROOT/.config
XDG_STATE_HOME=$ROOT/.local/state
XDG_DATA_HOME=$ROOT/.local/share
PIP_CACHE_DIR=$ROOT/.cache/pip
CUDA_CACHE_PATH=$ROOT/.cache/cuda
MPLCONFIGDIR=$ROOT/.config/matplotlib
PYTHONUSERBASE=$ROOT/.local

创建以上目录时也只能在 `$ROOT` 内操作。

pip 优先使用 `--no-cache-dir`，不得执行 `pip install --user`，不得向系统 Python 或其他 Conda 环境安装包。

6. 执行前检查

在执行每一条安装或构建命令前，检查其：

- 安装前缀；
- 缓存目录；
- 临时目录；
- HOME 和 XDG 目录；
- 是否可能调用 apt、sudo 或写入系统位置。

如果无法确认写入范围，先停止并询问我，不要用试运行来碰运气。

7. 禁止清理

即使文件位于 `/root/nfs/chenzhf/witwin` 内，也不得自行删除此前中断安装留下的：

- Conda 环境；
- Conda 包缓存；
- 构建目录；
- 源码；
- 安装日志。

如果需要删除、覆盖或整体重建，先列出具体目标、占用空间和恢复方案，等待我确认。

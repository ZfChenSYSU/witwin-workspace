# iPhone Session 上服务器建模：差距分析与下一步执行方案

日期：2026-08-06
适用服务器：`root@192.168.3.2:8048`
Git 工程目录：`/root/nfs/chenzhf/witwin/repository`
运行时目录：`/root/nfs/chenzhf/witwin`

## 1. 文档目的与结论

本文回答三个问题：

1. iPhone 当前采集结果距离“上传服务器后自动建模”还差什么；
2. 哪些工作必须在服务器端实现，哪些必须在 iPhone 端实现；
3. 下一步按什么顺序推进，才能尽快得到第一个可验证的米制房间模型。

本文不替代现有状态文档。当前能力边界仍以
[`COLMAP_CAPABILITY_BOUNDARY_2026-08-06.md`](COLMAP_CAPABILITY_BOUNDARY_2026-08-06.md)、
[`IPHONE_SESSION_IMPORT_REQUIREMENTS_2026-08-06.md`](IPHONE_SESSION_IMPORT_REQUIREMENTS_2026-08-06.md)、
[`work-wsl-witwin`](../branches/work-wsl-witwin.md) 和
[`work-ios-recorder`](../branches/work-ios-recorder.md) 为准。

核心结论如下：

- iPhone 端已经具备视频、逐帧 ARKit 位姿/内参、CoreMotion、事件、校验和及完整 session 导出的基础能力，不需要重写采集 App。
- 服务器端 COLMAP/CUDA/Python 环境已经安装，并在 South Building 数据集上验证了 mapper、PatchMatch 和 fusion；但尚未验证“从空数据库导入 iPhone session”的链路。
- `pipelines/reconstruction/` 目前只有流程说明，没有 `inspect_session`、抽帧、关键帧、COLMAP、轨迹对齐或网格分析代码，因此当前 session 不能一键建模。
- 第一版房间建模应以“后置视频 + ARKit 位姿/内参”为主。ARKit 已内部融合相机和 IMU；原始 CoreMotion 第一阶段用于时间/单位/重力/缺样质量检查，不应把重新实现完整 VIO 作为首个模型的前置条件。
- 当前最紧急的服务器阻塞项是：Git worktree 元数据失效，以及数据盘仅剩约 14 GB。两者必须先处理，否则代码不可可靠版本化，正式视频和稠密重建也没有安全空间。
- 跨端契约需要先升级并冻结。当前 iOS 输出已经接近可用，但仍缺视频方向/颜色/裁剪语义、IMU 单位和参考系、明确的矩阵字段规范，以及可靠的丢帧后视频样本索引。

## 2. 本次审计到的实际现状

### 2.1 iPhone 端已有能力

当前 App 版本文档记录为 `0.3.0`，实际 session 可包含：

```text
metadata.json
capabilities.json
assembly.json
rear_video.mov
ar_frames.csv
face_anchors.csv
imu.csv
events.csv
udp_tx.csv                 # 启用 P2 时
validation_report.json
checksums.sha256
```

代码已经做到：

- `rear_video.mov` 直接使用 `ARFrame.capturedImage` 写入 HEVC；
- `ar_frames.csv` 保存 ARFrame 时间戳、回调单调时钟、视频 PTS、4×4 相机位姿、3×3 内参、图像尺寸和 tracking state；
- `imu.csv` 保存加速度计、陀螺仪、user acceleration、rotation rate、gravity、姿态四元数和磁场；
- ARKit、IMU、UDP 回调均保存手机单调时钟字段；
- 停止采集后生成验证报告和 SHA-256；
- UI 已提供“导出完整 session 文件夹”。

已有真机测试证明 1 分钟采集可以达到视频/ARKit 3583 帧、视频丢帧 0、IMU 约 100 Hz，并通过自动完整性检查。因而当前重点不是增加更多传感器，而是把现有输出变成严格、版本化、可导入的数据契约。

### 2.2 服务器端已有能力

本次只读检查确认：

- RTX 5090 可见，显存约 32 GB；
- COLMAP 4.0.4 CUDA 构建可运行；
- 项目 Python 3.12 环境可运行，`pip check` 无损坏依赖；
- South Building 已完成 128/128 图像稀疏建图、PatchMatch 和 891,084 点 fusion；
- FFmpeg/ffprobe、PyCOLMAP、OpenCV、Open3D、Trimesh 等环境已按现有文档准备；
- `pipelines/reconstruction/` 只有 `README.md`，没有可执行流水线；
- `/root/nfs/chenzhf/witwin/testdata/sessions/` 当前没有可供验证的 iPhone session。

### 2.3 当前基础设施阻塞

#### A. Git worktree 已失效

仓库根目录 `.git` 当前内容为：

```text
gitdir: /root/nfs/chenzhf/witwin-workspace/.git/worktrees/repository
```

但目标管理目录不存在，`git status --short --branch` 报：

```text
fatal: not a git repository: /root/nfs/chenzhf/witwin-workspace/.git/worktrees/repository
```

在修复前，当前源代码树可以读取和运行，但不能可靠确认分支、追踪改动、提交或回滚。不得直接把现有目录初始化为新仓库，也不得覆盖现有文件。推荐先确认规范远端和 `work/wsl-witwin` 提交，在同级新目录安全克隆/恢复，再逐文件比较当前树。

#### B. 数据盘空间不足

`/root/nfs` 和 `/datasets` 实际位于同一分区，目前约 2.7 TB 已使用 2.6 TB，仅剩约 14 GB，`df` 显示 100%。这只够极小冒烟测试，不足以安全保存正式视频、抽帧和稠密重建工作区。

在空间问题解决前：

- 只允许 20–60 秒、受控分辨率/关键帧数的小 session；
- 不运行不受控的全分辨率 PatchMatch；
- 不删除其他项目、缓存或已有重建产物来腾空间；
- 应由用户指定新的大容量挂载点，或明确授权清理目标。

首个真实 session 建议至少准备 100 GB 可用空间；若要保留多个参数组合和稠密工作区，建议 200 GB 以上。该值是工程预算，不是当前实测峰值，实际峰值必须由首个小 session 报告校正。

## 3. 尚未解决的问题与责任边界

### 3.1 必须在服务器端完成

| 编号 | 问题                             | 当前证据                        | 服务器端应实现的结果                                                      |
| ---- | -------------------------------- | ------------------------------- | ------------------------------------------------------------------------- |
| S0   | Git 工作区不可用                 | `.git` 指向不存在目录         | 恢复可用 worktree，能确认分支、状态和远端；保留当前文件                   |
| S1   | 正式数据无安全存储位置           | 当前只剩约 14 GB                | 指定原始数据、派生数据、日志路径和最小余量门槛                            |
| S2   | 没有可靠上传/接收流程            | 目前只有 iPhone ShareLink       | Mac/VS Code 到服务器的断点续传、`.partial` 暂存、校验后原子入库         |
| S3   | 没有 session 导入器              | reconstruction 目录只有 README  | `inspect_session`：Schema、SHA、视频、CSV、时间轴、内参、位姿、IMU 报告 |
| S4   | 没有视频抽帧与映射               | 只有 MOV 和 CSV                 | `extract_frames`：每张图可追溯到 MOV PTS、ARFrame、手机时间和内参       |
| S5   | 没有关键帧选择                   | 无实现                          | 清晰度、曝光、基线、tracking、覆盖度的版本化选择器                        |
| S6   | iPhone 数据未从空数据库验证      | South Building 使用数据包数据库 | CUDA SIFT + sequential matcher；ALIKED/LightGlue 对照；输出数据库和报告   |
| S7   | 三种 mapper 未在 iPhone 数据验证 | 仅命令存在                      | mapper/global_mapper/pose_prior_mapper 分别输出可分析结果和指标           |
| S8   | ARKit 与 COLMAP 未对齐           | 无 Sim(3) 工具                  | 合成测试通过的 RANSAC + Sim(3)，保存尺度、内点和残差                      |
| S9   | IMU 尚未进入离线质量分析         | 只在手机端检查采样率            | 单位/轴向/时间间隙/饱和/重力一致性报告；第一阶段不重复实现 VIO            |
| S10  | 稠密点云到 WiTwin 网格未实现     | 只验证 fusion 点云              | 稠密、平面、Manhattan、网格、简化、闭合性和材料区域导出                   |
| S11  | 任务不可恢复、不可审计           | 无流水线入口                    | 分阶段状态文件、配置快照、日志、退出码、磁盘峰值和幂等重跑                |
| S12  | CSI 尚未物化到手机时间轴         | clock fit 已有，关联工具没有    | 后续把 CSI 映射到手机时间，并关联最近 ARKit 帧和 IMU 区间                 |

### 3.2 必须在 iPhone 端完成

| 编号 | 问题                             | 当前实现                                                                  | iPhone 端应修改的结果                                                                                      |
| ---- | -------------------------------- | ------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| I1   | session 契约不足以表达逐帧语义   | Schema 1.2 主要覆盖公共摘要                                               | 与服务器共同发布新次版本，明确每个 CSV 的字段、类型、单位和参考系                                          |
| I2   | 视频成像语义不完整               | 有编码、尺寸和 PTS，但 manifest 未完整声明                                | 记录 codec、像素格式/颜色空间、标称帧率、方向、镜像、镜头、裁剪/缩放/稳像策略                              |
| I3   | 位姿列名不完全统一               | CSV 使用`world_T_rear_camera_*`，规范使用 `arkit_world_T_rear_camera` | 统一命名或在版本化格式中声明兼容映射；明确行主序、右手系和米                                               |
| I4   | 丢帧后的实际视频样本索引不可靠   | `video_frame_id` 当前总是等于 AR `frame_id`                           | 仅在 append 成功时递增视频样本序号；失败行留空或记`-1`，保留原 AR frame id                               |
| I5   | IMU 单位和参考系没有机器可读声明 | CSV 使用通用`x/y/z/w`                                                   | 明确 accelerometer/gravity/userAcceleration 的单位、gyro 单位、磁场单位、四元数顺序和 device-motion 参考系 |
| I6   | 缺样/饱和语义不足                | 可由时间戳部分推断                                                        | 记录请求/实际采样率、传感器可用性、时间间隙统计和已知中断事件；原始记录不做静默插值                        |
| I7   | 构建来源不可追溯                 | 有 App 版本/build，无源码提交字段                                         | 构建时注入 commit 或构建标识，写入 metadata；无法取得时明确为`unknown`                                   |
| I8   | 大 session 导出可靠性未验证      | ShareLink 可导出目录                                                      | 增加封装进度、导出前空间检查和最终校验；首阶段可导出到 Mac，不在 App 内嵌 SSH 私钥                         |
| I9   | 正式房间扫描规范未落到 UI/事件   | 有人工 marker 和 tracking 事件                                            | 增加开始静止段、结束静止段、回环、标定物/测距点等事件标记及扫描提示                                        |

### 3.3 必须跨端共同冻结

以下内容不能由服务器或 iPhone 各自定义一份：

1. Canonical session 文件名：建议继续把现有 `metadata.json` 作为原始 manifest；服务器可生成派生的 normalized manifest，但不得改写原始文件。
2. Schema 版本与兼容策略：服务器先兼容现有 `1.2.0`，新增字段采用新次版本；改变单位/含义才提升主版本。
3. CSV 格式规范：字段顺序、空值、布尔值、数值精度、时间基、单位、坐标轴和矩阵展开顺序。
4. 时间关系：`ARFrame.timestamp`、`callback_phone_monotonic_ns`、视频 PTS、CoreMotion timestamp 的定义及可比较范围。
5. 坐标关系：`arkit_world_T_rear_camera`、图像旋转后的内参、COLMAP world-to-camera 形式和 `room_T_arkit_world`。
6. fixture：提交一个不含敏感内容的 2–5 秒小 session 或合成 fixture，供 iOS 与服务器 CI 同时验证。

## 4. 建议的数据传输与目录方案

第一阶段不建议在 iPhone App 内直接实现 SSH/SFTP。更稳妥的链路是：

```text
iPhone 完成并校验 session
  -> ShareLink/AirDrop/Files 导出到 Mac
  -> rsync/scp 上传到服务器 <session_id>.partial
  -> 服务器校验 checksums.sha256 与 metadata.json
  -> 原子改名为 raw/<session_id>
  -> raw 只读，所有输出进入 derived/、colmap/、alignment/、mesh/、reports/
```

建议服务器结构：

```text
<DATA_ROOT>/sessions/<session_id>/
├── raw/                       # iPhone 原始内容，不改写
│   ├── metadata.json
│   ├── rear_video.mov
│   ├── ar_frames.csv
│   ├── imu.csv
│   └── ...
├── derived/
│   ├── frames/
│   ├── frame_manifest.parquet
│   ├── quality_metrics.parquet
│   └── keyframes/
├── colmap/
├── alignment/
├── mesh/
└── reports/
```

传输工具必须支持断点续传。上传完成后先在暂存目录验证，再原子改名；不得让流水线读取仍在上传的目录。传输日志至少记录源/目标、开始结束时间、字节数和最终 SHA-256 结果。

## 5. 下一步执行方案

### 阶段 0：解除基础阻塞

#### 0A. 恢复 Git 元数据

1. 只读记录当前树文件清单与关键文件 SHA-256。
2. 确认规范 Git 远端、目标分支 `work/wsl-witwin` 和预期提交。
3. 在新的同级目录克隆/恢复 worktree，不覆盖现有 `repository`。
4. 比较新 worktree 与当前树，迁移仅属于当前树的未提交文件。
5. 验证 `git status --short --branch`、远端跟踪和分支状态。

通过条件：Git 状态可用，现有文件无丢失，后续文档和代码可被追踪。

#### 0B. 准备数据盘

1. 用户指定新的大容量挂载点，或明确授权清理具体目录。
2. 设定 `DATA_ROOT`、日志路径和磁盘停止阈值。
3. 验证服务器进程对该目录具有读写权限。
4. 用 1 GB 临时文件或等价方法做顺序读写探针后删除该临时文件。

通过条件：首个真实 session 建议至少有 100 GB 可用空间；流水线开始前和每阶段结束后均检查余量。

### 阶段 1：冻结契约并取得最小样例

服务器端：

- 在 `schemas/session-format/` 增加 ARFrame、IMU 和视频 manifest 的正式规范；
- 先实现对现有 Schema 1.2/iOS 0.3.0 的兼容解析器；
- 建立一个小型 fixture 的自动测试。

iPhone 端：

- 补齐 I1–I7；
- 修复丢帧后视频样本索引；
- 导出 20–60 秒小 session，包含静止开始、缓慢平移、转角、回到起点、静止结束；
- 同时记录一到两个人工测距或已知尺寸。

通过条件：服务器能在不改写原始文件的前提下解析全部记录；每个成功视频样本均能追溯到 ARFrame、视频 PTS、手机时钟和内参。

### 阶段 2：实现导入检查和抽帧

在 `pipelines/reconstruction/` 首先实现：

```text
inspect_session
extract_frames
select_keyframes
```

`inspect_session` 输出机器可读 JSON 和人类可读 Markdown，至少覆盖：

- Schema、文件角色、文件大小和 SHA；
- ffprobe 解码、帧数、时长、分辨率、旋转和颜色信息；
- ARKit/IMU 时间戳单调性、重复、间隙和重叠区间；
- 内参有限性和合理范围；
- 位姿旋转正交性、行列式、平移速度/范围；
- tracking state、热状态、掉帧和中断事件；
- IMU 采样率、缺样、单位、饱和和重力模长；
- 预计抽帧/稠密输出空间和当前磁盘余量。

通过条件：异常必须精确定位到文件、行号、字段和时间区间；报告失败时禁止自动进入 COLMAP。

### 阶段 3：从空数据库完成稀疏重建

实现：

```text
prepare_colmap
run_reconstruction --stage sparse
```

执行顺序：

1. CUDA SIFT + sequential matcher；
2. 同一关键帧集上运行内置 ALIKED + LightGlue 对照；
3. 分别运行 incremental mapper、global mapper、pose-prior mapper；
4. 保存注册率、匹配数、三角化点、轨迹长度、重投影误差、失败图像、耗时和磁盘峰值。

首轮通过条件：至少一种前端和一种 mapper 从空数据库产生非空模型，且模型可由 PyCOLMAP 读取。注册率目标可暂设为 80%，但最终阈值应根据首个真实 session 的覆盖和失败原因冻结，不能为了达标静默删帧。

### 阶段 4：ARKit/COLMAP 米制对齐

实现 `align_arkit_colmap`：

1. 先用合成相机验证矩阵方向、求逆和四元数顺序；
2. 验证图像旋转/缩放后投影和内参一致；
3. 按帧映射建立 ARKit 相机中心与 COLMAP 相机中心对应；
4. 排除 tracking 异常和视觉外点，RANSAC 估计 Sim(3)；
5. 保存尺度、旋转、平移、内点率、RMSE、P50/P95 残差；
6. 使用人工测距或已知尺寸独立检查米制尺度。

通过条件：结果不仅能可视化，还必须有独立米制误差和闭环误差报告。

### 阶段 5：稠密重建、房间结构化与 WiTwin 导出

1. 受控运行 `image_undistorter`、PatchMatch 和 `stereo_fusion`；
2. 生成点云质量报告，确认有限坐标、法向和颜色；
3. 进行墙/地/顶平面拟合和 Manhattan 方向估计；
4. 网格化、简化、补洞，并报告连通分量、孔洞、非流形边和法向；
5. 输出米制低多边形网格、主要传播面、材料区域占位标记和坐标变换；
6. 用关键墙长、夹角、平面 RMSE 和重复扫描一致性评估几何。

通过条件：网格可由 WiTwin 加载，手机轨迹、房间网格和后续 CSI 接收坐标位于同一 `room` 坐标系，并且坐标变换可追溯。

### 阶段 6：接入 CSI 和统一 session

房间模型首轮通过后，再把现有 `fit_phone_csi_clock.py` 输出正式物化：

- 每条 CSI 保存映射后的手机时间、映射版本和残差质量；
- 关联最近 ARKit 帧和覆盖该时间的 IMU 区间；
- 不假设一条 UDP 等于一条 CSI；
- 相位校准通过前，主实验优先使用幅度、RSSI、包级时间和相对特征；
- 最终统一加载器同时读取 CSI、手机轨迹、人体参考点、房间网格、材料区域和装配标定。

## 6. 推荐代码边界

服务器仓库：

```text
pipelines/reconstruction/
├── pyproject.toml
├── configs/
├── src/witwin_reconstruction/
│   ├── inspect_session.py
│   ├── extract_frames.py
│   ├── select_keyframes.py
│   ├── prepare_colmap.py
│   ├── run_reconstruction.py
│   ├── align_arkit_colmap.py
│   └── analyze_geometry.py
└── tests/
    ├── fixtures/
    ├── test_session_contract.py
    ├── test_timestamps.py
    ├── test_intrinsics_rotation.py
    └── test_sim3.py
```

iPhone 仓库：

```text
apps/ios-recorder/
├── Models/SessionModels.swift             # 新 schema 字段
├── Services/RoomScanRecorder.swift        # 视频/ARFrame 映射和成像元数据
├── Services/MotionRecorder.swift          # 单位、参考系、采样信息
├── Services/SessionIntegrityValidator.swift
└── Tests/                                  # 编码、丢帧、manifest 和导出测试
```

共享契约只放在 `schemas/session-format/`。服务器不得在 Python 中另造隐式字段，iPhone 也不得把服务器派生结果写回原始 session。

## 7. 近期任务排序

| 优先级 | 任务                              | 责任端           | 依赖                 | 产出                      |
| ------ | --------------------------------- | ---------------- | -------------------- | ------------------------- |
| P0     | 恢复 Git worktree                 | 服务器           | 规范远端/分支信息    | 可追踪仓库                |
| P0     | 提供至少 100 GB 数据空间          | 服务器/用户      | 新挂载或明确清理授权 | `DATA_ROOT`             |
| P0     | 冻结 session vNext 契约           | 共享             | 当前 1.2 和 iOS 输出 | Schema、CSV 规范、fixture |
| P0     | 修复视频样本索引并补齐元数据      | iPhone           | vNext 契约           | 新小 session              |
| P1     | 实现上传暂存和`inspect_session` | 服务器           | DATA_ROOT、fixture   | 导入报告                  |
| P1     | 实现抽帧、内参转换和关键帧        | 服务器           | 导入通过             | keyframes + manifest      |
| P1     | 从空数据库跑通 sparse 三路线      | 服务器           | 关键帧               | 对照报告                  |
| P1     | 实现并验证 Sim(3)                 | 服务器           | sparse + ARKit       | 米制轨迹/模型             |
| P2     | PatchMatch、fusion 和网格 QA      | 服务器           | 米制稀疏模型、空间   | 点云/网格报告             |
| P2     | 正式扫描与独立测距                | iPhone/实验      | 扫描规范             | 首个真实验收 session      |
| P3     | CSI 时间轴物化和统一加载器        | 服务器/CSI Linux | 房间坐标闭环         | unified session           |

## 8. 立即可执行的下一步

建议下一轮严格按以下顺序开始：

1. 先恢复 Git worktree，不改写当前源文件。
2. 用户指定大容量数据目录；未解决前只做 20–60 秒小样。
3. 由服务器端先提交 session vNext 草案和兼容解析器测试。
4. iPhone 端按草案补齐元数据、单位和视频索引，并导出一个最小 session。
5. 服务器实现 `inspect_session`，只做导入和报告，不立即跑稠密重建。
6. 导入报告通过后，实现抽帧和 CUDA SIFT/sequential matcher 冒烟测试。
7. sparse 非空后再做 Sim(3)，Sim(3) 有独立尺度检查后再启动 PatchMatch。

这个顺序把风险逐层隔离：先保证代码和数据可追溯，再验证契约和时间轴，然后验证稀疏几何、米制尺度，最后才消耗大量磁盘和 GPU 做稠密建模。

## 9. 当前明确不应做的事项

- 不在 iPhone App 内保存服务器 root 私钥或硬编码 SSH 凭据。
- 不在手机端过滤、插值或“修复”原始 IMU/位姿后覆盖原始数据。
- 不把完整 ORB-SLAM3/VINS 标定作为第一个 COLMAP 房间模型的前置条件。
- 不因为 ARKit 平移单位是米，就直接宣称 COLMAP 模型已经米制正确。
- 不在当前 14 GB 余量下运行正式高分辨率稠密重建。
- 不在 Git 元数据失效时初始化新仓库或覆盖当前目录。
- 不把 MOV、抽帧、数据库、深度图、点云和网格提交进 Git。

## 10. 验收总定义

第一阶段“iPhone 数据上服务器建模完成”应同时满足：

1. 原始 session 校验通过且保持不变；
2. 每个关键帧可追溯到视频 PTS、ARFrame、手机时间和内参；
3. iPhone 数据从空 COLMAP 数据库产生非空稀疏模型；
4. ARKit/COLMAP Sim(3) 有内点和残差报告，并通过独立米制检查；
5. PatchMatch/fusion 产物非空且可由 Open3D 读取；
6. 网格有尺度、平面、法向、连通性、孔洞和非流形报告；
7. 所有配置、命令、版本、日志路径、输出路径、退出状态和磁盘峰值可追溯；
8. 最终网格和手机轨迹可进入同一 `room` 坐标系，为后续 CSI/WiTwin 联合建模提供输入。

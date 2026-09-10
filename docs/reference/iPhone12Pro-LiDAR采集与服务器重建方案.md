# iPhone 12 Pro LiDAR 采集与服务器端重建方案

> 状态：方案稿，尚未实施、尚未通过真机与服务器验收。
>
> 适用范围：WiTwin 单房间/小型室内空间的几何建模，以及后续“人体位置—姿态—CSI—房间传播环境”联合实验。
>
> 设备前提：iPhone 12 Pro（后置 LiDAR、前置 TrueDepth）、固定手机夹具、CSI 接收端与现有 WiTwin 服务器。

## 1. 结论

本项目不应把单一 SLAM 软件当作最终答案。对 iPhone 12 Pro 的传感器形态和 WiTwin 的度量几何需求，推荐的主重建链是：

```text
ARKit VIO 位姿与相机标定
        +
逐帧 sceneDepth + confidenceMap
        ↓
RGB-D / point-to-plane ICP 位姿图精修（有证据时才接受）
        ↓
置信度加权 TSDF 融合
        ↓
RoomPlan + ARKit 平面/网格提供结构先验与交叉验证
        ↓
墙/地/顶/门窗结构化、网格清理、简化和材料区域标注
        ↓
WiTwin 可追溯的度量场景模型
```

主实现建议使用 **ARKit + Open3D Tensor TSDF/pose graph**。ARKit 网格、RoomPlan 和纯 ARKit 轨迹分别保留为基线，不能被最终结果覆盖。COLMAP 只作为视觉纹理与 LiDAR 缺失区域的补充；RTAB-Map 只在多房间、长轨迹或明显闭环问题出现时作为增强项。FAST-LIO、LIO-SAM、LOAM 等面向旋转式/高线数激光雷达的算法不适合作为 iPhone `sceneDepth` 的主链。

采集采用“**静态房间建模**”与“**动态 CSI/人体实验**”分离的设计。首版不要同时运行 RoomPlan、全量 mesh、全率深度、前脸、视频、IMU 和 UDP；否则出现丢帧或热降频时，很难确定原因，也会破坏现有已验证的联合时间线。

## 2. 设计依据与边界

### 2.1 iPhone 12 Pro 能提供什么

Apple 的规格页确认 iPhone 12 Pro 配有 LiDAR Scanner、三轴陀螺仪、加速度计与前置 TrueDepth。实际 App 仍必须在运行时探测 API 能力，不能只按机型名判断：[iPhone 12 Pro 技术规格](https://support.apple.com/en-us/111875)。

ARKit `sceneDepth` 是与当前后置相机帧对应的、以米为单位的场景距离估计；启用前必须调用 `supportsFrameSemantics`。`smoothedSceneDepth` 是跨帧平滑结果，适合预览或辅助，但不能替代主数据：[sceneDepth](https://developer.apple.com/documentation/arkit/arconfiguration/framesemantics-swift.struct/scenedepth)、[scene depth 点云示例](https://developer.apple.com/documentation/arkit/displaying-a-point-cloud-using-scene-depth)。

ARKit `sceneReconstruction = .meshWithClassification` 可产生持续更新的三角网格与粗语义类别。开启平面检测会影响网格，使检测到的平面更平整，因此保存时必须记录配置，不能把它误称为未经处理的 LiDAR 原始点云：[sceneReconstruction](https://developer.apple.com/documentation/arkit/arworldtrackingconfiguration/scenereconstruction)、[Apple 场景重建示例](https://developer.apple.com/documentation/arkit/visualizing-and-interacting-with-a-reconstructed-scene)。

RoomPlan 的 `CapturedRoomData` 可序列化后延迟处理，`CapturedRoom`/USDZ 适合作为墙、门、窗和大件物体的结构化先验与可视化结果：[CapturedRoomData](https://developer.apple.com/documentation/roomplan/capturedroomdata)。RoomPlan 不是逐像素几何真值，也不能从类别直接推出电磁材料。

### 2.2 本项目已经成立的约束

- 现有 Schema 1.4.0 已覆盖后置视频、ARKit 位姿/内参、CoreMotion、前脸、UDP/CSI 对时等基础链路。
- 后置视频帧、ARKit 位姿和前脸数据应继续来自同一个 `ARSession`/`ARFrame` 时间线。
- `video_frame_id` 只对成功写入 MOV 的帧递增；丢帧写 `-1`，不能制造不存在的视频帧。
- 坐标变换采用 `target_T_source`、右手系、米制、row-major 表达。
- 最终模型面向传播仿真：主要墙面、地面、顶面和开口的度量准确性，比照片级渲染更重要。
- 原始采集数据只读保存；所有重建、精修、简化和语义结果均为派生物。

## 3. 采集任务拆分

每个真实房间建议包含四类独立 session。它们共享房间编号和固定控制点，但各自有独立时间线、校验和与清单。

| Session 类型 | 目的 | 主要数据 | 是否含 CSI/人体 | 建议次数 |
|---|---|---|---:|---:|
| `L0_capability` | 真机能力、负载和时序摸底 | 视频、ARFrame、深度、mesh、运行状态 | 否 | 每个 App/系统版本至少 1 次 |
| `G1_lidar_geometry` | 房间度量几何主数据 | 后置 RGB、ARKit、sceneDepth/confidence、mesh | 否 | 每房间 2–3 次 |
| `G2_roomplan_structure` | 墙/门/窗/大件物体结构先验 | CapturedRoomData、CapturedRoom JSON、USDZ | 否 | 每房间 1–2 次 |
| `E1_joint_experiment` | 人体/CSI 联合实验 | 现有视频、ARKit、IMU、前脸、UDP；低率深度可选 | 是 | 按实验条件重复 |

分离 session 的原因是：房间几何通常静态且只需高质量扫描一次，而人体/CSI 实验需要严格、稳定的联合时间线。几何建模失败不应迫使重做全部 CSI 条件，CSI 会话的热负载也不应污染房间参考模型。

## 4. iPhone 端采集方案

### 4.1 共同准备

1. 使用同一台 iPhone 12 Pro、同一手机壳、夹具和安装方向。记录机型标识、iOS、App、schema、存储余量、电量、温度状态和相机格式。
2. 手机—夹具—天线的相对位置在一轮实验内不改变。若改变，生成新的 `assembly_id` 和标定记录。
3. 房间内设置至少 4 个固定、可重复检测的控制标记；至少 3 个不共线，覆盖不同墙面和高度。记录标记在 `room` 坐标系中的三维坐标与测量方法。
4. 手工测量不少于 5 个校核量：房间长/宽/高、至少一个门或窗尺寸，以及两个远距离控制点间距。测量值不参与所有模型拟合，应留出一部分作为盲测。
5. 扫描前清理快速移动人员和镜面遮挡；玻璃、镜面、纯黑和强日照区域单独标记为低可信区。
6. 每次采集前后分别静止 10–20 秒，并在可见固定控制点的位置开始和结束。

### 4.2 `L0_capability`：先做能力与负载门控

此阶段只定义验收步骤，不在本方案中执行。

启动时必须记录以下探测结果：

- `ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)`；
- `supportsFrameSemantics(.smoothedSceneDepth)`；
- `supportsSceneReconstruction(.meshWithClassification)`；
- `ARWorldTrackingConfiguration.supportsUserFaceTracking`；
- RoomPlan 的系统版本可用性；
- 实际 RGB 分辨率、深度分辨率、像素格式、帧率和可用相机内参；
- `sceneDepth + meshWithClassification + userFaceTracking` 是否能在本机、本 iOS 版本上共同运行。

以 30 秒、60 秒、120 秒三个档位逐级测试。记录视频写入失败、深度缺帧、ARKit tracking state、队列积压、App 内存警告、thermal state 和 session interruption。

接受条件：

- 时间戳单调，无重复主键；
- 每个深度样本能唯一关联到 `ar_frame_id`；
- 视频成功帧与 `video_frame_id` 规则不被破坏；
- 120 秒内没有持续热降频、崩溃或不可恢复的积压；
- 若全功能并发不通过，按“mesh 更新 → 动态会话深度 → smoothed depth”的顺序降级，不能牺牲 E1 的视频/ARKit/IMU/前脸/UDP 基线。

### 4.3 `G1_lidar_geometry`：房间几何主扫描

建议使用单个 `ARWorldTrackingConfiguration`：

- world alignment：`.gravity`；
- frame semantics：`.sceneDepth`；
- scene reconstruction：`.meshWithClassification`；
- plane detection：`.horizontal` 与 `.vertical`；
- 后置相机图像直接取同一 `ARFrame.capturedImage`；
- `smoothedSceneDepth` 仅作可选预览/对照，不作为主 TSDF 输入。

扫描路线：

1. 在控制点可见处静止 10–20 秒。
2. 沿房间周边缓慢走一圈，手机运动平稳，覆盖墙—地、墙—顶连接处。
3. 对门窗、凹槽、家具遮挡后区域做第二视角补扫。
4. 回到起点形成闭环，再静止 10–20 秒。
5. 反方向或不同起点重复一遍；两次扫描必须是独立 session，以便评估重复性。

速度不写死为“每秒多少米”，首轮以运动模糊、tracking quality 和深度覆盖率联合决定。操作员 UI 应实时提示“过快、tracking limited、深度无效比例过高、存储不足和热状态”，但提示不得改变原始数据。

深度保存策略：

- 首选保存每个实际可用的 `sceneDepth`，不预设它一定等于视频帧率。
- 若 L0 证明持续写入会丢视频或引发热问题，改为确定性的 10–15 Hz 抽样；每个 ARFrame 仍保留，未选中时显式写 `depth_sample_id = -1`。
- 保存 Float32 米制 depth map 和原始 `confidenceMap` 枚举值；不要转成 8-bit PNG，也不要在手机端先填洞。
- 保存 RGB 与 depth 的宽高、方向、裁剪/显示变换和 ARCamera 内参。服务器按分辨率缩放内参，不凭经验猜测投影关系。
- 无效值规则、confidence 枚举映射和字节序写入元数据。

mesh 保存策略：

- 保存 ARMeshAnchor 的 add/update/remove 事件，包含 anchor UUID、关联 `ar_frame_id`、anchor transform、顶点、法线、三角面、分类和 revision。
- 结束时另存一份合并后的 final snapshot，便于快速预览。
- 事件日志是可追溯输入，final snapshot 是派生便利文件；两者不能互相替代。

### 4.4 `G2_roomplan_structure`：单独完成 RoomPlan 扫描

RoomPlan 与 G1 分开运行，避免多套高负载扫描逻辑争用资源，也让结构先验和密集深度具有独立失败边界。

保存三类结果：

1. 可序列化的 `CapturedRoomData`，供以后在不同版本重新处理；
2. `CapturedRoom` 的结构化 JSON/Codable 结果；
3. USDZ，仅用于人工查看和跨工具交换。

RoomPlan 输出不直接覆盖 TSDF。墙、门、窗拓扑优先作为约束或候选；只有通过控制点和手工尺寸验收后，才能写入最终结构化房间壳体。

### 4.5 `E1_joint_experiment`：人体、姿态、CSI 联合采集

E1 保留现有单 `ARSession` 设计：

- 后置 `capturedImage`/MOV；
- ARKit 相机位姿和内参；
- CoreMotion；
- `userFaceTrackingEnabled` 的前脸 anchor/距离；
- UDP 发包与 CSI 接收侧对时；
- 同一个 phone monotonic clock；
- 现有成功写帧、丢帧和异常记录语义不变。

E1 默认关闭 RoomPlan 和高频 mesh 更新。LiDAR 的使用分两档：

- **默认档**：10 Hz 左右的 `sceneDepth` 作为遮挡/局部几何质检；
- **稳定性优先档**：完全关闭 E1 深度，只使用已完成的 G1/G2 房间模型。

若 L0 证明 `userFaceTracking + sceneDepth` 在目标系统组合下不稳定，必须选稳定性优先档。房间已经由 G1/G2 建好，因此这不是数据损失，而是合理的职责分离。

每次 E1 在实验主体进入前后拍到固定控制点。可选加载同房间保存的 `ARWorldMap` 以帮助重定位，但不能仅凭重定位成功就声称多个 session 已处于同一坐标系。服务器仍需计算并记录 `room_T_arkit_world`，用控制点求解 SE(3) 后报告残差。

### 4.6 绝对不要混淆的数据含义

- `sceneDepth` 是 ARKit 对 LiDAR 与相机处理后的深度产品，不是原始 ToF 回波。
- `smoothedSceneDepth` 是时间平滑产品，不是更高精度的“真值”。
- ARKit mesh 会持续更新，且可能受 plane detection/people occlusion 配置影响。
- ARMeshClassification 和 RoomPlan 类别是几何/物体弱标签，不是混凝土、玻璃、木材等电磁材料测量。
- ARWorldMap 用于重定位，不等于跨 session 的已验证全局标定。

## 5. 建议的 Session Format 1.5.0 扩展

当前仓库的 1.4.0 不包含 LiDAR 文件语义。本节只是下一版合同提案；在 recorder、validator、导入器和文档同时更新前，不得把任何输出标记为 1.5.0。

建议新增而不破坏旧字段：

```text
session/
├── metadata.json
├── capabilities.json
├── assembly.yaml
├── rear_video.mov
├── ar_frames.csv
├── imu.csv
├── face.csv
├── udp_events.csv
├── lidar/
│   ├── lidar_frames.csv
│   ├── scene_depth.f32le
│   ├── confidence.u8
│   ├── mesh_events/
│   ├── mesh_manifest.json
│   └── arkit_mesh_final.ply
├── roomplan/
│   ├── captured_room_data.json
│   ├── captured_room.json
│   └── room.usdz
├── calibration/
│   ├── control_points.csv
│   └── manual_measurements.yaml
├── events.jsonl
└── checksums.sha256
```

`lidar_frames.csv` 至少包含：

- `depth_sample_id`、`ar_frame_id`、`ar_frame_timestamp_s`；
- `callback_phone_monotonic_ns`；
- `depth_offset_bytes`、`confidence_offset_bytes`；
- `depth_width`、`depth_height`、像素格式和字节序；
- `captured_image_width`、`captured_image_height`；
- `depth_kind = scene_depth | smoothed_scene_depth`；
- `valid_pixel_ratio` 与各 confidence 等级像素数；
- `mesh_revision`（无更新为 `-1`）。

ARKit pose 和 `K_rgb` 继续以 `ar_frames.csv` 为唯一真值。服务器通过 `ar_frame_id` 关联，不在 LiDAR 文件中复制一套可能分叉的 pose。由 `K_rgb` 缩放得到 `K_depth` 时，派生清单必须记录公式、图像方向与裁剪变换。

metadata 建议新增：

- `session_purpose`：`capability`、`lidar_geometry`、`roomplan_structure`、`joint_experiment`；
- `depth_sampling_policy` 与目标/实际采样率；
- `frame_semantics`、`scene_reconstruction`、`plane_detection`；
- `ios_version`、`device_model_identifier`、`app_version`、`schema_version`；
- 运行时能力探测结果；
- `assembly_id`、`room_id`、`scan_repeat_id`；
- thermal/interruption/drop 统计；
- 所有文件大小和 SHA-256。

## 6. 坐标系与跨 Session 对齐

继续遵守现有命名和 `target_T_source` 约定：

- `arkit_world`：每个 session 的局部 ARKit 世界系；
- `rear_camera`：当前后置相机坐标系；
- `phone_body`：手机/夹具刚体系；
- `face_anchor`、`human_ref`：前脸与人体参考系；
- `room`：跨扫描、跨实验保持稳定的房间坐标系；
- `csi_rx`：CSI 接收阵列坐标系。

建议把 `room` 定义为：原点在一处永久控制点，+Z 向上，+X 沿主墙，+Y 由右手系确定。对每个 G1/G2/E1 单独求解：

```text
room_T_arkit_world
```

对齐过程：

1. 在 RGB 帧/点云中检测固定标记，得到 session 内三维点；
2. 用 3 个以上不共线点做 RANSAC + 刚体 SE(3) 求解；
3. 用未参与拟合的控制点计算 RMSE、P95 和最大误差；
4. 若单目 COLMAP 模型参与，则它首先用 Sim(3) 对齐到 LiDAR/ARKit 米制模型；最终交付仍为 SE(3) 一致的米制 `room`；
5. 变换、输入控制点、内点掩码、算法版本和残差写入 `alignment.yaml`。

## 7. 服务器端重建方案

### 7.1 环境与数据入口

服务器维护两个隔离环境：

- `reconstruction`：Open3D、OpenCV、COLMAP、点云/网格工具；
- `witwin`：锁定项目仿真依赖，只消费验收通过的场景产物。

导入步骤：

1. session 以只读方式落盘，先校验 `checksums.sha256`；
2. validator 检查 schema、时间戳单调性、ID 关联、矩阵有限性、深度 offset/长度和文件完整性；
3. 生成不可变的 `ingest_manifest.json`，记录源文件 hash、导入时间、工具版本和目标路径；
4. 后续派生目录只引用源 hash，不修改原始 session。

历史记录中的 RTX 5090/CUDA/Open3D/COLMAP 状态只能作为曾经验证过的环境，不应当成当前状态。正式执行前必须重新记录 GPU、驱动、CUDA、系统内存、磁盘余量和软件版本。历史文档曾出现系统盘只剩约 25 GB，这对密集重建是实质风险，应先解决存储而不是先调算法。

### 7.2 基线结果

每个 G1 必须先产出三份不精修基线：

1. `trajectory_arkit`：ARKit 原始轨迹；
2. `mesh_arkit`：ARKit final mesh；
3. `room_roomplan`：RoomPlan 结构结果。

基线用于定位错误来源。如果最终 TSDF 变差，可以区分是深度、位姿精修、融合还是网格后处理引入的问题。

### 7.3 主算法：置信度加权 TSDF

主链使用 Open3D Tensor 管线，流程如下：

1. 按 `ar_frame_id` 读取 RGB、sceneDepth、confidence 和 `world_T_rear_camera`。
2. 将 RGB 内参按深度分辨率、方向和裁剪关系转换为 `K_depth`。
3. 先只用高置信度深度；中置信度作为可配置补充；低置信度默认拒绝。
4. 按深度范围、入射角、时间一致性和局部法线做可追溯的离群过滤，保留过滤前统计。
5. 用 ARKit pose 初始化 RGB-D odometry 与 point-to-plane ICP。
6. 建立关键帧 pose graph：相邻边来自 ARKit + RGB-D/ICP，闭环边来自视觉检索/几何验证。
7. 只有当优化轨迹同时降低控制点误差、重复扫描误差和 held-out RGB-D 残差时，才接受精修；否则回退 ARKit pose。
8. 用接受的轨迹重新积分置信度加权 TSDF，导出点云与三角网格。

初始参数不写成不可更改的“最佳值”。voxel size、truncation、关键帧间隔和置信度策略必须形成小规模参数表，并用盲测尺寸/重复扫描选择，不能按视觉观感挑结果。单房间首轮可从 1–2 cm voxel 和 4–8 cm truncation 做网格搜索，但它们只是待验证起点。

### 7.4 结构化与网格清理

1. 从 TSDF 点云提取墙、地、顶主平面，结合 RoomPlan 和 ARMeshClassification 建立候选对应。
2. 在房间基本符合正交结构时施加 Manhattan 方向约束；非正交墙必须保留，不能为了整齐强行拉直。
3. 用高可信平面形成闭合 room shell；门窗开口以 RoomPlan 候选、RGB 证据和手工尺寸交叉确认。
4. 家具与不规则表面保留 TSDF 网格，和 room shell 分层输出。
5. 修复翻转法线、重复面、自交、非流形边和非预期孔洞；对玻璃/镜面造成的空洞显式标为 `uncertain`，必要时用手工测量 CAD 面补齐。
6. 生成 raw、clean、simplified 三档网格，简化时锁定主要平面边界和开口。

### 7.5 视觉与闭环增强的启用条件

| 方法 | 本项目角色 | 何时启用 | 不应承担的角色 |
|---|---|---|---|
| Open3D RGB-D pose graph + TSDF | 默认主链 | 所有 G1 | 无 |
| RTAB-Map | 可选长轨迹闭环 | 多房间、长走廊、ARKit 漂移且 Open3D 闭环不足 | 首版单房间默认依赖 |
| COLMAP 4.0.4+ | 视觉精修/纹理/缺失区对照 | RGB 纹理足、LiDAR 盲区明显 | 取代已有米制深度主链 |
| ARKit mesh | 实时基线和语义弱标签 | 所有 G1 | 最终唯一模型 |
| RoomPlan | 墙/门/窗结构先验 | 所有 G2 | 密集几何真值、材料真值 |
| NeRF/3DGS | 可选可视化 | 展示需求明确时 | WiTwin 碰撞/传播主几何 |
| FAST-LIO/LIO-SAM/LOAM | 不采用 | 除非未来换成对应扫描式 LiDAR | iPhone sceneDepth SLAM |

若使用 COLMAP，优先读取 ARKit 位姿先验并与 TSDF 交叉验证。服务器历史上验证过 COLMAP 4.0.4 的 Blackwell/CUDA 路径；升级版本必须重新跑固定小数据回归，不能只看编译成功。

### 7.6 材料与 WiTwin 交付

材料区域来自 RGB、现场记录和人工复核，不从深度/mesh 类别直接推断。每个区域至少记录：

- `region_id`、几何面集合；
- 可观察的表面类别；
- 假设材料与来源；
- 厚度/介电参数的先验范围；
- `measured | inferred | unknown` 证据等级；
- 后续 CSI 反演是否允许更新。

建议交付结构：

```text
derived/<room_id>/<reconstruction_id>/
├── trajectory_arkit.csv
├── trajectory_optimized.csv
├── mesh_arkit_raw.ply
├── roomplan.usdz
├── tsdf_raw.ply
├── room_shell.glb
├── scene_clean.glb
├── scene_simplified.glb
├── materials.yaml
├── alignment.yaml
├── reconstruction_config.yaml
├── provenance.json
└── qa_report.md
```

WiTwin 只读取带 `reconstruction_id`、源 session hash、坐标变换和 QA 结论的冻结版本。后续重建参数改变时创建新版本，不覆盖旧版本。

## 8. 算力、显存与存储选择

### 8.1 Laptop RTX 4050 能做什么

Laptop RTX 4050 足以完成：

- session 校验、抽帧和可视化；
- 单次短扫描的 ARKit 基线与低分辨率 TSDF；
- 小范围参数调试；
- 网格查看、人工标注和轻量简化。

它不适合作为多次高分辨率扫描、COLMAP PatchMatch、多参数网格搜索和批量重建的主要机器。限制通常来自显存、散热持续功耗和中间数据吞吐，而不是算法完全无法运行。

### 8.2 50 系服务器的定位

按当前硬件描述，服务器 50 系显卡显存约为 laptop 40 系卡的 6 倍。它不是单房间 TSDF 能否成功的必要条件，但应作为正式重建主机，因为它能：

- 容纳更细 voxel、更大 active block 和更长关键帧序列；
- 降低 COLMAP/Open3D 因显存不足而反复切块或 OOM 的概率；
- 更快完成重复扫描和参数消融；
- 保持 laptop 用于采集检查和交互工作。

推荐分工：**4050 做采集后 5–10 分钟快速质检；50 系服务器做全量重建、参数选择和最终导出。**

### 8.3 容量预算

不要只按 MOV 大小估算。以 256×192 为示例，一帧 Float32 depth 加 UInt8 confidence 约 240 KiB；如果实际深度为 60 Hz，未压缩数据约 0.86 GiB/分钟，15 Hz 时约 0.22 GiB/分钟。实际分辨率和帧率必须由 L0 测量，mesh 事件、RGB、重复扫描和中间结果还会额外占用空间。

建议：

- iPhone 采集前可用空间至少为预计原始数据的 3 倍；
- 服务器每个活跃房间预留至少 100 GB，200 GB 更稳妥；
- 多房间、多重复与 COLMAP 中间文件建议准备 500 GB 以上项目空间；
- 每次运行前检查系统盘、数据盘、临时目录和容器缓存，不把大中间文件写入仅剩几十 GB 的系统盘。

系统内存建议 64 GB 起步，批量或 COLMAP 密集任务 128 GB 更稳妥。这是工程预算建议，不是算法硬门槛；正式决定前用一组真实 session 做峰值 CPU RAM、GPU VRAM、磁盘和耗时基准。

## 9. 验收门槛

以下是首轮预注册的项目门槛，不是 Apple 对传感器精度的承诺。拿到真实数据后可以修订，但必须在查看最终实验结论前冻结版本。

### 9.1 数据完整性

- 100% 文件通过 SHA-256；
- 时间戳单调、主键唯一、所有 offset 均在文件边界内；
- 每个深度样本唯一关联一个 ARFrame；
- 视频帧成功/失败计数与 MOV 实际帧数一致；
- tracking limited、interruption、thermal 与 drop 均可定位到时间线；
- 原始文件与派生文件目录完全分离。

### 9.2 几何准确性

- 盲测房间主尺寸误差：`≤ max(5 cm, 2%)`；
- 控制点对齐：RMSE ≤ 3 cm，P95 ≤ 5 cm；
- 主要墙/地/顶平面拟合 RMSE ≤ 3 cm；
- 应为正交的主平面夹角误差 ≤ 2°；
- 两次独立 G1 扫描在主要可见表面的点到面 P95 ≤ 5 cm；
- 墙、地、顶和关键开口的有效覆盖率 ≥ 90%；
- 门窗等关键开口不得因补洞算法被封死。

如果实际物理环境、玻璃或遮挡使某项无法达标，必须在 QA 报告中标记区域与原因，不能通过删除困难区域提高分数。

### 9.3 位姿精修接受规则

优化轨迹相对 ARKit 原始轨迹，必须同时满足：

- 控制点误差不增加；
- 重复扫描一致性不降低；
- held-out RGB-D/ICP 残差下降；
- 没有新的尺度、地面高度或墙面弯曲异常。

否则该 session 使用 ARKit 轨迹完成 TSDF，并把“精修被拒绝”记录为正常、可解释结果。

### 9.4 WiTwin 下游门槛

- 网格为米制并明确 `room` 坐标系；
- 发射机、接收机、人体参考点能通过显式变换落入场景；
- 主要传播面法线一致且无大面积非流形问题；
- 材料 region 全部具有证据等级；
- 在允许的几何扰动范围内，主要路径数量、时延和到达角不存在非物理跳变；
- 同一冻结模型可由 manifest 和配置重建。

## 10. 预期故障与降级路径

| 故障 | 首选处理 | 降级结果 |
|---|---|---|
| 深度写入导致视频丢帧/热降频 | 降到确定性 10–15 Hz | 保留全 ARFrame 与抽样映射 |
| `userFaceTracking + sceneDepth` 不稳定 | E1 关闭深度 | 使用 G1 已建房间模型 |
| mesh 事件量过大 | 降低 mesh snapshot/事件频率，不影响 depth | TSDF 仍为主链 |
| RoomPlan 漏墙/门窗 | 以 TSDF + 手工尺寸修正 | RoomPlan 仅作弱先验 |
| ARKit 闭环漂移 | 控制点 + pose graph 精修 | 精修不通过则报告局部误差 |
| 玻璃/镜面深度无效 | 标记 uncertain，现场测量补面 | 不伪造传感器真值 |
| 服务器显存不足 | 降 voxel 分辨率或分块；记录参数 | 不覆盖高分辨率基线 |
| 服务器磁盘不足 | 停止导入并扩容/迁移数据盘 | 不删除唯一原始数据 |

## 11. 后续实施顺序（本次不执行）

1. **能力探测**：只实现并运行 L0，得到 iPhone 12 Pro + 当前 iOS 的真实并发与吞吐上限。
2. **合同评审**：把 1.5.0 提案转成 schema、示例 session、validator 测试和迁移说明。
3. **G1 采集**：实现 sceneDepth/confidence、mesh 事件和 final snapshot，完成两次独立房间扫描。
4. **G2 采集**：实现 RoomPlan 原始/结构化/可视化三类输出。
5. **服务器导入**：只读导入、校验和、时间线检查、基线导出。
6. **主重建**：ARKit 基线 → RGB-D pose graph → TSDF → 结构化与 QA。
7. **E1 集成**：先保持现有联合链稳定，再按 L0 结果决定是否加入 10 Hz depth。
8. **WiTwin 验证**：冻结模型版本，完成坐标、材料、路径稳定性与重复性验收。

每一步都应有独立可回退产物。未通过上一步门槛时，不进入下一步，也不为了得到“漂亮模型”跳过可追溯性验证。

## 12. 与仓库现有文档的关系

- 数据合同基线：[Session Format README](../../schemas/session-format/README.md)
- 现有采集文件定义：[capture_files.md](../../schemas/session-format/capture_files.md)
- 坐标约定：[coordinate_frames.md](../../schemas/session-format/coordinate_frames.md)
- iOS LiDAR 注意事项：[LiDAR 采集与标定指南](ios/LiDAR采集与标定指南.md)
- 算法调研基础：[iPhone SLAM 空间建模调研](research/IPHONE_SLAM_SPATIAL_MODELING_RESEARCH_2026-07-29.md)
- 服务器导入基础：[iPhone Session 导入指南](server/iPhone-Session导入指南.md)
- 服务器操作基础：[服务器工作区与远程操作指南](server/服务器工作区与远程操作指南.md)
- 项目验收原则：[研究设计与验证标准](../current/project/研究设计与验证标准.md)
- 当前迁移背景：[LiDAR 与服务器迁移计划](../current/project/LiDAR与服务器迁移计划.md)

本文件负责给出 iPhone 12 Pro 换机后的目标方案；真正实施时，`schemas/session-format` 仍是机器可读合同的唯一权威，`docs/current` 负责记录当时已经完成且通过验证的事实。

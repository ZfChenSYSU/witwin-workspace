# iPhone 11 Pro 工程进度与下一步方向

更新时间：2026-07-29

关联文档：

- [iPhone 11 Pro 多模态采集与 SLAM 建模工程交接](IPHONE_11_PRO_IMPLEMENTATION_CONTEXT.md)
- [前置深度增强的科研项目待办与验证计划](../workspace/project-docs/前置深度增强的科研项目待办与验证计划.md)
- [iOS Recorder 说明](../apps/ios-recorder/README.md)

## 1. 总体结论

当前已经完成 **P0：Mac 与真机环境**，并完成 **P1 最小版本的 1 分钟真机
功能测试**。

连续后置视频、ARKit 位姿、IMU、人脸锚点、事件、校验和与自动检查报告已经
闭环。下一步应完成正式移动路径下的 10 分钟稳定性测试，修复发现的问题并冻结
P1 格式；在此之前不进入 P2 的 CSI 开发。

## 2. 阶段状态

| 阶段 | 当前状态 | 结论 |
|---|---|---|
| P0：Mac 与真机环境 | 已完成 | 工程、签名、安装、启动、能力探针和真机测试通过 |
| P1：单手机采集闭环 | 最小版本通过 | 1 分钟真机同步采集通过；10 分钟稳定性测试待执行 |
| P2：UDP 与 CSI 最小闭环 | 未开始 | 应在 P1 的 10 分钟稳定性测试通过后开始 |
| P3：视频 SLAM 房间模型 | 未开始 | 仍需建立 COLMAP/SfM/稠密重建基线 |
| P4：统一坐标与联合数据集 | 未开始 | 依赖 P1、P2、P3 的数据和标定结果 |

## 3. 已完成工作

### 3.1 Mac、Xcode 与 iPhone 真机链路

- 已创建可运行的 SwiftUI iOS 工程；
- 工程同时包含 Xcode 工程和 XcodeGen `project.yml`；
- iPhone 11 Pro 已通过 USB 配对；
- iPhone 开发者模式已开启；
- Apple Personal Team 自动签名成功；
- App 已成功安装并在真机启动；
- 开发证书已恢复系统默认信任，私钥可以用于自动签名；
- XCTest 已在真机执行，5 项测试全部通过。

工程入口：

```text
apps/ios-recorder/WiTwinRecorder.xcodeproj
```

### 3.2 CapabilityProbe

当前能力探针能够：

- 记录设备型号、硬件标识、iOS 与 App 版本；
- 检查三项 ARKit 静态能力；
- 请求相机权限并启动 `ARWorldTrackingConfiguration`；
- 在支持时启用 `userFaceTrackingEnabled`；
- 等待世界跟踪达到 `normal`；
- 记录有效 `ARFrame` 的时间戳、相机内参、图像分辨率和世界变换；
- 记录观察到的 `ARFaceAnchor` 变换及对应帧时间戳；
- 记录相机设备、CoreMotion 可用性、存储空间和热状态；
- 将稳定排序、snake_case 字段的结果原子写入
  `Documents/capabilities.json`；
- 区分模拟器结果和真机能力证据。

### 3.3 iPhone 11 Pro 真机验证结果

测试设备为 iPhone 11 Pro（`iPhone12,3`），iOS 26.3.1。已经确认：

- `ARWorldTrackingConfiguration.isSupported == true`；
- `ARWorldTrackingConfiguration.supportsUserFaceTracking == true`；
- `ARFaceTrackingConfiguration.isSupported == true`；
- ARKit 世界跟踪实际达到 `normal`；
- ARFrame、1920 × 1440 图像、相机内参和世界变换均已取得；
- `userFaceTrackingEnabled` 可以启用；
- 实际观察到 `ARFaceAnchor`；
- 加速度计、陀螺仪、Device Motion 和磁力计均可用；
- 测试时热状态为 `nominal`。

P0 真机证据保存在：

```text
datasets/iphone11pro-p0-20260728/capabilities.json
```

这说明实施上下文中原本待验证的并发世界跟踪和人脸锚点能力已经通过 P0
检查。但是，P1 的 10 分钟稳定性测试和 P3 弱纹理房间重建尚未通过，因此仍不能声称
iPhone 11 Pro 已满足全部科研功能。

### 3.4 数据格式与测试基础

- `capabilities.json` 使用稳定的 snake_case 字段；
- 矩阵按行主序展开；
- 已明确 `target_T_source` 变换命名规则；
- 已修复带数字的 `3x3`、`4x4` JSON 字段解码问题；
- 已有 session schema、坐标系约定和 UDP 包格式；
- iOS Simulator、无签名 iPhoneOS 和真机签名构建均已验证；
- `WiTwinRecorderTests` 已在同一台 iPhone 11 Pro 上通过。

相关格式文件：

```text
schemas/session-format/session.schema.json
schemas/session-format/coordinate_frames.md
schemas/session-format/udp_probe_packet.md
```

### 3.5 P1 最小版本与 1 分钟真机结果

2026-07-29 已实现：

- `SessionRecorder` 统一状态机；
- HEVC/MOV 后置视频连续写入；
- 视频帧、ARFrame、位姿和 presentation timestamp 逐帧映射；
- 连续 `ar_frames.csv`、`imu.csv`、`face_anchors.csv` 和 `events.csv`；
- 固定装配编号、热状态和存储空间记录；
- `metadata.json`、`validation_report.json` 和 `checksums.sha256`；
- App 内自动完整性检查；
- Mac/Linux 离线复核脚本
  `apps/ios-recorder/scripts/check_p1_session.sh`；
- `session.schema.json` 1.1.0 的 `capture_stage` 条件约束，P1 不再要求虚假 CSI
  字段。

真机 1 分钟测试结果：

| 指标 | 结果 |
|---|---:|
| 元数据会话时长 | 60.18 秒 |
| 有效 AR/视频时长 | 59.70 秒 |
| ARFrame | 3583 |
| HEVC 视频帧 | 3583 |
| 视频写入丢帧 | 0 |
| 视频—位姿映射缺失率 | 0 |
| IMU 总样本 | 42050 |
| 各 IMU 流估计频率 | 约 100.02 Hz |
| 人脸锚点样本 | 2569 |
| 人脸有效跟踪占比 | 99.81% |
| ARFrame 最大间隙 | 0.0333 秒 |
| 最高热状态 | nominal |
| 自动检查 | 通过，0 错误、0 警告 |
| SHA-256 离线复核 | 全部通过 |

完整证据位于本地忽略目录：

```text
datasets/iphone11pro-p1-20260729/session_20260729_105114/
```

## 4. 尚未完成的关键部分

### 4.1 P1：单手机采集闭环

P1 最小版本与 1 分钟真机功能测试已经完成。仍需完成：

- 正式移动扫描路径下的 10 分钟稳定性测试；
- 统计 10 分钟内存、存储、温度、跟踪状态和丢帧；
- 根据压力测试结果修复问题并冻结 P1 数据格式。

### 4.2 P2：UDP 与 CSI

尚未实现：

- iPhone UDP 上行探测包；
- `udp_tx.csv`；
- PicoScenes/CSI 接收；
- 手机上行帧筛选；
- 手机时钟到 CSI 时钟的偏移和漂移拟合。

### 4.3 P3/P4：建模和统一坐标

尚未开始：

- COLMAP/SfM/稠密重建基线；
- ARKit 与视觉轨迹的 SE(3)/Sim(3) 对齐；
- 点云、网格和独立精度报告；
- 相机、手机机体、Wi-Fi 天线、人脸、人体和 CSI 接收端外参；
- WiTwin 数据加载器及联合数据集。

## 5. 已完成的实施方向

### 5.1 建立 SessionRecorder

已实现统一的采集会话状态机：

```text
idle -> preparing -> recording -> stopping -> completed/failed
```

每次采集建立独立目录：

```text
session_YYYYMMDD_HHMMSS/
├── metadata.json
├── capabilities.json
├── assembly.json
├── rear_video.mov
├── ar_frames.csv
├── face_anchors.csv
├── imu.csv
├── events.csv
├── validation_report.json
└── checksums.sha256
```

`session.schema.json` 已升级到 1.1.0。`capture_stage=phone_only_p1` 只要求
手机设备、手机装配和手机单调时基；只有 P2/P4 才条件要求 CSI 字段。

### 5.2 实现 RoomScanRecorder

采用：

- `ARWorldTrackingConfiguration`；
- `ARSessionDelegate`；
- `AVAssetWriter`；
- HEVC/MOV。

每个 ARFrame 已同时处理：

- 将 `capturedImage` 写入视频；
- 保存 `ARFrame.timestamp`；
- 保存 `ARCamera.transform`；
- 保存 `ARCamera.intrinsics`；
- 保存图像尺寸和 `trackingState`；
- 保存视频 presentation timestamp；
- 保存视频帧编号与 ARFrame 编号的映射。

不能使用系统相机 App 单独录像，因为这无法可靠建立视频帧与 ARKit 位姿的严格
对应关系。

### 5.3 并行加入 IMU 和人脸流

- 使用 CoreMotion 连续记录加速度计、陀螺仪和 Device Motion；
- 每条样本保存手机单调时钟时间戳；
- 持续记录 `ARFaceAnchor.transform` 和 `isTracked`；
- 记录人脸跟踪丢失与恢复事件；
- 保存固定的手机—夹具—稳定器装配编号。

### 5.4 1 分钟功能测试（已通过）

检查：

- 所有时间戳严格单调；
- 视频帧、ARFrame 和位姿没有明显断裂；
- 矩阵元素数量和有限性正确；
- 跟踪状态分布可以统计；
- 人脸跟踪丢失和恢复有记录；
- App 停止后所有文件正确关闭；
- 校验和正确；
- 没有崩溃、内存快速增长或严重发热。

### 5.5 进行 10 分钟稳定性测试（下一步）

至少统计：

- 实际采集时长；
- 视频帧数和平均帧率；
- ARFrame 数量；
- 视频—位姿映射缺失率；
- IMU 实际采样率；
- `normal`、`limited` 和 `notAvailable` 跟踪占比；
- 人脸锚点有效占比；
- 丢帧、时间戳间隙和写盘错误；
- 起止存储空间；
- 最高热状态；
- 是否因发热或后台状态退出。

只有 10 分钟测试通过后，才进入 P2 的 UDP/CSI 开发。

## 6. 下一里程碑

下一次开发里程碑更新为：

> 在正式移动扫描路径上完成 10 分钟后置视频、ARKit 位姿、IMU 和人脸锚点
> 同步采集，自动检查无错误，且无过热退出或明显写盘/跟踪断裂。

完成该里程碑后：

1. 修复稳定性和数据完整性问题；
2. 冻结 P1 数据格式；
3. 进入 UDP/CSI 最小闭环；
4. 同步建立 COLMAP 重建基线。

## 7. 保持不变的工程边界

- iPhone 11 Pro 没有后置 LiDAR；
- 不依赖 `sceneDepth`、`ARMeshAnchor`、RoomPlan 或 ARKit 场景网格；
- 房间模型必须主要来自后置视频、ARKit VIO/IMU 和离线视觉重建；
- `ARFaceAnchor` 可用于人体—手机相对几何，但不能假设主模式可取得前置原始
  TrueDepth 深度图；
- CSI 必须由外部 CSI 采集网卡获得；
- 主线物理链路保持为
  `iPhone 11 Pro -> CSI acquisition NIC`；
- 手机、CSI 和其他数据源没有天然共享硬件时钟，后续必须估计时钟偏移和漂移；
- 人工测距或 LiDAR 设备只能作为独立精度真值，不能代替视觉建模成为主要输入。

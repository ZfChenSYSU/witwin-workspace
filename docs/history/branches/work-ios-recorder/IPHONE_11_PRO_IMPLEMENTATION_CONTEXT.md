# iPhone 11 Pro 多模态采集与 SLAM 建模工程交接

更新时间：2026-07-27

适用工作区：`/opt/witwin`

关联计划：[前置深度增强的科研项目待办与验证计划](../../../current/project/前置深度增强的科研项目待办与验证计划.md)

## 1. 文档目的

本文固化围绕 iPhone 11 Pro 的设备选型、能力边界和工程实现结论，供后续在
Mac/Xcode、iPhone 真机、CSI 采集主机及 WiTwin 容器之间继续开发。

本文不是逐字聊天记录，不包含账号凭据、Cookie、令牌或签名证书。

## 2. 已确认的项目约束

1. 手机是移动无线发射端和多模态传感器平台。
2. 房间三维模型必须主要来自手机后置视频和手机移动时的传感器信息，通过
   SLAM/VIO、SfM 和稠密三维重建生成。
3. 人工测量或激光测距可以作为独立精度真值，但不能替代 SLAM/视觉重建成为
   房间模型的主要来源。
4. CSI 由支持 CSI 的外部网卡接收或监听手机上行帧后输出；手机本身不直接输出
   Wi-Fi CSI。
5. 主线物理链路必须表述为：

   ```text
   iPhone 11 Pro -> CSI acquisition NIC
   ```

6. 后置 RGB、VIO/SLAM 位姿、IMU、前置人脸几何和 CSI 没有天然共享硬件时钟，
   必须记录本地时间戳并估计时钟偏移与漂移。
7. 第一阶段将手机固定在稳定器或可重复夹具上，固定保护壳、夹持位置、方向和
   工作模式，把“手机—夹具—稳定器”视为一个完整的待标定发射端装配。

## 3. iPhone 11 Pro 的适用性结论

### 3.1 可以承担的任务

iPhone 11 Pro 可作为第一阶段原型设备，承担以下任务：

- 后置 RGB 视频采集；
- ARKit 世界跟踪和米制六自由度相机位姿；
- CoreMotion 原始或融合 IMU 数据采集；
- 前置 TrueDepth 支持的人脸三维跟踪；
- 在系统支持时，输出与世界坐标关联的 `ARFaceAnchor`；
- 通过 Wi-Fi 产生带序号和手机时间戳的 UDP 上行探测包；
- 为离线视觉 SLAM/SfM/多视图稠密重建提供后置视频、内参和位姿先验。

### 3.2 不具备的后置 LiDAR 能力

iPhone 11 Pro 没有后置 LiDAR，因此不能把下列能力作为主线依赖：

- ARKit 后置 `sceneDepth`；
- ARKit `smoothedSceneDepth`；
- `ARMeshAnchor` 场景网格；
- `sceneReconstruction` 直接房间网格；
- 基于后置 LiDAR 的 RoomPlan 房间扫描。

这不代表无法构建房间模型，而是模型必须采用后置视频、ARKit VIO/IMU 和离线
视觉重建生成。相较后置 LiDAR 设备，该路线对白墙、玻璃、弱纹理、运动模糊和
曝光变化更敏感，属于项目的前置高风险验证项。

### 3.3 前置深度的边界

主实验应优先使用：

```swift
let configuration = ARWorldTrackingConfiguration()
configuration.userFaceTrackingEnabled = true
```

该模式的目标是同时获得后置世界跟踪和前置人脸锚点。必须在 iPhone 11 Pro
真机和目标 iOS 版本上运行时检查：

```swift
ARWorldTrackingConfiguration.isSupported
ARWorldTrackingConfiguration.supportsUserFaceTracking
ARFaceTrackingConfiguration.isSupported
```

不能在完成真机测试前把并发跟踪稳定性写成已验证事实。

主实验可使用 `ARFaceAnchor.transform` 和人脸几何估计人体—手机相对几何，
但不应假设在后置世界跟踪配置中可以同时取得前置 TrueDepth 原始深度图。
如果研究必须使用原始面部深度，应增加独立的前置校准模式，例如基于
`ARFaceTrackingConfiguration` 采集；该模式不能替代后置房间扫描。

Apple 相关入口：

- <https://developer.apple.com/documentation/arkit/combining-user-face-tracking-and-world-tracking>
- <https://developer.apple.com/documentation/arkit/arworldtrackingconfiguration>
- <https://developer.apple.com/documentation/arkit/arfaceanchor>

## 4. iOS 采集端建议架构

建议将 iOS 应用分成四个模块，首版先保证数据正确和可追溯，不追求复杂 UI。

### 4.1 CapabilityProbe

启动时记录：

- iPhone 型号和 iOS 版本；
- ARKit 世界跟踪支持状态；
- 世界跟踪配置中的用户人脸跟踪支持状态；
- 人脸跟踪支持状态；
- 摄像头图像尺寸和内参；
- 可用存储空间；
- `ProcessInfo.thermalState`；
- 相机和运动传感器授权状态。

探针结果写入 `capabilities.json`，作为设备 Go/No-Go 的直接证据。

### 4.2 RoomScanRecorder

使用 `ARWorldTrackingConfiguration` 进行空房间或静态房间扫描，逐帧记录：

- `ARFrame.timestamp`；
- `ARFrame.capturedImage`；
- `ARCamera.transform`；
- `ARCamera.intrinsics`；
- `ARCamera.imageResolution`；
- `ARCamera.trackingState`；
- 曝光等可取得的图像元数据；
- 扫描开始、停止和人工事件标记。

视频建议通过 `AVAssetWriter` 写为 HEVC/MOV，同时保存视频帧与 ARKit 帧的映射。
不要用系统相机应用单独录像，否则难以保证视频帧与 ARKit 位姿严格对应。

### 4.3 HumanGeometryRecorder

在真机确认支持后，使用
`ARWorldTrackingConfiguration.userFaceTrackingEnabled = true`，记录：

- 世界坐标中的手机/相机六自由度位姿；
- 世界坐标中的 `ARFaceAnchor.transform`；
- `ARFaceAnchor.isTracked`；
- 必要时保存人脸网格或 blend shapes；
- 人脸跟踪丢失、恢复和质量状态；
- 手机固定装配编号。

关键相对变换为：

```text
camera_T_face = inverse(world_T_camera) * world_T_face
```

后续仍需标定：

- 后置相机坐标到手机机体坐标的关系；
- 手机机体到 Wi-Fi 有效天线参考点的关系；
- 前置人脸参考点到胸腔或简化人体模型参考点的关系；
- 手机—夹具—稳定器整体的装配重复性。

### 4.4 MotionAndTrafficRecorder

使用 CoreMotion 并行记录：

- 加速度计；
- 陀螺仪；
- `deviceMotion`；
- 每条样本的手机单调时钟时间戳。

使用 Network.framework 的 `NWConnection` 向固定主机发送 UDP 上行包，建议字段：

```text
magic | protocol_version | session_id | sequence | phone_timestamp | payload
```

包速率、载荷长度、目标 IP/端口必须可配置。首轮可从 100 包/秒开始，再根据
CSI 网卡和 PicoScenes 的稳定性调整。

## 5. 建议数据目录和字段

```text
session_YYYYMMDD_HHMMSS/
├── metadata.json
├── capabilities.json
├── assembly.json
├── rear_video.mov
├── ar_frames.csv
├── face_anchors.csv
├── imu.csv
├── udp_tx.csv
├── events.csv
├── calibration/
└── checksums.sha256
```

`ar_frames.csv` 至少包括：

```text
timestamp,frame_id,camera_4x4,fx,fy,cx,cy,width,height,tracking_state
```

`face_anchors.csv` 至少包括：

```text
timestamp,frame_id,face_4x4,is_tracked
```

`imu.csv` 至少包括：

```text
timestamp,sensor_type,x,y,z
```

所有矩阵必须在元数据中明确：

- 行主序或列主序；
- 左乘或右乘约定；
- 坐标轴方向；
- 单位；
- 变换命名规则，例如 `target_T_source`。

## 6. 房间视频 SLAM/三维重建链路

### 6.1 推荐基线

```text
后置视频 + ARKit VIO 位姿 + CoreMotion IMU
    -> 图像质量筛选与关键帧选择
    -> 视觉特征提取和顺序匹配
    -> SfM/视觉轨迹估计
    -> 与 ARKit 米制轨迹进行 SE(3)/Sim(3) 对齐
    -> 多视图稠密重建
    -> 点云清理、平面正则化和网格化
    -> 材料区域标注
    -> 导出 WiTwin 可使用的房间坐标模型
```

第一版离线基线可采用 COLMAP 的顺序匹配和稠密重建。ARKit 轨迹作为独立的
米制轨迹与视觉轨迹进行 Umeyama 对齐，先验证轨迹和尺度一致性，再决定是否把
ARKit 位姿作为更强的优化先验。

### 6.2 扫描规范

- 缓慢平移和转动，避免快速旋转；
- 相邻视角保持较高重叠，目标约 70% 以上；
- 绕房间形成闭环；
- 墙角、门窗和主要物体从多个倾斜角度覆盖；
- 避免扫描中途切换后置镜头；
- 尽量固定焦距、曝光策略和分辨率；
- 记录 ARKit tracking state，剔除严重失跟踪片段；
- 白墙或弱纹理区域可临时布置 AprilTag/ArUco 或可移除纹理纸；
- 玻璃、镜面、强反光面应单独标记为高风险区域。

临时视觉标记属于传感器辅助，不是用人工尺寸替代三维重建。生成模型后可清理
标记对应纹理或几何。

### 6.3 精度验证

激光测距、卷尺、已知尺寸标定物或后置 LiDAR 设备可以作为独立真值，评价：

- 关键距离相对误差；
- 墙面点到拟合平面的距离；
- 相邻墙面夹角误差；
- 闭环漂移；
- 重复扫描之间的点云/网格误差；
- 轨迹与房间模型的一致性。

这些真值只用于验证，不作为主要建模输入。

## 7. CSI 同步与统一时间轴

CSI 主机记录每个可识别手机上行帧的：

- CSI 设备时间戳；
- 主机接收时间；
- 手机 MAC、帧方向、信道和带宽；
- 子载波复数 CSI、RSSI 和射频链信息；
- 能够关联的 UDP `session_id` 和 `sequence`。

利用整个 session 中分布的匹配事件拟合手机时钟到 CSI 时钟的仿射映射：

```text
t_csi = a * t_phone + b
```

其中 `b` 表示偏移，`a` 表示漂移。不要只用开始时的一次对时，也不要按数组下标
直接配对 CSI、ARKit 和人脸数据。

实验 SSID 若启用 iOS 私有 Wi-Fi 地址，应记录 CSI 网卡实际观察到的 MAC。
可以为实验 SSID 固定该地址或在每个 session 元数据中记录，不能假设它永远等于
设备硬件地址。

## 8. Codex、USB 与 Apple 开发环境边界

仅把 iPhone 通过 USB 接到当前 Windows/WSL/Linux 容器，Codex 不能直接接管
iPhone。当前环境缺少：

- macOS；
- Xcode 和 `xcodebuild`；
- Apple 代码签名与 provisioning 工具；
- 可见的 iPhone USB 设备通道。

可靠开发拓扑为：

```text
Mac + Xcode + Codex
        |
       USB
        |
 iPhone 11 Pro

Git/private remote
        |
 /opt/witwin 离线建模与 WiTwin 环境
```

当 Codex 运行在连接真机的 Mac 上，并且具备项目目录和终端权限后，可以协助：

- 生成和修改 Swift/SwiftUI/ARKit 代码；
- 运行 `xcodebuild`；
- 使用 `xcrun devicectl` 安装、启动和读取日志；
- 运行 XCTest/XCUITest；
- 分析崩溃、权限和性能问题。

下列动作仍需用户本人完成：

- 解锁 iPhone；
- 确认“信任此电脑”；
- 开启开发者模式并按系统要求重启；
- 在 Xcode 中登录 Apple ID；
- 选择开发团队和处理首次签名；
- 确认系统权限或证书弹窗。

USB 连接不等价于允许任意操作手机 UI，也不能绕过 Apple 的信任和签名机制。

OpenAI 的 iOS 工程参考：

- <https://learn.chatgpt.com/use-cases/native-ios-apps>

## 9. 分阶段实施与通过标准

### P0：Mac 与真机环境

交付物：

- 可运行的空白 iOS 工程；
- 真机签名和安装成功；
- CapabilityProbe 输出。

通过标准：

- `xcodebuild` 成功；
- 应用可在 iPhone 11 Pro 启动；
- 三项 ARKit 能力检查结果已保存。

### P1：单手机采集闭环

交付物：

- 10 分钟后置视频、ARKit 位姿和 IMU 数据；
- 人脸锚点测试数据；
- 数据完整性检查脚本。

通过标准：

- 视频帧和位姿映射无明显断裂；
- 跟踪状态和丢帧可统计；
- 人脸位姿随已知距离和方向变化正确；
- 长时间采集不过热退出、不耗尽存储。

### P2：UDP 与 CSI 最小闭环

交付物：

- 手机 UDP 发送日志；
- PicoScenes/CSI 原始数据；
- 手机上行帧筛选结果；
- 时钟偏移和漂移拟合报告。

通过标准：

- 手机上行帧可稳定识别；
- CSI 丢包和字段完整性可量化；
- `phone -> CSI acquisition NIC` 物理含义明确；
- 时间对齐残差达到后续实验要求。

### P3：视频 SLAM 房间模型

交付物：

- 一次完整房间扫描 session；
- 稀疏与稠密点云；
- 房间网格；
- ARKit 与视觉轨迹对齐结果；
- 独立精度验证报告。

通过标准：

- 模型尺度正确；
- 主要墙、地面、门窗可以稳定恢复；
- 重复扫描误差可接受；
- 失败区域和重扫规范明确。

### P4：统一坐标与联合数据集

交付物：

- 相机、手机机体、Wi-Fi 天线、人脸/胸腔、CSI 接收天线和房间坐标外参；
- 同一时间轴上的 CSI、手机位姿和人体几何；
- 可供 WiTwin/可微射线追踪使用的数据加载器。

通过标准：

- 任一 CSI 样本可追溯到对应的手机位姿、人体几何和装配配置；
- 坐标变换闭环误差已量化；
- 跨 session 装配和测量重复性已验证。

## 10. 当前 Go/No-Go 判断

当前结论为“有条件 Go”：

- iPhone 11 Pro 足以启动后置视频/VIO、IMU、前置人脸锚点和 UDP/CSI 的工程验证；
- 房间模型必须走离线视觉 SLAM/SfM/稠密重建路线；
- 后置 LiDAR 不是算法定义上的必需条件，但缺少它会显著提高房间重建的工程风险；
- 在 P0/P1 真机并发跟踪和 P3 弱纹理房间重建通过前，不能声称 iPhone 11 Pro
  已经满足全部科研功能；
- 如果 P3 在目标房间反复失败，再评估借用带后置 LiDAR 的 iPhone Pro/iPad Pro
  作为对照或辅助真值设备，而不是预先改变主线设备。

## 11. 与 WiTwin 当前环境的衔接限制

当前已验证组合：

- WiTwin Core 0.0.2；
- WiTwin Channel 0.1.0；
- RayD 0.4.0；
- DrJit 1.3.1；
- PyTorch 2.10.0+cu128。

确定性 LOS、CIR 和 CFR 已通过。`max_bounces > 0` 的反射路径尚未在当前上游组合
中完成验证。因此，即使手机采集、房间模型和 CSI 数据闭环已经完成，也不能把
当前 WiTwin 环境描述为已通过完整多次反射信道验证。涉及依赖升级时必须先做兼容
性评估，并重新运行：

```bash
/opt/witwin/venv/bin/python /opt/witwin/validate_witwin.py
```

## 12. 下一步最小行动

1. 准备可连接 iPhone 11 Pro 的 Mac 和 Xcode。
2. 创建可复现生成的 iOS 工程，优先考虑 XcodeGen 或 Tuist 管理工程结构。
3. 先实现 CapabilityProbe，不立即堆叠全部功能。
4. 真机确认 ARWorldTracking 和用户人脸跟踪并发能力。
5. 实现 1 分钟、10 分钟两档 RoomScanRecorder 稳定性测试。
6. 再接入 CoreMotion、UDP 发送和 CSI 主机。
7. 在 `/opt/witwin` 建立离线数据检查和 COLMAP 重建基线。
8. 每一阶段保存原始数据、配置、软件版本、装配照片和校验和，避免只保留处理后
   结果。

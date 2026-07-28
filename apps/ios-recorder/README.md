# iOS Recorder

此目录用于 Mac/Xcode 上开发 iPhone 11 Pro 多模态采集应用，对应工作分支
`work/ios-recorder`。

## 职责

- ARKit 后置世界跟踪、RGB 帧、相机内参和六自由度位姿；
- CoreMotion 加速度计、陀螺仪和 device motion；
- 支持时启用前置用户人脸跟踪并记录 `ARFaceAnchor`；
- 发送带协议版本、序号和手机单调时间戳的 UDP 上行探测包；
- 按 `schemas/session-format/` 写出可校验的 session。

## 工程边界

iPhone 11 Pro 没有后置 LiDAR，不依赖 `sceneDepth`、`ARMeshAnchor`、RoomPlan 或
ARKit 场景网格。房间模型由后置视频、VIO/IMU 和离线重建流水线生成。

主应用正式建立前，先实现能力探针并在目标 iOS 版本真机检查：

```swift
ARWorldTrackingConfiguration.isSupported
ARWorldTrackingConfiguration.supportsUserFaceTracking
ARFaceTrackingConfiguration.isSupported
```

推荐后续使用 XcodeGen 或 Tuist 保存可复现工程定义，避免只提交某台 Mac 的本地
Xcode 状态。`DerivedData/` 和本地构建产物已被 Git 忽略。

## 当前实现

已建立 `WiTwinRecorder.xcodeproj`、共享 Scheme 和对应的 `project.yml`。当前
P0 能力探针会：

- 记录设备型号、硬件标识、iOS 与 App 版本；
- 检查三项 ARKit 静态能力；
- 请求相机权限并启动 `ARWorldTrackingConfiguration`；
- 在支持时启用 `userFaceTrackingEnabled`，等待 `ARFaceAnchor` 或超时；
- 记录首个有效 `ARFrame` 的时间戳、相机内参、图像分辨率和世界变换；
- 记录观察到的人脸锚点变换及其对应帧时间戳；
- 记录相机设备、CoreMotion 可用性、存储空间和热状态；
- 将稳定排序、snake_case 字段的结果原子写入
  `Documents/capabilities.json`，并在界面中提供系统分享入口；
- 明确标记模拟器结果不能作为 iPhone 11 Pro 真机能力证据。

`capabilities.json` 是设备能力探针，不替代完整 session 的
`schemas/session-format/session.schema.json`。

## 打开与构建

直接在 Xcode 中打开：

```text
apps/ios-recorder/WiTwinRecorder.xcodeproj
```

无需签名的 SDK 编译检查：

```bash
cd apps/ios-recorder
xcodebuild \
  -project WiTwinRecorder.xcodeproj \
  -scheme WiTwinRecorder \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  ARCHS=arm64 \
  ONLY_ACTIVE_ARCH=YES \
  build
```

测试 Target 编译检查将末尾的 `build` 换成 `build-for-testing`。

如果 Mac 已安装 XcodeGen，可以在修改 `project.yml` 后重新生成工程：

```bash
cd apps/ios-recorder
xcodegen generate
```

生成后应重新执行构建和测试，避免只验证 YAML 或只验证已生成工程。

## 当前验证状态（2026-07-28）

- iOS Simulator 26.5 SDK、arm64、Debug App 构建通过；
- `WiTwinRecorderTests` 测试 Target 的 `build-for-testing` 通过；
- iPhoneOS 26.5 SDK、arm64、无签名 Debug 构建通过；
- `CapabilityReport` 的 snake_case JSON 编码、解码和等值往返冒烟测试通过；
- Personal Team 自动签名、真机安装、开发者信任和 App 启动通过；
- iPhone 11 Pro（`iPhone12,3`，iOS 26.3.1）三项 ARKit 静态能力均为 `true`；
- 真机相机权限、1920 × 1440 ARFrame、相机内参和世界变换已取得；
- 世界跟踪达到 `normal`，并发用户人脸跟踪已启用且 `ARFaceAnchor` 已取得；
- 加速度计、陀螺仪、Device Motion 和磁力计均报告可用，热状态为 `nominal`；
- 真机证据保存在本地忽略目录
  `datasets/iphone11pro-p0-20260728/capabilities.json`；
- 开发证书已恢复系统默认信任，个人证书私钥授权可正常用于自动签名；
- `WiTwinRecorderTests` 已在同一台 iPhone 11 Pro 上执行，2 项测试全部通过，
  包括带数字的 `3x3`、`4x4` snake_case 字段解码和 JSON 等值往返。

## 真机验证

真机接入步骤和 P0 通过条件见
[`TRUE_DEVICE_CHECKLIST.md`](TRUE_DEVICE_CHECKLIST.md)。在生成并导出真实
`capabilities.json` 前，只能认为工程“编译通过”，不能认为设备能力或并发跟踪
已经通过。

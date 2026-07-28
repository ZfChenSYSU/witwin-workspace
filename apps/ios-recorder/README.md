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

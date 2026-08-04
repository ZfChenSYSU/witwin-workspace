# iPhone 11 Pro P0 真机检查

## 首次连接

1. 用 USB 将 iPhone 11 Pro 连接到 Mac，解锁手机并确认“信任此电脑”。
2. 在 iPhone 的“设置 > 隐私与安全性 > 开发者模式”中开启开发者模式，并按系统
   要求重启。
3. 在 Xcode 的 Settings > Accounts 登录 Apple ID。
4. 打开 `WiTwinRecorder.xcodeproj`，选择 `WiTwinRecorder` Target，在
   Signing & Capabilities 中选择自己的 Team。
5. 如果 `org.witwin.recorder` 与现有 App ID 冲突，将 Bundle Identifier 改成自己
   唯一的反向域名；同时同步修改 `project.yml`。
6. 在 Xcode 顶部选择已连接的 iPhone 11 Pro，然后执行 Product > Run。

## 运行探针

1. 首次启动时允许相机访问；如果系统出现运动与健身权限提示，也选择允许。
2. 保持手机屏幕和前置摄像头朝向实验人员、后置摄像头朝向有纹理且光照充足的
   房间区域。
3. 点击“运行并保存能力探针”，保持人脸可见，等待完成或 8 秒超时。
4. 点击“导出 capabilities.json”，保存到实验数据目录。
5. 不要用截图替代 JSON 原文件。

## P0 自动字段检查

真实结果至少应满足或给出明确失败原因：

- `execution_environment.is_simulator == false`；
- `device.model_identifier == "iPhone12,3"`（iPhone 11 Pro）；
- `arkit.world_tracking_supported == true`；
- `arkit.world_tracking_supports_user_face_tracking` 已记录；
- `arkit.face_tracking_supported` 已记录；
- `runtime_validation.ar_frame_received == true`；
- `runtime_validation.ar_frame_timestamp_seconds` 非空；
- `runtime_validation.world_transform4x4_row_major` 有 16 个有限数值；
- `camera.intrinsics3x3_row_major` 有 9 个有限数值；
- 图像尺寸和 `ARCamera.imageResolution` 非空；
- 如果并发人脸跟踪受支持，
  `runtime_validation.face_anchor_observed == true`；
- 如果观察到人脸锚点，人脸变换有 16 个有限数值且对应帧时间戳非空；
- 可用存储空间和热状态已记录。

所有矩阵按行主序展开，变换命名遵循
`schemas/session-format/coordinate_frames.md`。本探针中的相机变换对应
`arkit_world_T_rear_camera`，人脸锚点变换对应
`arkit_world_T_face_anchor`。

## 人工检查和失败记录

- 在 Xcode 控制台确认没有 ARSession、权限或内存错误。
- 若状态为 `face_anchor_timeout`，记录光照、人脸是否被遮挡、手机方向和 iOS
  版本后重试，不能直接写成“不支持”。
- 若三项静态能力为真但运行时失败，保留 JSON 和 Xcode 日志；静态 API 返回值
  不能替代运行时稳定性。
- 首次成功只完成 P0。随后仍需分别进行 1 分钟和 10 分钟采集稳定性测试。

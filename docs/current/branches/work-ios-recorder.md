# `work/ios-recorder` 分支当前状态

更新时间：2026-09-09

## 当前结论

P0 真机环境、P1 单手机采集功能闭环和 P2 Recorder 同进程 UDP 联合采集已在
iPhone 11 Pro 上通过。当前路线改用带后置 LiDAR 的 iPhone；旧结果作为 RGB、ARKit、
CoreMotion、人脸跟踪与 UDP 的回归基线，不能代替新设备验收。

Session Schema 已升级到 1.4.0，App 版本升级到 0.5.0。视频方向/编码/像素格式、
ARKit 矩阵约定、CoreMotion 单位与参考系、构建来源现已机器可读；
`video_frame_id` 只对成功写入 MOV 的样本连续编号，失败样本记为 `-1`。
`face_anchors.csv` 直接保存逐样本 `face_distance_m`，并要求 `frame_id` 与同时间戳
ARFrame 严格一致。

已验证的代表性结果包括：

- 1 分钟 P1 session 中视频和 ARKit 各 3583 帧，视频丢帧与位姿映射缺失均为 0；
- IMU 各流约 100 Hz，该次人脸有效跟踪率为 99.81%；
- 60 秒 P2 联合 session 中视频、ARKit、IMU 和 UDP 同期运行，完整性检查通过；
- 采集 App、schema、校验和和离线检查脚本已经形成基础闭环。
- 2026-08-06 的 5 秒真机 session 实际出现 2 个未写入视频帧，MOV 解码 238 帧与
  238 个成功样本逐一一致；该 session 上传 WSL 后导入检查零错误、零警告通过。
- P1/P2 采集期间现可在前台显示非全屏后置摄像头预览；预览从 Recorder 的同一
  `ARFrame.capturedImage` 异步降采样生成，不另启后置相机会话。录制期间前台距离、
  `ARFaceAnchor` 与后置视频统一使用 Recorder 的同一个 ARSession；待机测距会在
  开始/停止边界切换，不与正式采集竞争相机资源。
- 2026-08-07 的 App 0.5.0 / Schema 1.4.0 真机交互回归通过：15.18 秒内生成
  912 个 ARKit/视频样本、0 丢帧、11,124 条 IMU 和 762 条人脸记录；761 条有效
  距离与同帧位姿重算最大误差约 `4.0e-8 m`，人脸—ARFrame 时间戳差为 0，
  三类数据共同覆盖 14.61 秒，事件中没有 ARKit 中断，MOV 解码得到 912 个样本。

## 当前缺口

- 人脸锚点尚未通过外部真值换算为可靠的胸腔/人体参考点 `r_t`；
- 前摄像头—Wi-Fi 天线外参、头部姿态影响和人体几何协方差尚未完成标定；
- 正式移动房间扫描和更长压力测试仍需在 P3 数据需求明确后执行；
- 目标 LiDAR iPhone 型号、iOS 版本和存储容量尚未确认；
- App 尚未定义和导出场景深度、置信度、场景网格或 RoomPlan 数据；
- Session Format 1.4 尚未表达 LiDAR 文件、标定、时间关联和质量语义；
- 当前 5 秒自动测试只作为链路 smoke，不作为首次 COLMAP 建模输入；iPhone 视频
  建模按当前决定暂缓。
- 正式构建尚未注入 40 位 workspace commit，当前测试构建明确记录为 `unknown`。
- 单 ARSession 的 15 秒联合回归已通过，仍需完成 1 分钟移动扫描与低照度/遮挡
  压力回归。

## 下一步

1. 在目标 LiDAR iPhone 上运行能力探针，确认 `sceneDepth`、mesh、RoomPlan、前置
   人脸跟踪和后置采集并发边界。
2. 用最小样例确定首版 LiDAR 输出及 RGB—深度—位姿关联，再版本化扩展 schema。
3. 更新 App 编码、完整性校验和离线检查，并保留旧 1.4 session 兼容性。
4. 按扫描规范采集带人工尺寸真值的 30–60 秒 session，完成低纹理、遮挡、移动过快、
   tracking limited、起止静止和回环压力测试。
5. 冻结手机—保护壳—夹具—稳定器装配编号、相机与 LiDAR 配置。
6. 完成人脸—胸腔和相机—天线外参标定，并为 CSI 时间轴提供稳定的 ARKit/IMU
   查询接口和缺失区间标志。
7. 保持原始观测与滤波结果分离，不在手机端伪造统一时钟或人体真值。

历史证据见 [iOS 历史进度](../../history/branches/work-ios-recorder/) 和 [P2 跨端报告](../../history/integration/2026-07/)。
本轮建模联调证据和下一步见
[iPhone 到 WSL 建模执行分析](../../history/integration/2026-08/iPhone到WSL建模执行分析与下一步_2026-08-06.md)。
当前设备迁移任务见
[LiDAR iPhone 与 WiTwin 服务器迁移计划](../project/LiDAR与服务器迁移计划.md)。

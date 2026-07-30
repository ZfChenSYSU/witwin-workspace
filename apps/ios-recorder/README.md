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
App 版本为 0.3.0。

### P0 能力探针

能力探针会：

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

### P1 同步采集

`SessionRecorder` 实现：

- `idle -> preparing -> recording -> stopping -> completed/failed` 状态机；
- 每次建立独立的 `Documents/Sessions/session_YYYYMMDD_HHMMSS/`；
- 使用同一个 `ARFrame.capturedImage` 写入 HEVC/MOV 并生成逐帧映射；
- 连续保存 ARKit 世界位姿、内参、图像尺寸和 tracking state；
- 以 100 Hz 目标频率记录加速度计、陀螺仪和 Device Motion；
- 持续保存 `ARFaceAnchor.transform`、`isTracked` 和跟踪事件；
- 保存装配编号、人工标记、热状态和起止可用存储空间；
- 停止后生成 `metadata.json`、`validation_report.json` 和
  `checksums.sha256`；
- App 进入后台或热状态达到 `critical` 时主动停止并封装数据。

P1 session 目录包含：

```text
metadata.json
capabilities.json
assembly.json
rear_video.mov
ar_frames.csv
face_anchors.csv
imu.csv
events.csv
validation_report.json
checksums.sha256
```

公共 session schema 已升级到 1.2.0，并用 `capture_stage=phone_only_p1` 明确
P1 不需要伪造 CSI 设备、装配或时基。

### P2 直连 IP UDP 上行

App 已加入独立 UDP 测试和 Recorder 同进程集成：

- 手机端可自由填写目标 IPv4/主机名和 UDP 端口；
- 首轮默认目标为 `192.168.3.31:5201`；
- 正式数据流前发送 WTWN HELLO，只有收到 Linux 接收器 ACK 才开始发包；
- 独立测试默认以 2 Mbit/s、1200 字节数据报运行，时长从 ACK 后开始计算；
- Recorder 可勾选“同时发送 P2 UDP 上行”，视频、ARKit、IMU、人脸锚点和
  UDP 在同一 App 进程及同一 session 中记录；
- `udp_tx.csv`、ARKit 回调、IMU 回调和人脸锚点回调均记录同源的手机单调
  纳秒时钟；
- P2 session 使用 `capture_stage=phone_udp_p2`，停止后同样生成完整性报告与
  SHA-256。

PicoScenes/Linux 端先启动 ACK 接收器：

```bash
/opt/witwin/venv/bin/python /opt/witwin/capture/csi-linux/udp_probe_receiver.py \
  --bind 0.0.0.0 \
  --port 5201 \
  --output /opt/witwin/capture/csi-linux/raw/udp_probe.csv
```

看到 `WTWN UDP receiver listening` 后，再在手机点击“开始发包”。iPerf3 TCP
5201 可以与 WTWN UDP 5201 并存；iPerf3 UDP 与 WTWN UDP 不能同时绑定 UDP
5201。

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

## 当前验证状态（2026-07-30）

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
- `WiTwinRecorderTests` 已在同一台 iPhone 11 Pro 上执行：7 项常规测试通过，
  2 项实时网络用例默认由安全开关跳过；
- 5 秒真机端到端采集冒烟测试通过；
- 1 分钟真机 P1 测试通过：60.18 秒、3583 个 ARFrame、3583 个视频帧、
  0 丢帧、42050 条 IMU 样本；
- 各 IMU 数据流约 100.02 Hz；
- 取得 2569 条人脸锚点样本，有效跟踪占比 99.81%；
- 测试期间最高热状态为 `nominal`，自动报告无错误、无警告；
- 完整 1 分钟证据保存在本地忽略目录
  `datasets/iphone11pro-p1-20260729/session_20260729_105114/`。
- 2026-07-30 直连 `192.168.3.31:5201` 的 10 秒独立 UDP 真机测试通过：
  2083 包全部本地发送成功、0 失败、约 1.999 Mbit/s；
- 5 秒 `phone_udp_p2` 联合真机测试通过：260 个 AR/视频帧、0 视频丢帧、
  3506 条 IMU、1035 个 UDP 本地成功包、1 个停止阶段取消包、序号缺口 0；
- P2 手机端证据保存在
  `datasets/iphone11pro-p2-udp-20260730/` 和
  `datasets/iphone11pro-p2-integrated-20260730/`。

## 离线完整性复核

App 会在停止时自动检查。导出 session 后还可以在 Mac/Linux 复核 CSV 与
SHA-256：

```bash
apps/ios-recorder/scripts/check_p1_session.sh \
  datasets/iphone11pro-p1-20260729/session_20260729_105114
```

## 真机验证

真机接入步骤和 P0 通过条件见
[`TRUE_DEVICE_CHECKLIST.md`](TRUE_DEVICE_CHECKLIST.md)。在生成并导出真实
`capabilities.json` 前，只能认为工程“编译通过”，不能认为设备能力或并发跟踪
已经通过。

P1 最小里程碑与 1 分钟真机功能测试已经通过；当前不把 10 分钟测试作为进入 P2
的前置条件。P2 的直连 IP、HELLO/ACK、独立 UDP 和 Recorder 同进程联合采集均已
通过真机测试。下一步是保存并对照 Linux 接收日志与手机日志，再在 PicoScenes
结果中筛选上行帧并建立手机时钟到 CSI 时钟的偏移/漂移模型。

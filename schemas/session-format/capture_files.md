# iPhone 采集文件契约

本文定义 Schema 1.3.0 下 `rear_video.mov`、`ar_frames.csv` 和 `imu.csv` 的机器
语义。所有 CSV 使用 UTF-8、首行为表头，布尔值写为 `true`/`false`，原始记录
不得在采集端插值或静默修复。

## rear_video.mov 与 ar_frames.csv

视频来自同一回调中的 `ARFrame.capturedImage`，Recorder 不额外裁剪、缩放、镜像
或启用独立稳像。实际编码、源像素 FourCC、尺寸、方向和策略写在
`metadata.capture.video`。服务器仍须使用 ffprobe 核对容器中的实际信息。

`ar_frames.csv` 固定列为：

```text
timestamp_seconds,callback_phone_monotonic_ns,frame_id,video_frame_id,
video_pts_seconds,video_appended,
world_T_rear_camera_00..world_T_rear_camera_33,
intrinsics_00..intrinsics_22,image_width,image_height,tracking_state
```

- `timestamp_seconds`：`ARFrame.timestamp`，单位秒，系统启动后的单调时基。
- `callback_phone_monotonic_ns`：回调收到帧时的 `DispatchTime` uptime 纳秒。
- `frame_id`：所有 ARFrame 的零基连续编号。
- `video_frame_id`：MOV 中成功样本的零基连续编号；`video_appended=false` 时为
  `-1`，失败帧不占用编号。
- `video_pts_seconds`：相对首个 ARFrame 的视频 PTS，单位秒。
- 位姿矩阵：`arkit_world_T_rear_camera` 的行主序展开，右手系、米。
- 内参矩阵：`frame.camera.intrinsics` 的行主序展开，对应同行的
  `frame.camera.imageResolution`。

## imu.csv

固定列为：

```text
timestamp_seconds,callback_phone_monotonic_ns,sample_id,sensor_type,x,y,z,w,accuracy
```

`timestamp_seconds` 是对应 CoreMotion 样本的单调秒时间；`sample_id` 是跨流写入
顺序的连续编号。`w` 仅用于四元数，顺序固定为 `x,y,z,w`。各流语义由
`metadata.capture.motion.streams` 声明，当前定义为：

| sensor_type | 单位 | 参考系/语义 |
| --- | --- | --- |
| `accelerometer` | g | device body |
| `gyroscope` | rad/s | device body |
| `device_motion_user_acceleration` | g | device body |
| `device_motion_rotation_rate` | rad/s | device body |
| `device_motion_gravity` | g | device body |
| `device_motion_attitude_quaternion` | unitless | 相对 `xArbitraryZVertical` 的设备姿态 |
| `device_motion_magnetic_field` | µT | device body；`accuracy` 保存标定等级 |

请求频率当前为 100 Hz；实际频率必须由时间戳重新估计。缺流、间隙和中断必须在
导入报告中显式呈现，不能把请求频率当作实际频率。

## 构建来源

`metadata.source.workspace_commit` 为 40 位提交哈希；若构建流程没有注入则明确写
`unknown`。`build_identifier` 至少组合 bundle identifier、App 版本和 build 号。
正式验收构建应通过 `WITWIN_WORKSPACE_COMMIT` 注入可追溯提交。

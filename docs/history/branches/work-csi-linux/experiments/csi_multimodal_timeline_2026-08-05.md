# CSI—ARKit—IMU 时间轴物化验证

验证日期：2026-08-05

## 1. 结论

`work/csi-linux` 已实现 `materialize_csi_timeline.py`，能够把 PicoScenes CSI
设备时间反解到 iPhone 单调时间，并为每条 CSI 关联：

- 最近的 ARKit 测量帧、相机位姿、视频帧和 tracking state；
- 指定时间窗内的 CoreMotion 原始样本；
- 时钟映射、输入文件、设备组合和适用时间的完整来源信息。

工具已用 `session_20260730_170429` 与 Linux 同期采集
`phone-recorder-csi-20260730-v1` 完成真实数据验证。191 条 CSI 全部获得有效
ARKit 和 IMU 关联。

本次 60 秒 session 的时钟映射仍是固定单位斜率，
`drift_fit_reliable=false`。工具保留这一警告，不把物化成功解释为硬件同步或
可靠漂移已经在该 session 内重新估计。

## 2. 数据与设备组合

- iPhone session：`session_20260730_170429`
- 手机：iPhone 11 Pro，`iPhone12,3`，iOS `26.3.1`
- App：WiTwinRecorder `0.3.0 (1)`
- 手机 Wi-Fi MAC：`86:d7:cd:37:90:4c`
- AP/BSSID：`e4:4e:12:ae:fe:07`
- 信道：2442 MHz，20 MHz
- CSI 网卡 MAC：`4c:5f:70:73:f2:5d`
- PicoScenes interface index：2
- CSI 形状：`245×1×2×1`、`245×2×2×1`
- WTWN session hash：`569fc0c3bfbd0461`

本地验证目录：

```text
datasets/iphone11pro-p2-csi-linux-20260730/
  phone-recorder-csi-20260730-v1/
    iphone_session/
    linux_capture/
    timeline-v2/
```

数据目录受 Git 忽略。因 ARKit 轨迹属于敏感实验数据，本次将 Linux CSI 输入下载
到 Mac 与手机文件本地汇合，没有把 ARKit/IMU 上传到远端主机。

## 3. 时间定义

已有映射定义为：

```text
t_csi_device_ns = scale * t_phone_monotonic_ns + offset_ns
```

物化时反解：

```text
t_phone_monotonic_ns =
    (t_csi_device_ns - offset_ns) / scale
```

ARKit 和 CoreMotion 关联使用传感器测量时刻：

```text
round(timestamp_seconds * 1e9)
```

`callback_phone_monotonic_ns` 发生在测量之后，只用于回调延迟诊断，不参与最近邻
或时间窗关联。真实数据中 ARKit 回调延迟 P50 为 36.017 ms、P95 为
43.539 ms；若错误使用回调时间，会引入不可忽略的系统偏差。

## 4. 输出契约

### `csi_timeline.csv`

每条 CSI 对应一行，包含：

- CSI 设备时间、Linux 系统时间和反解后的手机单调时间；
- 原始 CSI 包元数据、RSSI、PHY 参数、数组分组和索引；
- 最近 ARKit 帧及其测量时间差；
- `world_T_rear_camera`、视频帧、内参和 tracking state；
- IMU 窗口起止时间、样本数和传感器类型数。

### `csi_imu_links.csv`

记录 CSI 与时间窗内每条 CoreMotion 原始样本的多对多关系，保留 source line、
sample ID、sensor type、测量值和相对 CSI 的有符号时间差。

### `timeline_manifest.json`

记录：

- clock mapping SHA-256、方法、斜率、偏移、残差和可靠性标志；
- 所有输入及两个 CSV 输出的 SHA-256 与大小；
- 手机、App、Wi-Fi 发射端、AP、CSI 网卡、信道和 CSI 形状；
- CSI、ARKit、IMU 三条时间轴的适用范围；
- ARKit/IMU 关联误差、tracking state、参数、限制和警告。

## 5. 真实结果

默认参数：ARKit 最大间隔 50 ms，IMU 窗口为 CSI 时刻前后各 10 ms。

| 指标                      |             结果 |
| ------------------------- | ---------------: |
| CSI 行数                  |              191 |
| ARKit 有效匹配            |          191/191 |
| 匹配 ARKit tracking state | 191 条`normal` |
| ARKit 绝对时间差 P50      |         3.647 ms |
| ARKit 绝对时间差 P95      |         7.694 ms |
| ARKit 绝对时间差最大值    |         8.169 ms |
| 含 IMU 样本的 CSI         |          191/191 |
| CSI—IMU 链接             |            2,674 |
| 每类 IMU 链接             |              382 |
| IMU 绝对时间差 P50        |         4.999 ms |
| IMU 绝对时间差 P95        |         9.413 ms |

7 类 IMU 均被关联：accelerometer、gyroscope、device motion 的 user
acceleration、rotation rate、gravity、attitude quaternion 和 magnetic field。

## 6. 关键 SHA-256

| 文件                       | SHA-256                                                              |
| -------------------------- | -------------------------------------------------------------------- |
| `clock_mapping.json`     | `e60105a8e599f0e3f2804708a8cae2989e8271065f79ba50bc2a77bcbe918d19` |
| `csi_packets.csv`        | `849dbfe854e02f0036af9c88014f80a83a5545fc0469bd81f36b910e22c00ee3` |
| `ar_frames.csv`          | `eaf368c3cea6872d3a2bf2b51f553c06076432c3b9b857a194afba91341af579` |
| `imu.csv`                | `04591bf7fcd6a94cf7ecc49c9e54c4e59d096b7d9be7003353897c26d3318969` |
| `metadata.json`          | `59c895e9d049ee4badc971d44fb333b4876fd1e3f4f553e577ae3844ebb5bc45` |
| `csi_timeline.csv`       | `b288dd6f6baedc09679135462bb6a67ed3ba7ad32bb0dfbc901e0da9be8206ee` |
| `csi_imu_links.csv`      | `fca92c08b2ad5dbdc14b04c8fa974ed4afb6a508d53584269be86f562b0938a7` |
| `timeline_manifest.json` | `0aca8d901c508d67df16a040248d6b260b169103ce53f966494407221857e4d8` |

## 7. 测试与边界

Linux `/opt/witwin/venv-picoscenes` 中 8 项测试通过，包括原有 5 项时钟拟合测试和
新增 3 项时间轴测试。新增测试覆盖：

1. CSI 反解、ARKit 最近邻、IMU 窗口及来源哈希；
2. CSI 与 ARKit 时间窗不重叠时显式拒绝；
3. 漂移不可靠、ARKit 超差或 IMU 缺失时显式警告。

当前限制：

- 60 秒真实 session 的有效 CSI 时间跨度不足 60 秒，斜率固定为 1；
- 软件时钟桥不是硬件同步；
- 一条 UDP 与一条 CSI 不存在机械一一对应关系；
- CSI 相位尚未完成跨 session 校准。

## 8. 下一步

1. 采集至少 3 组相同位置和装配的重复 session；
2. 每组保留采集前后静态参考段，并记录装配标识；
3. 统计跨 session 的 CSI 密度、ARKit/IMU 关联误差、时钟残差和漂移；
4. 将 `csi_timeline.csv` 接入 WSL 统一数据加载器；
5. 相位校准通过前，真实主线继续优先使用幅度、RSSI 和包级时间信息。

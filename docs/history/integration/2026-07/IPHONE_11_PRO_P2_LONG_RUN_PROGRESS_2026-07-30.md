# iPhone 11 Pro P2 长时与 Recorder 同进程联合采集进度

验证日期：2026-07-30

本文是
[P2 PicoScenes/CSI 联合采集报告](IPHONE_11_PRO_P2_CSI_SMOKE_2026-07-30.md)
之后的新进度记录。未覆盖或修改
[iPhone 11 Pro 工程进度](../../branches/work-ios-recorder/2026-07/IPHONE_11_PRO_PROGRESS_2026-07-28.md)。

## 1. 当前结论

P2 已完成以下两个连续里程碑：

1. 150 秒独立 UDP/CSI 基准测试取得可靠的手机时钟漂移估计；
2. 60 秒 `SessionRecorder` 同进程测试同时生成视频、ARKit、IMU 和 UDP 日志，
   Linux 同期接收 UDP 并由 PicoScenes 导出手机上行 CSI。

因此，“iPhone 原生采集与 UDP 发包必须处于同一个 App/进程，且使用同一手机单调
时间基准”的实现要求已经通过真机验证。当前仍不能声称 CSI 相位已经校准，也不能
把软件时钟桥的残差解释为硬件级同步精度。

## 2. 本轮代码与环境

- iPhone：iPhone 11 Pro，`iPhone12,3`，iOS `26.3.1`
- App：WiTwinRecorder `0.3.0 (1)`
- iPhone Wi-Fi MAC：`86:d7:cd:37:90:4c`
- AP：`HUAWEI-CJ103P_2.4G`
- 信道：channel 7，2442 MHz，HT20
- Linux UDP：`192.168.3.31:5201`
- UDP 负载：1200 B，目标码率 2 Mbit/s
- PicoScenes：AX200，interface index 2

真机 XCTest 新增了两个可选时长变量：

```text
WITWIN_UDP_DURATION_SECONDS       默认 10，允许 1～600 秒
WITWIN_RECORDER_DURATION_SECONDS 默认 5，允许 1～120 秒
```

默认值保持短测试行为不变；本轮分别使用 150 秒和 60 秒。自动化用的 Xcode
Scheme 环境变量在每次测试后均已移除。

## 3. 独立 UDP/CSI 长时基准

### 3.1 边界测试

第一轮 iPhone 发包实际运行 `120.034 s`，但进入拟合窗口的有效跨度仅为：

| 时间轴 | 有效跨度 |
|---|---:|
| 手机单调时间 | 117.888 s |
| PicoScenes 设备时间 | 117.770 s |

两者都略低于可靠漂移判定所要求的 120 秒，因此该轮虽然估计出斜率，但
`drift_fit_reliable=false`。没有降低门槛，而是延长测试后重测。

Linux 证据目录：

```text
/opt/witwin/capture/csi-linux/raw/phone-csi-long-20260730-v1/
```

### 3.2 150 秒有效测试

iPhone XCTest 实际运行 `150.124 s`。Linux 证据目录：

```text
/opt/witwin/capture/csi-linux/raw/phone-csi-long-20260730-v2/
```

UDP 结果：

| 指标 | 结果 |
|---|---:|
| iPhone 本地发送成功 | 31,247 |
| Linux 收到数据包 | 31,195 |
| 缺失包 | 52 |
| 接收率 | 99.8336% |
| 重复或乱序 | 0 |
| 手机时间戳跨日志不一致 | 0 |
| WTWN data session hash | `ede7da24d2e6baca` |

Linux 用户态接收时刻相对 `SO_TIMESTAMPNS` 内核到达时刻：

| 指标 | 延迟 |
|---|---:|
| 样本数 | 31,196 |
| P50 | 0.078 ms |
| P95 | 0.190 ms |
| P99 | 0.320 ms |
| 最大值 | 8.125 ms |

CSI 结果：

| 指标 | 结果 |
|---|---:|
| PicoScenes 已解析手机源帧 | 1,708 |
| 筛出的手机上行大包 CSI PPDU | 1,535 |
| `245 × 2 × 2` CSI | 565 |
| `245 × 1 × 2` CSI | 970 |
| 手机有效跨度 | 145.613 s |
| CSI 有效跨度 | 145.556 s |

时钟映射：

```text
t_csi_device_ns =
    0.999981543157363 * t_phone_monotonic_ns
    - 59293657085850.98
```

| 指标 | 结果 |
|---|---:|
| `clock_scale_estimated` | `true` |
| `drift_fit_reliable` | `true` |
| 漂移 | -18.457 ppm |
| 时钟桥残差 RMS | 13.962 ms |
| 手机→Linux 残差 P50 | 1.372 ms |
| 手机→Linux 残差 P95 | 21.770 ms |
| CSI 设备→Linux 残差 RMS | 0.912 ms |
| CSI 设备→Linux残差绝对值 P95 | 1.530 ms |
| 诊断性最近邻 CSI 匹配 | 1,497/1,535 |

该结果满足当前工具的所有可靠性门槛：两条有效时间轴均超过 120 秒、下包络拟合
样本数不少于 12、匹配数不少于 100，且斜率处于 `0.999～1.001`。

关键 SHA-256：

| 文件 | SHA-256 |
|---|---|
| iPhone `udp_tx.csv` | `8a39b6a004e6bfc71003fb1251e636e62b8ec1d6ea83d32db2c54e251b90f940` |
| Linux `udp_probe.csv` | `c17cf306a23ce1361f24c6c348f3c56960c30cdb664611052a5c87a339971901` |
| `csi_packets.csv` | `21ff3e0a6bcc91c54b1516169d84ef935b4e6f4b3a77989712aea8c0291f4e96` |
| `clock_mapping.json` | `0646fe39385757c42e36d5a49cd012db84e9eefb6f08e3d28c1cd63e5616848d` |
| PicoScenes `.csi` | `a523e856b434b25b24d56b6a801614129e4f0b07a6af63bb711f712aa10f8080` |

## 4. Recorder 同进程 60 秒联合测试

iPhone session：

```text
Documents/Sessions/session_20260730_170429/
```

Linux 同期证据目录：

```text
/opt/witwin/capture/csi-linux/raw/phone-recorder-csi-20260730-v1/
```

XCTest 实际运行 `61.783 s`；Recorder 元数据记录采集 `60.206 s`，完整性报告
`passed=true` 且 `errors=[]`。

### 4.1 手机端同进程产物

| 指标 | 结果 |
|---|---:|
| 视频帧 | 3,569 |
| 视频丢帧 | 0 |
| 视频时间映射缺失率 | 0 |
| 视频大小 | 90,025,171 B |
| ARKit 帧 | 3,569 |
| ARKit 最大时间间隔 | 16.770 ms |
| ARKit normal tracking | 3,499 |
| IMU 样本 | 42,038 |
| 各 IMU 类型估计频率 | 约 100.026 Hz |
| UDP 本地成功 | 12,481 |
| UDP 本地失败 | 0 |
| UDP 日志序号间断 | 0 |
| UDP 实际码率 | 1.9971 Mbit/s |
| 测试期间最高热状态 | nominal |

`face_anchors.csv` 没有有效面部锚点并产生一条警告；本轮使用后置相机进行房间
采集，这不影响视频、ARKit、IMU、UDP 或 CSI 的 P2 验证结论。

### 4.2 Linux UDP/CSI 结果

| 指标 | 结果 |
|---|---:|
| Linux 收到数据包 | 12,471/12,481 |
| 缺失包 | 10 |
| 接收率 | 99.9199% |
| 重复或乱序 | 0 |
| 手机时间戳跨日志不一致 | 0 |
| WTWN data session hash | `569fc0c3bfbd0461` |
| 筛出的手机上行大包 CSI PPDU | 191 |
| `245 × 2 × 2` CSI | 100 |
| `245 × 1 × 2` CSI | 91 |
| 诊断性最近邻 CSI 匹配 | 189/191 |

本次 CSI 有效跨度为 56.738 秒，低于重新估计斜率所需的 60 秒，因此 session 内
映射正确采用固定单位斜率：

```text
t_csi_device_ns = t_phone_monotonic_ns - 60125643421184
```

其时钟桥残差 RMS 为 11.962 ms，CSI 设备到 Linux 的残差 RMS 为 0.856 ms。
漂移斜率应使用紧邻本轮、已通过可靠性判定的 150 秒基准结果，而不是把本轮
`drift_fit_reliable=false` 误解为功能失败。

关键 SHA-256：

| 文件 | SHA-256 |
|---|---|
| iPhone `udp_tx.csv` | `23f3b2c7f3e014d718c47f3f83786ed695279a8954be288ff51a9899d1b9e63e` |
| Linux `udp_probe.csv` | `63d9695ef293d984996f31123906526640c1e0d436480bbf292bf21b085bce41` |
| `csi_packets.csv` | `849dbfe854e02f0036af9c88014f80a83a5545fc0469bd81f36b910e22c00ee3` |
| `clock_mapping.json` | `e60105a8e599f0e3f2804708a8cae2989e8271065f79ba50bc2a77bcbe918d19` |
| PicoScenes `.csi` | `3c829d0ec9ae71557378cbb235ccaf2b4265b4db31251ef8c72d1f9c2bf0f813` |

Mac 上已复制轻量证据和 iPhone 日志到：

```text
datasets/iphone11pro-p2-csi-linux-20260730/
  phone-csi-long-20260730-v1/
  phone-csi-long-20260730-v2/
  phone-recorder-csi-20260730-v1/iphone_session/
```

大体积原始视频和 PicoScenes 文件仍保留在各自设备/主机的上述原始目录，不纳入
Git。

## 5. 验证与恢复状态

- 可配置 UDP 时长代码已在现有 iPhone 17 模拟器完成编译/单元测试；
- iPhone 150 秒独立 UDP 真机 XCTest 通过；
- iPhone 60 秒 Recorder 同进程真机 XCTest 通过；
- 两次 Xcode 自动化使用的临时 Scheme 环境变量均已移除；
- Linux AX200 已删除 `mon2` 并恢复连接
  `HUAWEI-CJ103P_2.4G`；
- 没有残留 PicoScenes、UDP receiver 或联合采集进程。

## 6. 下一步实施方向

1. 新增离线时间轴物化工具：把 `csi_packets.csv` 的设备时间转换为手机
   `mach_continuous_time`，再给每条 CSI 标注最近的 ARKit 帧和 IMU 区间；
2. 在 session 清单中记录所采用的长时基准映射 SHA-256、适用时间和设备组合，
   避免跨设备或跨日期误用漂移；
3. 对同一静止位置重复至少 3 个 60 秒 session，统计 UDP 接收率、CSI PPDU
   采样密度和映射残差的重复性；
4. 独立开展 CSI 相位校准；在完成前只使用幅度、RSSI、包级时间与形状信息，
   不声称跨 session 的绝对相位可比；
5. 完成以上数据契约后，再进入正式房间轨迹扫描与后续算法接口。

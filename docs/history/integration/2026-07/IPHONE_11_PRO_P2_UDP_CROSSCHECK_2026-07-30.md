# iPhone 11 Pro P2 UDP 跨端核对报告

核对日期：2026-07-30

## 1. 输入证据

Linux 接收端：

```text
datasets/iphone11pro-p2-linux-20260730/udp_probe_20260730_111527.csv
```

手机独立 UDP：

```text
datasets/iphone11pro-p2-udp-20260730/udp_test_1785381409/udp_tx.csv
```

手机 Recorder 联合 session：

```text
datasets/iphone11pro-p2-integrated-20260730/session_20260730_111846/
```

输入文件 SHA-256：

| 文件 | SHA-256 |
|---|---|
| Linux `udp_probe_20260730_111527.csv` | `07d3439e38bfc4ba9afd46d48a5b73edc6e99524937c4c41460987a63fcb0149` |
| 手机独立 `udp_tx.csv` | `ef356fe67572d1cf1e49d5327407397f22566c2a47c0f9e34a40a25f11f760fa` |
| 手机联合 `udp_tx.csv` | `6417a54d56f0159b674f0f45da8a2ee561b7d9416164edeec29a20a9d5c15ab2` |

当前目录只发现 Linux CSV，没有发现接收器生成的
`udp_probe_20260730_111527.summary.json`。以下统计均从逐包 CSV 重新计算。

## 2. Session 识别

| 流 | session_id | WTWN session hash | preflight hash |
|---|---|---|---|
| 独立 UDP | `udp_test_1785381409` | `ce0861a32efd99a8` | `4916c7c943f95b1a` |
| Recorder 联合 | `session_20260730_111846` | `0d9ea0c108864871` | `ef11f8032ea12818` |

两个 preflight hash 在 Linux 端各出现一个 `flags=1` 的 HELLO，状态均为
`hello_acknowledged`。这证明两次测试都实际完成了双向 HELLO/ACK，而不是只在
iPhone 本地 UDP 栈中显示发送成功。

Linux 观察到的手机地址为 `192.168.3.26`。两次连接的临时源端口分别为
`58505` 和 `52328`；端口变化是 UDP 客户端连接重新建立时的正常现象。

## 3. 正式数据包核对

| 指标 | 独立 UDP | Recorder 联合 |
|---|---:|---:|
| 手机本地发送成功 | 2083 | 1035 |
| Linux 接收 | 2079 | 1035 |
| Linux 相对手机成功包的接收率 | 99.8080% | 100.0000% |
| 网络/接收路径缺失 | 4 | 0 |
| 重复包 | 0 | 0 |
| 乱序 | 1 个乱序块 | 0 |
| Linux 有效接收时长 | 9.996133 s | 4.997531 s |
| Linux 接收有效载荷码率 | 1.996612 Mbit/s | 1.988182 Mbit/s |

独立 UDP 缺失序号为：

```text
1303, 1305, 1306, 1309
```

独立 UDP 还观察到一个乱序块：`1053…1055` 先于 `1029…1052` 到达。所有已
接收序号均唯一，没有重复。缺失集中在短时间段，并伴随 Linux 接收时间上的批量
到达，可能来自 Wi-Fi/内核接收队列/用户态调度中的瞬时排队；仅凭本次日志不能
进一步区分无线丢包和接收端队列丢包。

联合 session 的手机日志还有序号 `1035`，状态为
`cancelled_before_completion`。该包没有计入手机本地成功包，也未在 Linux
出现，因此它是停止过程中的本地取消，不是网络丢包。正式成功序号
`0…1034` 全部到达 Linux。

两次测试合计：

- 手机本地成功包：3118；
- Linux 收到正式数据包：3114；
- 缺失：4；
- 合计接收率：99.8717%；
- 合计缺失率：0.1283%。

Linux CSV 共 3116 个数据行，其中 3114 个正式数据包、2 个已确认 HELLO；
所有行的 magic、协议版本、头长度和 flags 均可解析，没有无效包。

## 4. 字段和时间轴一致性

对每个 Linux 已接收正式包，按 session hash 和 sequence 回查手机日志：

- `phone_monotonic_ns` 不一致：0；
- `datagram_bytes` 不一致：0；
- Linux 端意外出现、手机端不存在的 sequence：0。

因此 WTWN v1 的 session hash、序号、手机单调时间戳和网络字节序已经跨 Swift
发送端与 Python 接收端验证一致。

Recorder 联合 session 的手机单调纳秒范围：

| 数据流 | 首个 callback/send ns | 最后 callback/send ns |
|---|---:|---:|
| IMU | 39440886390833 | 39445917389083 |
| UDP | 39440915333375 | 39445912763375 |
| ARFrame | 39441572351166 | 39445906042625 |

UDP 完整落在 IMU 采集窗口内，并与 ARFrame 采集窗口重叠。这验证了 UDP、
ARKit 和 CoreMotion 使用同一个 App 进程内的手机单调时钟，可以按
`callback_phone_monotonic_ns`/`phone_monotonic_ns` 直接关联。

Linux `receiver_monotonic_ns` 与手机时钟不是同一个时钟。两次流量中
`receiver_monotonic_ns - phone_monotonic_ns` 的观测范围分别波动约
153.4 ms 和 137.5 ms，且存在批量到达和乱序。因此不能把 UDP 到达时间直接当作
CSI 时间，也不应使用这两个仅 5/10 秒的样本拟合可信的时钟漂移。

## 5. 结论

P2 的以下目标已经通过：

1. 数字 IP `192.168.3.31:5201` 双向可达；
2. WTWN HELLO/ACK 预检有效；
3. iPhone 独立上行能够稳定产生约 2 Mbit/s UDP；
4. UDP 已与视频、ARKit 和 IMU 在 Recorder 同一进程、同一 session 内运行；
5. Swift 与 Python 对 WTWN v1 包头的解析完全一致；
6. 联合测试正式成功包的跨端接收率为 100%，序号无缺口；
7. 接收端到达时间存在明显排队抖动，必须保留独立 CSI 时间戳并进行后续时钟映射。

下一步应把 PicoScenes 中与这两段 UTC 窗口对应的 CSI/帧记录导出：

```text
2026-07-30T03:16:49Z … 2026-07-30T03:16:59Z
2026-07-30T03:18:46Z … 2026-07-30T03:18:51Z
```

然后按源地址、方向、信道和帧时间筛选 iPhone 上行帧，并使用更长采集、分布在
session 开始/中间/结束的匹配事件，以稳健方法估计手机时钟到 CSI 时钟的偏移和
漂移。

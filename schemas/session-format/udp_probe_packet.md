# UDP Probe Packet v1

手机通过 Wi-Fi 发送 UDP 上行包，用于产生可识别流量并建立手机时钟与 CSI
采集时钟的对应关系。所有多字节整数采用网络字节序（big-endian）。

## 固定 32 字节头

| 偏移 | 长度 | 字段 | 类型 | 含义 |
|---:|---:|---|---|---|
| 0 | 4 | `magic` | bytes | ASCII `WTWN` |
| 4 | 1 | `protocol_version` | uint8 | 当前为 `1` |
| 5 | 1 | `flags` | uint8 | `0` 数据、`1` HELLO、`2` ACK |
| 6 | 2 | `header_length` | uint16 | 当前为 `32` |
| 8 | 8 | `session_hash` | uint64 | `session_id` SHA-256 的前 8 字节 |
| 16 | 8 | `sequence` | uint64 | session 内从 0 单调递增 |
| 24 | 8 | `phone_monotonic_ns` | uint64 | 手机单调时钟纳秒 |

偏移 32 之后是可选载荷。接收端必须先验证 magic、版本和头长度，再读取其他字段。
不支持的主版本应明确拒绝，不能按 v1 猜测解析。

## HELLO/ACK 预检

Recorder 正式发包前使用独立的 `session_id + ".preflight"` 哈希发送最多 5 个
HELLO。接收端以相同的 session hash、sequence 和 phone timestamp 返回
32 字节 ACK。Recorder 只有在 3 秒内收到并验证 ACK 后才开始 flags=0 的正式
数据流。预检使用独立 session hash，因此正式数据的 sequence 仍从 0 开始。

ACK 只用于证明目标 IP、UDP 端口和接收进程可达，不能代替 CSI 时间戳，也不能
作为手机和 CSI 时钟已经同步的证据。

## 采集要求

- iOS 端同时将每个序号和发送结果写入 `udp_tx` 日志；
- CSI Linux 端记录可解析 UDP 包的序号、CSI 时间和主机接收时间；
- 不允许用 UDP 到达时间替换 CSI 硬件或采集软件时间戳；
- session 开始、中间和结束都应持续产生匹配点，以估计时钟漂移；
- 重发不能复用序号；丢失序号作为丢包统计保留。

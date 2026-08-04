# iPhone 11 Pro P2 PicoScenes/CSI 联合采集报告

验证日期：2026-07-30

## 1. 结论

P2 已完成第一次真正包含以下三类同期证据的端到端短测试：

1. iPhone 原生 App 的 `udp_tx.csv`；
2. Linux WTWN 接收日志及内核到达时间；
3. PicoScenes 原始 `.csi`、手机上行过滤结果与复数 CSI 数组。

本次证明了 iPhone 上行 WTWN 流量能在同一窗口内被 Linux 接收并由 AX200/
PicoScenes 取得 CSI。10 秒窗口只足以验证过滤和偏移流程；时钟漂移仍未估计，
不能把 provisional 映射解释为硬件同步。

## 2. 验证拓扑

```text
iPhone 11 Pro (86:d7:cd:37:90:4c)
        │  2 Mbit/s UDP, 1200 B
        ▼
HUAWEI-CJ103P_2.4G, channel 7, 2442 MHz, HT20
        ├── enp1s0 192.168.3.31:5201 -> WTWN receiver
        └── AX200 mon2 -> PicoScenes interface index 2
```

Linux 原始会话：

```text
/opt/witwin/capture/csi-linux/raw/phone-csi-kernel-ts-smoke-20260730-v3/
```

Mac 上的 Linux 会话备份：

```text
datasets/iphone11pro-p2-csi-linux-20260730/
  phone-csi-kernel-ts-smoke-20260730-v3/
```

iPhone 日志的 Mac 副本：

```text
datasets/iphone11pro-p2-csi-smoke-20260730/
  udp_test_1785399496/udp_tx.csv
```

关键输入 SHA-256：

| 文件                                | SHA-256                                                              |
| ----------------------------------- | -------------------------------------------------------------------- |
| iPhone`udp_tx.csv`                | `43b218dcd72ed90cda978cf4ca2806f8168a2ad36374d3d47a27dfb769004a60` |
| Linux`udp_probe.csv`              | `cacfaf3034e8c358658821591bc05223866bc82a47424beb7317c1c85084c9f5` |
| `csi_packets.csv`                 | `00cda8d13bb8a35543af3db97e25a7a3a672ee1c3e041005e189e4375c3f9476` |
| `alignment-v2/clock_mapping.json` | `2dff0ee4cb2dc0b87574c64ed5e547f80a959615a40606d18d2d33cd7757e561` |

## 3. UDP 结果

| 指标                   |                 结果 |
| ---------------------- | -------------------: |
| iPhone 本地成功包      |                 2080 |
| Linux 收到数据包       |                 2031 |
| 缺失包                 |                   49 |
| 接收率                 |             97.6442% |
| 手机时间戳跨日志不一致 |                    0 |
| HELLO/ACK              |                 通过 |
| WTWN data session hash | `c5dfd24192a5753f` |
| Linux 接收缓冲区       |               16 MiB |
| Linux 内核时间戳       |                 可用 |

用户态 `recvmsg` 时刻相对 `SO_TIMESTAMPNS` 内核到达时刻：

| 指标   |     延迟 |
| ------ | -------: |
| 中位数 | 0.081 ms |
| P95    | 0.246 ms |
| 最大值 | 0.623 ms |

这说明 Python 调度不再是主要到达时间误差。仍存在的较大抖动主要位于
iPhone—AP—有线接收路径，不能靠把 Python 时间替换为内核时间完全消除。

## 4. CSI 过滤结果

原始 PicoScenes 文件：

```text
rx_2_260730_161803.csi
SHA-256 3010bbc72a70d9a39699f55ca37ac140abbfbd4a19cd111a4e8fb29402943561
```

过滤条件：

```text
Addr2 == 86:d7:cd:37:90:4c
ToDS == 1
FromDS == 0
frame_type == data
primary_mpdu_bytes >= 1000
```

| 指标                        |           结果 |
| --------------------------- | -------------: |
| PicoScenes 已解析手机源帧   |            156 |
| 筛出的手机上行大包 CSI PPDU |             86 |
| `245 × 1 × 2` CSI       |             78 |
| `245 × 2 × 2` CSI       |              8 |
| 过滤结果复数类型            | `complex128` |

真实数据证明 CSI 形状并不恒定。导出器已改为按子载波布局、TX 和 RX 维度分组，
并通过 `csi_group`/`csi_group_index` 建立 CSV 与 `.npy` 的可追溯关系。不能把
一条 UDP 数据报机械对应为一条 CSI：Wi-Fi 聚合、重传及 PicoScenes/网卡采样会
使两侧数量不同。

## 5. 时钟映射结果

短窗口策略：

```text
t_csi_device_ns = t_phone_monotonic_ns + clock_offset_ns
```

本次输出：

| 指标                      |                    结果 |
| ------------------------- | ----------------------: |
| `clock_scale`           | `1.0`（固定，未估计） |
| `clock_scale_estimated` |               `false` |
| `clock_offset_ns`       |     `-56897171866880` |
| 时钟桥残差 RMS            |               56.801 ms |
| 手机→Linux 残差 P50      |                3.106 ms |
| 手机→Linux 残差 P95      |              146.306 ms |
| CSI 设备→Linux 残差 RMS  |                1.214 ms |
| 诊断性最近邻 CSI 匹配     |                   84/86 |
| `drift_fit_reliable`    |               `false` |

残差包含未知的单向网络时延、AP 排队、Wi-Fi 聚合和非一一对应误差。该映射只可
用于证明偏移拟合流程能运行，不能作为正式逐帧同步精度。

## 6. 下一步

1. 使用同一联合采集入口进行至少 120 秒的稳定位置测试；
2. 在 session 开始、中间和结束都保持可识别 WTWN 流量；
3. 使用 Linux 内核到达时间建立手机到 Linux 的下包络；
4. 使用 PicoScenes `systemns` 与设备时间建立 CSI 到 Linux 的映射；
5. 仅在两条时间轴均超过 60 秒且斜率处于合理 ppm 范围时接受漂移；
6. 再做 Recorder 同进程的 60～120 秒联合采集，把 CSI 映射到 ARKit/IMU 时间轴；
7. 独立开展 CSI 相位校准；当前只能声称复数 CSI 已导出，不能声称跨 session
   相位已具备物理可比性。

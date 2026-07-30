# CSI Linux Capture

此目录用于 CSI 采集 Linux 主机，对应工作分支 `work/csi-linux`。

## 职责

- 固定并记录 CSI 网卡、天线、线缆、支架、驱动和 PicoScenes 版本；
- 接收或监听 iPhone 上行通信帧；
- 按 MAC、帧方向、信道和带宽筛选 `phone -> CSI acquisition NIC` 链路；
- 解析 `schemas/session-format/udp_probe_packet.md` 定义的 UDP 探测头；
- 保存 CSI 本地时间戳、主机时间、RSSI、复数 CSI、射频链和丢包统计；
- 生成数据清单、SHA-256 和采集质量报告。

原始 CSI 默认写入 `capture/csi-linux/raw/` 或仓库根目录的 `datasets/`，两者均不
进入普通 Git。只提交采集脚本、配置模板、解析器、小型脱敏样例和报告。

在尚未验证相位校准前，应分别标记“幅度可用”和“复数 CSI 已验证”，不能把能
读取复数数组等同于相位已经具备跨 session 物理意义。

## WTWN UDP 接收基线

iPerf3 基准继续使用 TCP 控制端口 5201。Recorder 自定义的
`schemas/session-format/udp_probe_packet.md` 的目标 IP 和 UDP 端口由手机端
配置。首轮默认使用 `192.168.3.31:5201`；iPerf3 服务的 TCP 5201 可以与
WTWN UDP 5201 并存，但运行 iPerf3 UDP 测试时不能让两种 UDP 接收器同时占用
5201，此时应把 WTWN 改到 5202。

接收器会申请 Linux `SO_TIMESTAMPNS` 内核到达时间戳，并把 UDP 接收缓冲区请求
为 8 MiB（Linux 返回值通常为双倍记账后的 16 MiB）。在 PicoScenes 启动后，
也可以单独运行：

```bash
/opt/witwin/venv-picoscenes/bin/python \
  /opt/witwin/capture/csi-linux/udp_probe_receiver.py \
  --bind 0.0.0.0 \
  --port 5201 \
  --output /opt/witwin/capture/csi-linux/raw/udp_probe.csv
```

停止时按 `Ctrl-C`。脚本会响应 Recorder 的 HELLO/ACK 预检，并输出逐包 CSV
和 `udp_probe.summary.json`，检查 magic、协议版本、session hash、序号缺口
和手机单调时间戳。`receiver_kernel_realtime_ns` 非零时是时钟桥接的首选 Linux
到达时间；`receiver_monotonic_ns` 和 `receiver_realtime_ns` 保留为用户态诊断
字段。三者都不能替代 PicoScenes 的 CSI 设备时间戳。

## PicoScenes + WTWN 联合采集

先确认 AP 当前信道。例如本次验证使用信道 7，即 `2442 MHz / HT20`。网卡准备
会改变 AX200 状态，应只在有线 SSH 正常时明确执行：

```bash
sudo array_prepare_for_picoscenes 2 "2442 HT20"
```

随后由统一入口同时启动 PicoScenes 和 WTWN 接收器：

```bash
/opt/witwin/venv-picoscenes/bin/python \
  /opt/witwin/capture/csi-linux/run_phone_csi_capture.py \
  --output-dir /opt/witwin/capture/csi-linux/raw/session_name \
  --phone-mac 86:d7:cd:37:90:4c \
  --duration 120 \
  --interface-index 2 \
  --port 5201
```

`phone-mac` 只是本次测试示例；每次实验都应从 iPhone 当前实验 SSID 的固定私有
Wi-Fi 地址或 Linux 邻居表重新核对，不能永久硬编码。脚本不会自行调用
`array_prepare_for_picoscenes`，以免无提示地停止 NetworkManager 或切换信道。

控制台显示 `READY` 后再从 iPhone 开始发包。结束后目录至少包含：

```text
capture_manifest.json
picoscenes_capture.log
rx_*.csi
udp_probe.csv
udp_probe.summary.json
export/
├── csi_packets.csv
├── metadata.json
├── csi_group_000.npy
└── subcarrier_index_group_000.npy
```

联合入口会按 `Addr2=phone`、`ToDS=1`、`FromDS=0` 和
`primary_mpdu_bytes >= 1000` 筛选手机上行数据。实际 iPhone/AX200 采集中可能
同时出现不同 `numTx` 或子载波布局；导出器按 PHY/CSI 形状分组保存，而不是把
与首帧形状不同的数据丢弃。`csi_packets.csv` 的 `csi_group` 和
`csi_group_index` 可回查对应 NumPy 数组。

实验结束后若要恢复 AX200 普通联网，先删除本次监控接口、恢复网卡原 MAC，并
重新交给 NetworkManager。具体接口名和原 MAC 必须先用 `iw dev`/`array_status`
核对，不能照抄：

```bash
sudo iw dev mon2 del
sudo ip link set wlp2s0 down
sudo ip link set wlp2s0 address 4c:5f:70:73:f2:5d
sudo nmcli device set wlp2s0 managed yes
sudo ip link set wlp2s0 up
sudo nmcli connection up HUAWEI-CJ103P_2.4G
```

## CSI 导出与时钟映射

也可以独立重导已有 `.csi`：

```bash
/opt/witwin/venv-picoscenes/bin/python \
  /opt/witwin/capture/csi-linux/export_picoscenes.py \
  raw/session_name/rx_*.csi \
  --output-dir raw/session_name/export-udp \
  --phone-mac 86:d7:cd:37:90:4c \
  --require-uplink \
  --min-mpdu-bytes 1000
```

从 iPhone 导出同次 `udp_tx.csv` 后，使用手机日志、Linux UDP 日志和
`csi_packets.csv` 组成两段时钟桥：

```bash
/opt/witwin/venv-picoscenes/bin/python \
  /opt/witwin/capture/csi-linux/fit_phone_csi_clock.py \
  --phone-log raw/session_name/phone_udp_tx.csv \
  --receiver-log raw/session_name/udp_probe.csv \
  --csi-packets raw/session_name/export/csi_packets.csv \
  --session-hash 0123456789abcdef \
  --output-dir raw/session_name/alignment
```

输出 `clock_mapping.json` 和诊断性的 `udp_csi_matches.csv`。工具优先使用
`receiver_kernel_realtime_ns`，并拒绝把不重叠的 UDP/CSI 采集窗口强行拟合。
只有手机与 CSI 时间轴都覆盖至少 60 秒时才允许估计 `clock_scale`；短测试固定
`clock_scale=1`，只给出 provisional 偏移，并明确
`clock_scale_estimated=false`。该偏移仍包含未知的最小单向网络时延，不是硬件
时钟同步。

回归测试不需要安装 pytest：

```bash
/opt/witwin/venv-picoscenes/bin/python -m unittest -v \
  capture/csi-linux/tests/test_clock_fit.py
```

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

在 PicoScenes 启动后，可并行运行：

```bash
/opt/witwin/venv/bin/python /opt/witwin/capture/csi-linux/udp_probe_receiver.py \
  --bind 0.0.0.0 \
  --port 5201 \
  --output /opt/witwin/capture/csi-linux/raw/udp_probe.csv
```

停止时按 `Ctrl-C`。脚本会响应 Recorder 的 HELLO/ACK 预检，并输出逐包 CSV
和 `udp_probe.summary.json`，检查 magic、协议版本、session hash、序号缺口
和手机单调时间戳。脚本记录的
`receiver_monotonic_ns`/`receiver_realtime_ns` 是 Linux 主机时钟，不能替代
PicoScenes 的 CSI 时间戳。

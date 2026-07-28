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

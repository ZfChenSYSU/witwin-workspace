# `work/csi-linux` 分支当前状态

更新时间：2026-08-05

## 当前结论

PicoScenes/AX200 已能够与 WTWN UDP 接收器联合工作，按手机源地址、帧方向、信道和数据帧特征筛选 `phone -> CSI acquisition NIC` 链路，并导出可追溯的复数 CSI。

已验证的代表性结果包括：

- 150 秒测试收到 31,195/31,247 个手机成功 UDP 包，接收率 99.8336%；
- 筛得 1535 个手机上行大包 CSI PPDU，观测到 `245×1×2` 和 `245×2×2` 两类形状；
- Linux 内核到达时间和 PicoScenes 设备时间均已保存；
- 长时拟合得到约 `-18.457 ppm` 的手机—CSI 时钟漂移，并通过当前可靠性门槛；
- 一条 UDP 数据报与一条 CSI 记录不存在机械一一对应关系，导出器已按 CSI 形状分组。/
- CSI 时间轴物化工具已完成真实验证：191/191 条 CSI 关联到 `normal` ARKit
  帧，全部取得 IMU 时间窗，映射 SHA-256、设备组合和适用时间已写入 manifest。

## 当前缺口

- 现有 60 秒 Recorder session 已完成物化，但其有效 CSI 跨度不足 60 秒，映射
  仍采用固定单位斜率；需要在重复 session 中验证可靠漂移和关联误差的稳定性；
- 需要至少 3 个相同条件的重复 session 评估采样密度、映射残差和跨 session 漂移；
- CSI 相位只完成复数值导出，跨 session 物理可比性尚未校准；
- 网卡、天线、线缆、支架和主机机身的有效响应与装配重复性仍需量化。

## 下一步

1. 完成 3 组以上静止重复 session，并在每次采集前后加入静态参考段。
2. 统计跨 session 的 CSI 密度、ARKit/IMU 关联误差、时钟残差和漂移稳定性。
3. 冻结接收端装配，建立幅度、RSSI、包密度和时钟残差基线。
4. 将已物化的 `csi_timeline.csv` 接入 WSL 统一数据加载器。
5. 独立推进 CFO/SFO/PDD、公共相位和射频链响应校准；通过前以幅度为真实主线。
6. 保持手机上行与 AP 下行严格分离，不把监听网卡 CSI 表述为普通路由器端 CSI。

历史证据见 [P2 跨端联合验证](../../history/integration/2026-07/)。

本轮详细结果见
[CSI—ARKit—IMU 时间轴物化验证](../../history/branches/work-csi-linux/experiments/csi_multimodal_timeline_2026-08-05.md)。

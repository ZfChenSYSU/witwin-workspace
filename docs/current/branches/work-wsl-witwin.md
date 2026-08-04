# `work/wsl-witwin` 分支当前状态

更新时间：2026-08-04

## 当前结论

WiTwin 固定 GPU 环境和 `w_geo` 阶段 1 仿真已经完成。短轨迹与 80 时刻、5 空间区块的长轨迹实验均判定为 GO：动态三维人体—手机几何会显著改变复 CSI、污染有效反射参数，只保留标量距离不足以恢复传播几何。

当前能力包括：

- 固定版本下的 CUDA、DrJit、确定性信道、LOS、CIR 和 CFR 验证；
- 使用显式 DrJit 反射后端的最多三次镜面反射实验；
- 低维 `theta_ref` 恢复、有限差分/自动微分审计、空间留一验证和可复现产物；
- 重建流水线的输入、基线算法和评价指标设计。

## 当前缺口

- 仿真观测与预测仍来自同一仿真器，尚未获得真实 CSI 外部验证；
- 当前上游 WiTwin/Channel/RayD 组合的原生 reflected EPC 仍未通用通过；
- `pipelines/reconstruction` 尚无实际 COLMAP 稀疏/稠密重建结果；
- 统一数据加载器、坐标对齐、材料区域和真实参数反演尚未实现。

## 下一步

1. 接收 CSI 时间轴物化结果，建立统一 session 离线加载与质量检查。
2. 实现 COLMAP/SfM 基线，与 ARKit 米制轨迹做 SE(3)/Sim(3) 对齐并输出精度报告。
3. 生成适合 WiTwin 的房间网格、主要传播表面和材料区域。
4. 使用真实深度噪声、掉帧和 CSI 幅度统计更新仿真误差分布。
5. 在固定装配真实数据上比较 FIXED、RAW、KF、RTS 和不确定度边缘化，并使用留出轨迹/session 评价。
6. 扩展独立轨迹、AP 位置和房间布局，但不在真实闭环完成前扩大参数维度。

详细实验报告见 [`w_geo` 阶段 1](../../history/branches/work-wsl-witwin/experiments/wgeo_stage1/) 和 [长轨迹实验](../../history/branches/work-wsl-witwin/experiments/wgeo_stage1_long_trajectory/)。


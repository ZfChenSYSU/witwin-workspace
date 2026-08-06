# `work/wsl-witwin` 分支当前状态

更新时间：2026-08-06

## 当前结论

WiTwin 固定 GPU 环境和 `w_geo` 阶段 1 仿真已经完成。短轨迹与 80 时刻、5 空间区块的长轨迹实验均判定为 GO：动态三维人体—手机几何会显著改变复 CSI、污染有效反射参数，只保留标量距离不足以恢复传播几何。

当前能力包括：

- 固定版本下的 CUDA、DrJit、确定性信道、LOS、CIR 和 CFR 验证；
- 使用显式 DrJit 反射后端的最多三次镜面反射实验；
- 低维 `theta_ref` 恢复、有限差分/自动微分审计、空间留一验证和可复现产物；
- 重建流水线的输入、基线算法和评价指标设计。
- iPhone Session Schema 1.2/1.3 导入检查、校验和/视频/ARKit/IMU 报告和可追溯
  视频抽帧；
- 在 RTX 4050 Laptop 上从空数据库完成 128 张 South Building 图片的 CUDA SIFT、
  全匹配、mapper、PatchMatch 和 fusion：128/128 注册、33,272 个稀疏点、
  891,539 个融合点。

## 当前缺口

- 仿真观测与预测仍来自同一仿真器，尚未获得真实 CSI 外部验证；
- 当前上游 WiTwin/Channel/RayD 组合的原生 reflected EPC 仍未通用通过；
- 公共数据集基线已跑通，但正式 iPhone 房间 session 的稀疏/稠密重建尚未验证；
- 尚缺曝光/模糊/纹理/视差/覆盖度关键帧选择和 ARKit 内参写入 COLMAP；
- 尚缺 ARKit/COLMAP Sim(3) 米制对齐，以及 global/pose-prior mapper 对照；
- 统一数据加载器、坐标对齐、材料区域和真实参数反演尚未实现。

## 下一步

1. 接收一段合格的 iPhone 房间扫描，运行导入检查并实现质量/视差关键帧选择。
2. 从 frame manifest 注入 ARKit 内参，从空数据库完成 iPhone SIFT + sequential +
   mapper 稀疏基线。
3. 实现视觉轨迹与 ARKit 米制轨迹 Sim(3) 对齐并输出精度报告，再运行受控稠密。
4. 生成适合 WiTwin 的房间网格、主要传播表面和材料区域。
5. 接收 CSI 时间轴物化结果，建立统一 session 离线加载与质量检查。
6. 使用真实深度噪声、掉帧和 CSI 幅度统计更新仿真误差分布，并在固定装配真实
   数据上比较 FIXED、RAW、KF、RTS 和不确定度边缘化。

详细实验报告见 [`w_geo` 阶段 1](../../history/branches/work-wsl-witwin/experiments/wgeo_stage1/) 和 [长轨迹实验](../../history/branches/work-wsl-witwin/experiments/wgeo_stage1_long_trajectory/)。
本轮 iPhone/WSL/COLMAP 实测见
[iPhone 到 WSL 建模执行分析](../project/iPhone到WSL建模执行分析与下一步_2026-08-06.md)。

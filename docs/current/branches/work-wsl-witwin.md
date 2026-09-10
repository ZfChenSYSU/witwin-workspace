# `work/wsl-witwin` 分支当前状态

更新时间：2026-09-09

## 当前结论

WiTwin 固定 WSL/GPU 环境和 `w_geo` 阶段 1 仿真已经完成。短轨迹与 80 时刻、5
空间区块的长轨迹实验均判定为 GO。当前决定将 WiTwin、重建和离线分析迁往服务器；
分支名 `work/wsl-witwin` 暂时保留，以下环境结果只作为服务器迁移的回归基线。

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
- 目标服务器身份、代码提交、GPU 软件栈、数据盘和 WiTwin 最小验证尚待重新确认；
- 服务器导入器尚未支持新版 LiDAR session。

## 下一步

1. 审计目标服务器的 Git、GPU、驱动、CUDA、Python、WiTwin 和数据盘，并保存环境清单。
2. 从固定提交运行 LOS、CIR、CFR、梯度与历史实验最小回归。
3. 接收一个新版 LiDAR iPhone 最小 session，实现不可变导入、完整性检查以及
   RGB—深度—位姿—网格的时间和坐标对齐。
4. 比较 ARKit mesh、RoomPlan、RGB-D 融合与 LiDAR 辅助 COLMAP，生成独立精度报告。
5. 生成适合 WiTwin 的房间网格、主要传播表面和材料区域。
6. 接收 CSI 时间轴物化结果，建立统一 session 离线加载与质量检查。
7. 使用真实深度噪声、掉帧和 CSI 幅度统计更新仿真误差分布，并在固定装配真实
   数据上比较 FIXED、RAW、KF、RTS 和不确定度边缘化。

详细实验报告见 [`w_geo` 阶段 1](../../history/branches/work-wsl-witwin/experiments/wgeo_stage1/) 和 [长轨迹实验](../../history/branches/work-wsl-witwin/experiments/wgeo_stage1_long_trajectory/)。
本轮 iPhone/WSL/COLMAP 实测见
[iPhone 到 WSL 建模执行分析](../../history/integration/2026-08/iPhone到WSL建模执行分析与下一步_2026-08-06.md)。
当前迁移任务见
[LiDAR iPhone 与 WiTwin 服务器迁移计划](../project/LiDAR与服务器迁移计划.md)。

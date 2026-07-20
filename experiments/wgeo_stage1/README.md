# 阶段 1：`w_geo` 仿真科学假设验证

本目录是依据[《前置深度增强的科研项目待办与验证计划》](../../workspace/project-docs/前置深度增强的科研项目待办与验证计划.md)重新设计并实际完成的独立实验。正式求解固定 `max_bounces=3`，使用当前锁定的 WiTwin 环境和 DrJit 反射场后端；既有 `experiments/whd_4_3` 实验没有被修改。

## 一键复现

从零重跑全部 960 个主体几何求解和 6 个审计求解：

```bash
cd /opt/witwin
export DRJIT_LIBOPTIX_PATH=/usr/lib/x86_64-linux-gnu/libnvoptix.so.1
/opt/witwin/venv/bin/python experiments/wgeo_stage1/run_experiment.py --force-sim
```

复用已保存的逐阶路径基，仅重做统计分析和绘图：

```bash
cd /opt/witwin
export DRJIT_LIBOPTIX_PATH=/usr/lib/x86_64-linux-gnu/libnvoptix.so.1
/opt/witwin/venv/bin/python experiments/wgeo_stage1/run_experiment.py
```

本次完整运行耗时 99.665 秒，最终打印 `success: true`、`overall_go: true`。

## 文档入口

- [完整实验配置](simulation_config.md)
- [主结果与 Go/No-Go 结论](wgeo_sensitivity_report.md)
- [静态参数偏差报告](theta_bias_report.md)
- [标量距离与三维向量对照](scalar_vs_vector_geometry_report.md)
- [深度噪声、RTS 与边缘化报告](depth_noise_simulation_report.md)

## 证据文件

- `outputs/data/summary.json`：全部主结论的机器可读汇总。
- `outputs/data/group_summary.csv`：SIM-A--SIM-G 的均值、标准差、分位数和覆盖率。
- `outputs/data/group_metrics_repeats.csv`：7 组 × 200 次重复的逐次结果。
- `outputs/data/paired_comparisons.csv`：1 万次配对 bootstrap 的差值区间。
- `outputs/data/geometry_solve_inventory.csv`：960 个主体 WiTwin 几何求解的逐阶路径计数。
- `outputs/data/solver_audit.json`：采样收敛、重复确定性、后端和路径上限审计。
- `outputs/data/gradient_identifiability.json`：自动微分/有限差分及损失剖面检查。
- `outputs/data/trajectory_and_geometry.csv`：完整 `q_t`、`r_t`、含噪和滤波几何。
- `outputs/data/selected_paths.json`：三个代表场景中每条保留路径的顶点、时延和系数。
- `outputs/data/path_basis_cache.npz`：可复用的 0--3 阶复信道路径基。

所有 PNG 图由 `run_experiment.py` 从上述数据直接生成。图中的“三阶”表示最多三次镜面反射；本实验不声称穷尽无限阶物理传播路径。

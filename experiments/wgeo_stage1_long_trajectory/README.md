# `w_geo` 长轨迹并行 D0--D5 实验

本目录是在原 `experiments/wgeo_stage1` 基础上重新设计的独立实验。它使用覆盖 5 个空间区块的 80 时刻长轨迹，并在每个时刻并行施加 D0--D5 六种几何条件，避免把误差类型与时间或空间位置混在一起。

## 复现

完整重跑 2080 个主体几何场景和 6 个审计场景：

```bash
cd /opt/witwin
export DRJIT_LIBOPTIX_PATH=/usr/lib/x86_64-linux-gnu/libnvoptix.so.1
/opt/witwin/venv/bin/python experiments/wgeo_stage1_long_trajectory/run_experiment.py --force-sim
```

复用逐阶路径基，仅重做统计和绘图：

```bash
cd /opt/witwin
export DRJIT_LIBOPTIX_PATH=/usr/lib/x86_64-linux-gnu/libnvoptix.so.1
/opt/witwin/venv/bin/python experiments/wgeo_stage1_long_trajectory/run_experiment.py
```

最近一次完整强制运行耗时 **209.217 秒**，其中主体和审计路径求解耗时 **179.260 秒**；机器结果为 `success=true`、`overall_go=true`。

## 文档

- [完整实验配置](simulation_config.md)
- [完整实验报告](wgeo_long_trajectory_report.md)

## 主要证据

- `outputs/data/summary.json`：Go判据、主要结果和数值审计汇总；
- `outputs/data/direct_sensitivity_summary.csv`：固定 `theta_ref=1` 的直接敏感性；
- `outputs/data/cv_group_summary.csv`：空间留一交叉验证结果；
- `outputs/data/paired_cluster_comparisons.csv`：25个空间区块×几何种子cluster的配对bootstrap；
- `outputs/data/cv_zone_summary.csv`：逐空间区块结果；
- `outputs/data/geometry_solve_inventory.csv`：2080个场景的逐阶路径计数；
- `outputs/data/path_basis_cache.npz`：0--3阶复数路径基缓存。

所有图像均由 `run_experiment.py` 从上述数据生成。实验显式使用 DrJit 反射后端；官方验证器对当前版本组合的 native reflected EPC 限制仍然保留。

# WiTwin GPU 仿真与实验

此目录归属 `work/wsl-witwin`，用于 WiTwin 仿真、参数反演、实验脚本和经过筛选
的可复现结果。

当前分支状态见 [`docs/current/branches/work-wsl-witwin.md`](../../docs/current/branches/work-wsl-witwin.md)，已完成实验的 Markdown 报告统一归档在 [`docs/history/branches/work-wsl-witwin/experiments/`](../../docs/history/branches/work-wsl-witwin/experiments/)。

## 内容

- `experiments/`：已有 `w_geo`、长轨迹和早期 `w_hd` 的脚本、数据、图像与 README 导航；
- `artifacts/multipath_preview/`：已有多径预览结果；
- WiTwin Core/Channel 源码仍位于仓库根目录 `src/`；
- 完整环境验证入口仍为仓库根目录 `validate_witwin.py`。

运行现有实验时使用 `/opt/witwin/venv/bin/python`。历史实验报告记录工作区提交、两个源码子模块提交、依赖版本、配置和随机种子；新报告应写入 `docs/history/branches/work-wsl-witwin/experiments/`。

当前固定组合的确定性信道、LOS、CIR 和 CFR 已通过；`max_bounces > 0` 的当前
上游反射路径组合仍未验证。使用显式 DrJit 反射后端得到的独立实验结果不能写成
RayD native EPC 已获得通用兼容性验证。

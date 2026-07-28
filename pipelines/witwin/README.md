# WiTwin GPU 仿真与实验

此目录归属 `work/wsl-witwin`，用于 WiTwin 仿真、参数反演、实验脚本和经过筛选
的可复现结果。

## 内容

- `experiments/`：已有 `w_geo`、长轨迹和早期 `w_hd` 实验；
- `artifacts/multipath_preview/`：已有多径预览结果；
- WiTwin Core/Channel 源码仍位于仓库根目录 `src/`；
- 完整环境验证入口仍为仓库根目录 `validate_witwin.py`。

运行现有实验时使用 `/opt/witwin/venv/bin/python`。实验文档应同时记录工作区
提交、两个源码子模块提交、依赖版本、配置和随机种子。

当前固定组合的确定性信道、LOS、CIR 和 CFR 已通过；`max_bounces > 0` 的当前
上游反射路径组合仍未验证。使用显式 DrJit 反射后端得到的独立实验结果不能写成
RayD native EPC 已获得通用兼容性验证。

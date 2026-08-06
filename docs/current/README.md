# 当前文档总览

更新时间：2026-08-06

本目录只保存仍在维护的“活文档”。开始新任务时，先阅读总体进展，再阅读对应分支状态。

## 项目主文档

- [项目当前进展与下一步方向](项目当前进展与下一步方向.md)：跨分支总体状态与近期优先级。
- [科研项目精简执行计划](project/前置深度增强科研项目精简执行计划.md)：日常执行使用的简洁计划。
- [科研项目详细待办与验证计划](project/前置深度增强的科研项目待办与验证计划.md)：完整科学问题、实验设计、门槛与风险边界。
- [COLMAP 官方数据集首次验证报告](project/COLMAP官方数据集首次验证报告_2026-08-06.md)：RTX 4050 Laptop 在 WSL/Docker 中从空数据库完成稀疏和稠密重建的实测证据。
- [iPhone 到 WSL 建模执行分析](project/iPhone到WSL建模执行分析与下一步_2026-08-06.md)：跨端已完成能力、责任边界和暂缓的后续计划。

## 分支最新状态

| 分支 | 负责范围 | 最新状态文档 |
| --- | --- | --- |
| `main` | 已验证集成状态、公共协议和跨端数据契约 | [main](branches/main.md) |
| `work/ios-recorder` | iPhone、ARKit、CoreMotion、视频和 UDP 发送 | [work/ios-recorder](branches/work-ios-recorder.md) |
| `work/csi-linux` | PicoScenes、CSI/UDP 接收、筛选和时钟映射 | [work/csi-linux](branches/work-csi-linux.md) |
| `work/wsl-witwin` | WiTwin 仿真、离线分析、重建和真实数据算法 | [work/wsl-witwin](branches/work-wsl-witwin.md) |

分支状态文档只写“当前结论、当前缺口、下一步和交接边界”；完整实验数字和历史过程应链接到 [历史文档](../history/README.md)。

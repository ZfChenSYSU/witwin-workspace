# 当前文档总览

更新时间：2026-09-09

本目录只保存仍在维护的“活文档”。开始新任务时，先阅读总体进展，再阅读对应分支状态。

## 项目主文档

- [项目当前进展与下一步方向](项目当前进展与下一步方向.md)：跨分支总体状态与近期优先级。
- [科研执行计划](project/科研执行计划.md)：日常任务顺序和里程碑。
- [研究设计与验证标准](project/研究设计与验证标准.md)：完整科学问题、实验设计、门槛与风险边界。
- [LiDAR iPhone 与 WiTwin 服务器迁移计划](project/LiDAR与服务器迁移计划.md)：当前设备和运行环境迁移任务与验收边界。

## 分支最新状态

| 分支 | 负责范围 | 最新状态文档 |
| --- | --- | --- |
| `main` | 已验证集成状态、公共协议和跨端数据契约 | [main](branches/main.md) |
| `work/ios-recorder` | 带 LiDAR iPhone、ARKit、CoreMotion、视频和 UDP 发送 | [work/ios-recorder](branches/work-ios-recorder.md) |
| `work/csi-linux` | PicoScenes、CSI/UDP 接收、筛选和时钟映射 | [work/csi-linux](branches/work-csi-linux.md) |
| `work/wsl-witwin` | 当前保留的分支名；服务器 WiTwin、离线分析、重建和真实数据算法 | [work/wsl-witwin](branches/work-wsl-witwin.md) |

分支状态文档只写“当前结论、当前缺口、下一步和交接边界”；完整实验数字和历史过程应链接到 [历史文档](../history/README.md)。

`work/wsl-witwin` 是当前仍存在的分支名；其目标执行环境已调整为服务器。是否重命名
分支将在服务器迁移验证完成后单独决定。

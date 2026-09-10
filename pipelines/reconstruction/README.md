# 视频 SLAM 与房间三维重建

此目录用于服务器端的 RGB、LiDAR 与 ARKit 房间重建流水线，对应当前保留的工作分支
`work/wsl-witwin`。

当前进度和下一步见 [`docs/current/branches/work-wsl-witwin.md`](../../docs/current/branches/work-wsl-witwin.md)，算法调研见 [`docs/reference/research/IPHONE_SLAM_SPATIAL_MODELING_RESEARCH_2026-07-29.md`](../../docs/reference/research/IPHONE_SLAM_SPATIAL_MODELING_RESEARCH_2026-07-29.md)。本目录只维护代码入口，不再存放独立进度报告。

## 输入

- iOS 端后置视频或逐帧图像；
- ARKit 帧时间戳、相机内参、图像尺寸和 tracking state；
- ARKit 米制相机位姿；
- CoreMotion IMU；
- 目标设备实际支持并写入新版 session 的场景深度、置信度、场景网格或 RoomPlan 输出；
- session 元数据和校验和。

## 基线流程

```text
session 与 LiDAR 完整性检查
  -> RGB、深度、位姿和网格时间/坐标对齐
  -> LiDAR/ARKit 房间几何基线
  -> 视觉 SfM/MVS 或 RGB-D 融合作为对照与补全
  -> 平面正则化、网格化与材料区域标注
  -> 导出 WiTwin 可使用的统一房间坐标模型
```

首版具体采用 ARKit mesh、RoomPlan、RGB-D 融合还是 LiDAR 辅助 COLMAP，须经目标
设备小样例比较后冻结。人工测距或标定物用于独立尺度与几何精度检查。

后续代码应从 `schemas/session-format/` 读取统一字段，不在本目录复制一套独立
时间戳或坐标约定。

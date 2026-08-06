# South Building 重建测试记录（2026-08-06）

## 数据

- 来源：[COLMAP 官方 South Building 发布包](https://github.com/colmap/colmap/releases/download/3.11.1/south-building.zip)
- 本地压缩包：`testdata/south-building.zip`，约 400 MB；解压后包含 128 张图像、数据库和官方稀疏模型。
- 解压目录：`testdata/south-building/`

## 结果

- COLMAP 稀疏 mapper：成功注册 128/128 张图像，约 61,128 个三维点，平均重投影误差约 0.513 px。
- image undistorter：128/128 张图像成功处理。
- PatchMatch：800 px、5 samples、2 iterations 的受控 CUDA 稠密匹配成功完成。
- stereo fusion：成功融合 891,084 个点，输出 `testdata/south-building/dense/fused.ply`。

## 输出与日志

- 稀疏模型：`testdata/south-building/reconstruction/0/`
- 稠密工作区：`testdata/south-building/dense/`
- 日志：`logs/reconstruction-south-building-{mapper,undistorter,patchmatch,fusion}-2026-08-06.log`
- 下载校验日志：`logs/testdata-south-building-download-2026-08-06.log`

整个测试使用项目内运行时库路径和临时目录，未写入系统目录。重建期间磁盘余量最低约 15 GB，未触发约定的 8 GB 停止阈值。

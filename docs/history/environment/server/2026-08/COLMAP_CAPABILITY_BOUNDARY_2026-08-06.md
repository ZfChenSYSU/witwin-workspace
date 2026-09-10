# 当前 COLMAP 能力边界

日期：2026-08-06

本文件区分“已安装”“已实际验证”和“尚未验证或尚未实现”。其他 Agent 不应根据
二进制中存在某个命令，就推断对应的生产流水线已经可用。

## 1. 已安装环境

- COLMAP：4.0.4，官方标签，提交 `9c23f6942fe69962e06030905e77067c8673382f`。
- 构建方式：headless、shared libraries、CUDA ON、ONNX ON、GUI OFF、Tests OFF、
  CGAL OFF，`CMAKE_CUDA_ARCHITECTURES=120`。
- GPU 目标：RTX 5090 / Blackwell / Compute Capability 12.0。
- 项目 CUDA 编译组件：12.8 系列；NVCC 12.8.93。
- Python：3.12；PyCOLMAP 4.0.4、Open3D 0.19.0、OpenCV headless、SciPy、
  pandas、PyYAML、Pillow、Trimesh 和 scikit-learn 已安装。

关键路径：

```text
环境       /root/nfs/chenzhf/witwin/env
COLMAP 源码 /root/nfs/chenzhf/witwin/tools/src/colmap-4.0.4
构建树      /root/nfs/chenzhf/witwin/tools/build/colmap-4.0.4
安装前缀    /root/nfs/chenzhf/witwin/tools/colmap-4.0.4
日志       /root/nfs/chenzhf/witwin/logs
```

运行前必须设置：

```bash
WITWIN_ROOT=/root/nfs/chenzhf/witwin
export PATH="$WITWIN_ROOT/env/bin:$WITWIN_ROOT/tools/colmap-4.0.4/bin:$PATH"
export LD_LIBRARY_PATH="$WITWIN_ROOT/env/lib:$WITWIN_ROOT/tools/colmap-4.0.4/lib:$WITWIN_ROOT/tools/colmap-4.0.4/thirdparty"
```

## 2. 已确认存在的命令

`colmap -h` 已确认包含：

- `global_mapper`；
- `mapper`；
- `pose_prior_mapper`；
- `patch_match_stereo`；
- `stereo_fusion`；
- `mesh_simplifier`；
- `model_orientation_aligner`。

这只证明命令已编译进二进制，不等于所有命令都已通过数据验证。

## 3. 已实际验证的能力

使用 COLMAP 官方 South Building 数据集完成了受控测试：

- 输入图像：128 张；
- 稀疏建图使用数据包附带的 `database.db`，执行 `mapper`；
- 注册图像：128/128；
- 稀疏点：61,128；
- observations：326,926；
- 平均轨迹长度：5.348220；
- 平均重投影误差：0.512568 px；
- `image_undistorter` 成功处理 128 张图像；
- CUDA PatchMatch 使用 `max_image_size=800`、`num_samples=5`、
  `num_iterations=2`，完成 128/128 个视图；
- 生成 256 个深度图和 256 个法向图，分别包含 photometric 与 geometric 输出；
- `stereo_fusion` 生成 891,084 点的融合点云；
- Open3D 能独立读取点云，坐标和法向均为有限值，点、法向和颜色数量一致。

主要输出：

```text
/root/nfs/chenzhf/witwin/testdata/south-building/reconstruction/0
/root/nfs/chenzhf/witwin/testdata/south-building/dense/fused.ply
```

详细结果见 `SOUTH_BUILDING_RECONSTRUCTION_TEST_2026-08-06.md`。

## 4. 尚未验证或尚未实现

以下能力不能宣称已经通过：

1. 从空数据库对 iPhone 图像运行 CUDA SIFT 特征提取和匹配。
2. COLMAP 内置 ALIKED + LightGlue ONNX 前端。
3. `global_mapper` 在本机数据上产生非空模型。
4. `pose_prior_mapper` 接收 ARKit 位姿先验并产生非空模型。
5. ARKit 相机内参、图像方向、裁剪和稳像信息到 COLMAP 相机模型的可靠转换。
6. ARKit 轨迹与视觉轨迹的 RANSAC + Sim(3) 米制对齐。
7. CoreMotion 与图像时间轴的离线同步和质量分析。
8. Poisson 网格、`mesh_simplifier`、平面拟合、Manhattan 正则化、补洞和闭合性检查。
9. 在 iPhone 实采数据上的几何精度、尺度漂移、回环质量和弱纹理鲁棒性。
10. 大规模或高分辨率 session 的时间、显存、内存和磁盘容量边界。

当前 `pipelines/reconstruction/` 只有流程说明，没有可直接执行的一键导入和重建
脚本。因此，原始 iPhone session 目前不能直接导入后自动得到米制闭合房间网格。

## 5. 可以和不可以做什么

### 当前可以

- 对已整理为 JPG/PNG 的小型图像集手动运行 COLMAP 稀疏/稠密重建。
- 使用 `mapper`、PatchMatch 和 fusion 进行受控实验。
- 使用 PyCOLMAP/Open3D/Trimesh 读取与分析模型和点云。
- 开发并验证 iPhone session 导入、位姿转换和 Sim(3) 工具。

### 当前不能直接承诺

- 将 `.mov`、ARKit CSV/JSON 和 IMU 文件直接一键建模。
- 输出已经过尺度、坐标方向和绝对精度验证的米制模型。
- 直接得到可供 WiTwin 使用的闭合低多边形、材料分区房间模型。
- 在当前约 14 GB 剩余空间上运行不受控的完整高分辨率稠密重建。

## 6. 后续验收顺序

1. 用小型 iPhone 图像集从空数据库验证 CUDA SIFT 与 sequential matcher。
2. 在同一数据上验证 ALIKED + LightGlue，保存对照指标。
3. 分别验证 `mapper`、`global_mapper` 和 `pose_prior_mapper`。
4. 验证 ARKit 位姿方向、内参和时间戳转换。
5. 实现并用合成变换测试 Sim(3)，再对真实轨迹评估残差。
6. 运行受控 PatchMatch/fusion，确认 Blackwell 输出非空。
7. 验证网格化、简化、平面、Manhattan 和闭合性检查。
8. 使用人工测距或标定物评估米制尺度与几何误差。

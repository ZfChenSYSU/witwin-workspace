# iPhone Session 导入与分析需求

日期：2026-08-06

本文定义无 LiDAR iPhone 数据进入服务器重建流水线前必须具备的信息、建议目录、
校验步骤和待实现工具。它是导入器设计依据，不表示当前已经存在一键导入程序。

## 1. 支持目标

首选输入是一次完整、不可变的采集 session，而不是只有一个视频文件。流水线目标为：

```text
后置 RGB/视频 + ARKit 内参/位姿/tracking + CoreMotion
  -> 完整性和时间轴检查
  -> 抽帧、方向与内参归一化
  -> 清晰关键帧和覆盖度筛选
  -> COLMAP 特征、匹配和稀疏模型
  -> ARKit/视觉轨迹 Sim(3) 米制对齐
  -> 稠密点云、网格和房间几何检查
```

仅有照片或视频时可以运行纯视觉 COLMAP，但模型尺度不确定，也无法验证 ARKit 轨迹、
时间同步和逐帧内参。

## 2. 必需输入

### RGB 数据

至少提供一种：

- 原始后置相机视频及其容器时间戳；或
- 未重复编码的逐帧图像及文件名到时间戳的映射。

同时记录：编码、分辨率、帧率模式、设备方向、是否镜像、颜色空间，以及是否发生
裁剪、电子稳像或其他会改变有效内参的处理。

### 每帧 ARKit 数据

每个候选视频帧至少需要：

- 单调时钟时间戳及单位；
- 对应视频 PTS 或图像文件名；
- 图像宽高和方向；
- `fx`、`fy`、`cx`、`cy`；
- 内参对应的参考图像尺寸；
- tracking state 和有限跟踪原因；
- `arkit_world_T_rear_camera` 4×4 矩阵；
- 矩阵存储顺序、坐标系方向和长度单位。

统一命名遵循 `schemas/session-format/coordinate_frames.md`：矩阵采用
`target_T_source`，右手坐标系，平移单位为米，文件落盘时使用行主序并显式声明。

### CoreMotion 数据

至少记录：

- 单调时钟时间戳及单位；
- 加速度和角速度及单位；
- device motion 姿态或旋转矩阵的参考系定义；
- gravity 与 user acceleration 的字段语义；
- 采样率和缺样信息。

### Session 元数据

至少包含：

- `schema_version` 和唯一 `session_id`；
- 采集开始/结束时间；
- iPhone 型号、iOS 版本和采集 App 版本；
- 相机配置、视频配置和 ARKit 配置；
- 每个文件的相对路径、字节数和 SHA-256；
- 采集是否正常结束以及已知异常；
- 坐标规范文档路径；
- 代码提交或构建版本（若可用）。

现有公共元数据入口为 `schemas/session-format/session.schema.json`，但当前 Schema 主要
覆盖三端公共 session 信息，尚不足以表达全部逐帧相机和 IMU 字段。扩展时必须保持
版本化，不能在导入脚本里另造不兼容的隐式格式。

## 3. 建议落盘结构

以下是服务器导入器的建议结构，实施前可根据真实 iOS 输出做兼容映射：

```text
<session_id>/
├── manifest.json
├── raw/
│   ├── rear_camera.mov
│   ├── arkit_frames.csv
│   ├── coremotion.csv
│   └── checksums.sha256
├── derived/
│   ├── frames/
│   ├── frame_manifest.parquet
│   ├── quality_metrics.parquet
│   └── keyframes/
├── colmap/
│   ├── database.db
│   ├── sparse/
│   └── dense/
├── alignment/
│   ├── trajectory_correspondences.csv
│   └── sim3_result.json
├── mesh/
└── reports/
```

`raw/` 内容视为不可变输入。派生文件、数据库和重建结果必须写入其他子目录，不覆盖
原始采集数据。

小型受控 session 可放在：

```text
/root/nfs/chenzhf/witwin/testdata/sessions/<session_id>
```

正式数据应使用用户指定的大容量数据盘，并在 Git 文档中记录其逻辑位置，不提交
视频、深度图、点云或网格。

## 4. 导入前分析

导入器必须在运行 COLMAP 前生成机器可读报告，并检查：

1. manifest 和校验和完整，文件大小与声明一致；
2. 视频可以完整解码，时长、帧数、分辨率和旋转元数据可读取；
3. RGB、ARKit、CoreMotion 时间戳单调，没有重复、逆序或大段缺口；
4. 视频帧与 ARKit 记录可以按同一时基建立匹配；
5. 内参为有限值，主点和焦距与图像尺寸合理；
6. 位姿矩阵为有限值，旋转接近正交且行列式接近 +1；
7. 平移单位确认为米，轨迹速度和范围不存在明显数量级错误；
8. tracking state 分布、有限跟踪区间和重新定位事件已统计；
9. IMU 单位、采样率、缺样和饱和情况已统计；
10. 可用空间足以容纳抽帧、数据库和受控重建输出。

检查失败必须明确指出文件、字段、时间区间和原因，不能静默丢弃异常记录。

## 5. 关键帧与相机处理需求

- 抽帧必须保存视频 PTS、手机单调时间戳和 ARKit 记录之间的映射。
- 根据实际编码方向旋转图像后，必须同步变换内参和图像尺寸。
- 如果视频稳像、裁剪或缩放改变有效成像区域，不能直接使用未经修正的 ARKit 内参。
- 质量指标至少包括清晰度、曝光、运动幅度、tracking state 和与相邻帧的时间间隔。
- 关键帧选择应同时考虑图像质量、视角基线和空间覆盖，不只使用固定时间间隔。
- 所有阈值写入版本化配置，并随实验报告保存，不在脚本中隐藏硬编码。

## 6. 位姿与尺度处理需求

ARKit 保存的是约定明确的 `arkit_world_T_rear_camera`。COLMAP 优化和文件接口可能
使用 world-to-camera 形式，转换时必须显式求逆并验证旋转、平移和四元数顺序。

建议验证顺序：

1. 用合成相机和已知点验证矩阵方向；
2. 验证图像旋转前后投影点一致；
3. 将相同时间戳的 ARKit 与 COLMAP 相机中心建立对应；
4. 使用 RANSAC 估计 Sim(3)，拒绝 tracking 异常和视觉外点；
5. 保存尺度、旋转、平移、内点数和残差分布；
6. 使用人工测距或标定物独立检查米制误差。

不得仅因为 ARKit 平移单位为米，就认定未经对齐的 COLMAP 模型已经是正确米制坐标。

## 7. 待实现的软件组件

可提交代码应放在：

```text
/root/nfs/chenzhf/witwin/repository/pipelines/reconstruction
```

至少需要：

- `inspect_session`：完整性、格式、时间轴、内参、位姿和 IMU 报告；
- `extract_frames`：保持时间映射的抽帧和方向处理；
- `select_keyframes`：质量、基线和覆盖度筛选；
- `prepare_colmap`：相机、图像、数据库和可选 pose prior 准备；
- `run_reconstruction`：可恢复的 sparse/dense 分阶段执行；
- `align_arkit_colmap`：RANSAC + Sim(3) 对齐与残差报告；
- `analyze_geometry`：点云、平面、尺度、网格和闭合性检查；
- 小型合成 fixture、格式测试和坐标变换单元测试。

大型输出只写入运行时数据目录；Git 中只保存脚本、Schema、配置、小型 fixture 和结果
摘要。

## 8. 首个真实 session 的验收要求

- 原始文件校验通过且保留不变；
- 每个关键帧能追溯到视频 PTS、手机时间戳和 ARKit 记录；
- 内参和方向转换通过投影测试；
- CUDA 特征提取和匹配从空数据库成功；
- `mapper`、`global_mapper` 和 `pose_prior_mapper` 至少分别形成可分析结果；
- 记录注册率、重投影误差、轨迹覆盖和失败图像；
- Sim(3) 保存内点率、尺度和残差，且通过独立米制检查；
- PatchMatch 深度图非空，fusion 点云可由 Open3D 读取；
- 网格报告包含法向、连通分量、孔洞、非流形边和闭合性；
- 所有命令、版本、配置、日志路径、输出路径和磁盘峰值写入报告。

## 9. 导入前需要采集端确认的信息

在收到首个 iPhone session 后，先确认：

- 采集 App 和分支/提交版本；
- 实际文件树及单个小样例；
- 视频方向、编码、分辨率和是否启用稳像；
- 视频 PTS 与 ARKit/CoreMotion 时钟的对应方式；
- 位姿矩阵方向、存储顺序和单位；
- 内参对应的分辨率及是否随帧变化；
- session 总大小和期望输出（点云、网格或 WiTwin 房间模型）；
- 是否有人工测距、标定物或已知房间尺寸可作为独立真值。

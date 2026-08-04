# iPhone IMU、视频与可选 LiDAR 的室内空间建模算法调研

日期：2026-07-29
时区：Asia/Shanghai

关联文档：

- [`前置深度增强的科研项目待办与验证计划`](../../current/project/前置深度增强的科研项目待办与验证计划.md)
- [`iPhone 11 Pro 多模态采集与 SLAM 建模工程交接`](../../history/branches/work-ios-recorder/IPHONE_11_PRO_IMPLEMENTATION_CONTEXT.md)
- [`视频 SLAM 与房间三维重建`](../../../pipelines/reconstruction/README.md)

## 1. 用户问题

> 根据《前置深度增强的科研项目待办与验证计划》，调研相关领域的论文和综述，告诉我用 iPhone 所拿到的 IMU 和视频，在没有 LiDAR 和有 LiDAR 两种情况下，通过 SLAM 做空间环境建模的最佳 SLAM 算法或其他算法是什么？

## 2. 结论摘要

结合项目需要的最终输出——可用于 WiTwin 射线追踪的米制、坐标可对齐、可简化并可标注材料区域的房间网格——最佳方案不是只选择一个 SLAM 程序。

截至 2026 年 7 月，建议为：

- **无后置 LiDAR**：采用“ARKit VIO + COLMAP 4 全局 SfM/Bundle Adjustment + 稠密 MVS + 平面正则化网格”的混合流水线。
- **有后置 LiDAR**：采用“ARKit VIO + `sceneDepth`/置信度 + RGB-D 位姿图优化 + TSDF 融合 + RoomPlan/平面约束”的混合流水线。
- 对 WiTwin 射线追踪而言，最终重要的是**米制、闭合、低多边形、主要传播面正确并且可标材料区域的三角网格**，而不是只得到定位轨迹、稀疏点云、NeRF 或视觉效果良好的 3D Gaussian Splatting。

如果必须给出一个软件或算法名称：

| 条件                            | 首选                                                    |
| ------------------------------- | ------------------------------------------------------- |
| 无 LiDAR，离线完整建模软件栈    | COLMAP 4`global_mapper + pose prior + PatchMatch MVS` |
| 无 LiDAR，在线手机位姿          | ARKit VIO                                               |
| 无 LiDAR，开源 VIO 对照         | ORB-SLAM3 mono-inertial                                 |
| 无 LiDAR，现代稠密 SLAM 对照    | MASt3R-SLAM，使用 ARKit 恢复米制尺度                    |
| 有 iPhone LiDAR，开源 SLAM 后端 | RTAB-Map RGB-D，以 ARKit 位姿为初值                     |
| 有 LiDAR，离线最终几何          | ARKit pose + Open3D TSDF + RoomPlan                     |

## 3. 无 LiDAR：iPhone 11 Pro 的推荐方案

当前主设备 iPhone 11 Pro 没有后置 LiDAR，但可以采集：

- 后置 RGB；
- ARKit 世界跟踪和米制六自由度位姿；
- CoreMotion 原始加速度计和陀螺仪数据；
- 前置 TrueDepth 支持的人脸三维跟踪；
- 与每帧图像对应的 ARKit 时间戳和逐帧相机内参。

推荐流水线为：

```text
ARKit 后置 RGB + ARKit 米制位姿 + CoreMotion
    ↓
清晰关键帧选择、固定后置广角镜头
    ↓
ALIKED/DISK/SIFT + LightGlue 匹配
    ↓
COLMAP 4 global mapper（GLOMAP）或 incremental mapper
    + ARKit 位置/重力先验
    ↓
全局 Bundle Adjustment
    ↓
与 ARKit 轨迹进行 RANSAC + Sim(3) 米制对齐
    ↓
COLMAP PatchMatch MVS / MVSFormer++ 稠密深度
    ↓
深度融合、离群点清理
    ↓
墙—地—顶平面拟合、Manhattan/正交约束、补洞
    ↓
低多边形闭合房间网格 + 材料区域
```

### 3.1 为什么使用 ARKit 作为主位姿源

现有 iOS 采集程序已经取得严格对应的：

- `ARFrame.capturedImage`；
- `ARCamera.transform`；
- 逐帧相机内参；
- ARKit 米制世界坐标；
- 手机单调时间戳。

ARKit 内部已经处理相机—IMU 标定、时序、IMU 偏置和手机滚动快门等工程问题。已有实机研究对 Apple ARKit、Google ARCore、Intel RealSense T265 和 ZED 2 进行比较，ARKit 在其测试的室内外场景中表现出较好的定位一致性和准确性。

因此，重新把目前记录的独立 CoreMotion 数据直接送入 ORB-SLAM3 或 VINS-Fusion，不一定会优于 ARKit。开源 VIO 还需要额外完成：

- 后置相机—IMU 固定外参；
- 摄像头和 IMU 时延；
- 加速度计和陀螺仪噪声密度；
- 随机游走参数；
- 滚动快门读出模型；
- 单位、坐标轴和重力方向转换。

所以 ARKit 应作为默认在线位姿源，开源 VIO 用于独立对照和误差审计。

### 3.2 为什么还要使用 COLMAP

ARKit 位姿不能被当作几何真值，但适合提供：

- 初始米制尺度；
- 重力方向；
- 大致相机轨迹；
- 失跟踪和低质量片段标志。

COLMAP 的视觉重投影误差和全局 Bundle Adjustment 可以进一步修正轨迹及场景结构。COLMAP 4 已将 GLOMAP 集成为 `global_mapper`，还提供带协方差的位置先验和 pose-prior Bundle Adjustment。

建议同时运行：

1. `global_mapper`；
2. 传统 incremental mapper；
3. 使用 ARKit 位置先验的 pose-prior mapper。

根据注册图像比例、重投影误差、闭环漂移和外部测距真值选择结果，不能只根据模型视觉效果判断。

### 3.3 为什么 SLAM 稀疏地图不能直接用于射线追踪

ORB-SLAM3 和 VINS-Fusion 主要输出轨迹与定位用稀疏特征点。这种稀疏地图缺少：

- 完整墙面；
- 地板和天花板边界；
- 门窗开口；
- 稳定法向；
- 闭合拓扑；
- 可用于材料标注的连续三角面。

因此还必须进行多视图稠密重建和房间结构化处理。COLMAP PatchMatch MVS 是可解释、成熟且适合成为论文基线的稠密后端。

### 3.4 白墙和弱纹理的处理

室内白墙、玻璃、重复纹理和曝光变化容易使传统 ORB/SIFT 跟踪或 MVS 失败。建议：

- 使用 ALIKED、DISK 或 SuperPoint 与 LightGlue 构建学习型匹配对照；
- 扫描时保持相邻视角至少约 70% 重叠；
- 缓慢平移，避免只有原地旋转；
- 临时布置可移除的 AprilTag、ArUco 或纹理纸；
- 对墙面采用 RANSAC 平面拟合和 Manhattan/正交约束；
- 对玻璃和镜面区域单独记录为高风险材料区域；
- 不允许单目深度网络未经多视图一致性验证直接填充主传播面。

## 4. 无 LiDAR 方法对比

| 方法                    | 适合承担的角色                 | 主要限制                           | 项目结论        |
| ----------------------- | ------------------------------ | ---------------------------------- | --------------- |
| ARKit VIO               | 主在线位姿、米制坐标和重力方向 | 无 LiDAR 时不直接输出稠密房间网格  | 主线            |
| COLMAP 4/GLOMAP         | 离线全局 SfM、BA 和 MVS        | 需要良好覆盖，白墙可能产生孔洞     | 主线            |
| ORB-SLAM3 mono-inertial | 开源视觉惯性轨迹对照           | 稀疏地图；标定和同步要求高         | 必做 baseline   |
| VINS-Mono/VINS-Fusion   | VIO 和时延/外参研究对照        | 不直接交付稠密网格                 | 可选 baseline   |
| MASt3R-SLAM             | 弱纹理条件下的实时稠密 SLAM    | 单目尺度和几何偏差仍需验证         | 强 challenger   |
| VGGT/GLUEMAP            | 弱纹理、低重叠下的现代 SfM     | 学习先验可能产生几何幻觉           | 研究 challenger |
| DROID-SLAM              | 鲁棒视觉轨迹与稠密深度对照     | 原始系统不使用 IMU，单目尺度不确定 | 可选 baseline   |
| VINGS-Mono/3DGS SLAM    | 新视角合成和视觉展示           | Gaussian 不是闭合传播面网格        | 不作为最终模型  |

MASt3R-SLAM 和 VGGT 值得加入实验，但不能直接替代 COLMAP/MVS 和外部测量验证。它们更适合：

- 找出传统特征匹配失败片段；
- 生成候选深度或点图；
- 与传统多视图几何互相验证；
- 作为论文中的现代学习方法对照。

## 5. 有 iPhone 后置 LiDAR：推荐方案

iPhone LiDAR 在 ARKit 中主要提供与后置相机对齐的：

- `sceneDepth`；
- `smoothedSceneDepth`；
- `confidenceMap`；
- `ARMeshAnchor`；
- `sceneReconstruction` 网格。

这种传感器输出更接近 RGB-D 深度相机，不是机械式或 360° 三维激光雷达扫描。因此不建议直接使用：

- FAST-LIO2；
- LIO-SAM；
- LOAM；
- 面向旋转式激光雷达扫描线的 LiDAR-inertial SLAM。

推荐流水线为：

```text
ARKit VIO 位姿
+ RGB
+ sceneDepth
+ confidenceMap
+ ARMeshAnchor
+ RoomPlan 参数化结果
    ↓
置信度过滤、RGB–Depth 对齐
    ↓
RGB-D odometry / ICP 局部细化
    ↓
RTAB-Map 或 Open3D pose graph 闭环优化
    ↓
按优化后位姿重新进行 confidence-weighted TSDF 融合
    ↓
Marching Cubes 提取三角网格
    ↓
以 RoomPlan 修正墙、门窗、地面和天花板拓扑
    ↓
大型家具使用 TSDF 网格或简化包围几何
```

### 5.1 各模块的职责

- **ARKit**：在线视觉惯性定位和初始米制位姿。
- **RTAB-Map**：RGB-D 节点、回环检测和全局位姿图优化；可接受 ARKit 作为外部里程计初值。
- **Open3D TSDF**：根据置信度和优化后的相机位姿融合深度，抑制随机噪声并提取三角网格。
- **RoomPlan**：输出墙、门窗、房间尺寸和大型家具类别的参数化结构。
- **ARKit scene reconstruction mesh**：最快的直接网格 baseline，但不建议未经优化和清理直接作为最终 WiTwin 网格。

### 5.2 最适合射线追踪的融合形式

最终场景建议采用：

```text
RoomPlan/平面拟合产生的干净房间外壳
        +
TSDF 产生的大型家具和障碍物几何
```

其原因是：

- 墙、地面、天花板和门窗需要干净、连续、低多边形的传播表面；
- 大型家具需要保留对遮挡和主要反射有影响的几何；
- 原始 ARKit 网格可能存在噪声、重复面、孔洞和过多三角形；
- RoomPlan 的家具通常是参数化类别或包围几何，不能完全代替实际表面；
- TSDF 和 RoomPlan 相互补充，比单独使用任意一种更适合无线传播场景。

## 6. 针对当前工程的实验建议

当前 iPhone 11 Pro 无后置 LiDAR，近期应运行以下四条对照：

| 编号 | 方案                                    | 目的                       |
| ---- | --------------------------------------- | -------------------------- |
| R-0  | ARKit 原始轨迹                          | 手机现成 VIO baseline      |
| R-1  | ORB-SLAM3 mono-inertial                 | 开源 VIO 独立 baseline     |
| R-2  | COLMAP 4 global/pose-prior mapper + MVS | 无 LiDAR 主方法            |
| R-3  | MASt3R-SLAM + ARKit Sim(3) 尺度对齐     | 学习型稠密 SLAM challenger |

如果可以增加一台支持后置 LiDAR 的 iPhone，建议另外运行：

| 编号 | 方案                                        | 目的                  |
| ---- | ------------------------------------------- | --------------------- |
| L-0  | ARKit`sceneReconstruction` 原始网格       | 最低成本 baseline     |
| L-1  | RoomPlan 参数化房间                         | 干净结构模型 baseline |
| L-2  | ARKit pose + Open3D TSDF                    | LiDAR 稠密几何主方法  |
| L-3  | RTAB-Map RGB-D pose graph + TSDF + RoomPlan | 有 LiDAR 完整主方法   |

LiDAR 手机可以单独扫描静态房间，再用 AprilTag、控制点、已知墙角或刚体配准把房间模型与 iPhone 11 Pro 的 CSI 采集轨迹统一到同一个房间坐标系。

## 7. 验证指标

不能只报告重建模型截图。至少需要评价：

### 7.1 轨迹

- ATE；
- RPE；
- 闭环首尾误差；
- ARKit、ORB-SLAM3、COLMAP 轨迹间的 Sim(3)/SE(3) 残差；
- tracking lost 次数和恢复时间；
- 多次重复扫描之间的轨迹一致性。

### 7.2 房间几何

- 关键墙长、房间长宽高误差；
- 墙面点到拟合平面的 RMSE 和 95% 误差；
- 相邻墙面夹角误差；
- 网格完整率；
- 孔洞、重复面、退化三角形和错误法向数量；
- 与独立激光测距、标定物或高精扫描真值的 Chamfer/点到面距离；
- 重复扫描间的网格一致性。

### 7.3 WiTwin 下游指标

- 手机轨迹和房间网格的坐标对齐误差；
- 主要射线路径是否稳定；
- 网格版本变化对路径长度、到达角和反射点的影响；
- 几何误差对 CFR/CIR 的敏感性；
- 使用留出轨迹和留出 session 时，估计材料参数 `theta` 的一致性；
- 房间模型改变后，CSI 测试残差是否真正下降。

## 8. 与 Wi-Fi 相位精度的关系

即使使用 iPhone LiDAR，也不能把所得网格当作测量级几何真值。5 GHz 的自由空间波长约为 6 cm，厘米级路径长度误差已经可能造成较大的相位变化。

因此：

- 必须报告房间尺度和主墙面的几何误差；
- 激光测距或高精扫描应作为独立验证真值；
- 商品 Wi-Fi CSI 的绝对相位仍需处理 CFO、SFO、PDD、公共相位和硬件响应；
- 若几何精度不足以支撑绝对相位，应优先研究幅度、校准后的相对相位或 CIR 统计；
- LiDAR 只能提供几何，不能直接识别墙体和家具的电磁材料参数。

## 9. 最终推荐

### 当前 iPhone 11 Pro

```text
ARKit VIO
  → COLMAP 4 global/pose-prior BA
  → PatchMatch MVS
  → 平面拟合与 Manhattan 正则化
  → 闭合、简化、材料分区的 WiTwin 房间网格
```

ORB-SLAM3 作为开源独立轨迹 baseline，MASt3R-SLAM 作为现代学习型 challenger。

### 如果增加后置 LiDAR 设备

```text
ARKit VIO + sceneDepth/confidence
  → RTAB-Map/Open3D 位姿图细化
  → confidence-weighted TSDF
  → RoomPlan/平面约束
  → WiTwin 房间网格
```

对于白墙、弱纹理和主要依赖干净传播面的室内无线建模，有 LiDAR 的路线明显更稳妥，但仍需独立测距和重复扫描验证。

## 10. 论文、综述与官方资料

### 视觉、视觉惯性 SLAM 与 SfM

1. Campos et al., *ORB-SLAM3: An Accurate Open-Source Library for Visual, Visual-Inertial and Multi-Map SLAM*, IEEE TRO 2021.[https://doi.org/10.1109/TRO.2021.3075644](https://doi.org/10.1109/TRO.2021.3075644)
2. ORB-SLAM3 官方实现。[https://github.com/UZ-SLAMLab/ORB_SLAM3](https://github.com/UZ-SLAMLab/ORB_SLAM3)
3. Kim et al., *An Empirical Evaluation of Four Off-the-Shelf Proprietary Visual-Inertial Odometry Systems*, 2022.[https://arxiv.org/abs/2207.06780](https://arxiv.org/abs/2207.06780)
4. Cortés et al., *ADVIO: An Authentic Dataset for Visual-Inertial Odometry*, 2018.[https://arxiv.org/abs/1807.09828](https://arxiv.org/abs/1807.09828)
5. Schönberger and Frahm, *Structure-from-Motion Revisited*, CVPR 2016.[https://openaccess.thecvf.com/content_cvpr_2016/html/Schonberger_Structure-From-Motion_Revisited_CVPR_2016_paper.html](https://openaccess.thecvf.com/content_cvpr_2016/html/Schonberger_Structure-From-Motion_Revisited_CVPR_2016_paper.html)
6. Pan et al., *Global Structure-from-Motion Revisited*, ECCV 2024.[https://arxiv.org/abs/2407.20219](https://arxiv.org/abs/2407.20219)
7. COLMAP 4 文档和版本记录。[https://colmap.github.io/changelog.html](https://colmap.github.io/changelog.html)
8. COLMAP pose-prior 重建。[https://colmap.github.io/faq.html](https://colmap.github.io/faq.html)
9. Schönberger et al., *Pixelwise View Selection for Unstructured Multi-View Stereo*, ECCV 2016.[https://www.microsoft.com/en-us/research/?p=610152](https://www.microsoft.com/en-us/research/?p=610152)
10. Lindenberger et al., *LightGlue: Local Feature Matching at Light Speed*, ICCV 2023.
    [https://github.com/cvg/LightGlue](https://github.com/cvg/LightGlue)

### 现代学习型 SLAM 和重建

11. Murai et al., *MASt3R-SLAM: Real-Time Dense SLAM with 3D Reconstruction Priors*, CVPR 2025.[https://openaccess.thecvf.com/content/CVPR2025/papers/Murai_MASt3R-SLAM_Real-Time_Dense_SLAM_with_3D_Reconstruction_Priors_CVPR_2025_paper.pdf](https://openaccess.thecvf.com/content/CVPR2025/papers/Murai_MASt3R-SLAM_Real-Time_Dense_SLAM_with_3D_Reconstruction_Priors_CVPR_2025_paper.pdf)
12. Wang et al., *VGGT: Visual Geometry Grounded Transformer*, CVPR 2025.[https://openaccess.thecvf.com/content/CVPR2025/html/Wang_VGGT_Visual_Geometry_Grounded_Transformer_CVPR_2025_paper.html](https://openaccess.thecvf.com/content/CVPR2025/html/Wang_VGGT_Visual_Geometry_Grounded_Transformer_CVPR_2025_paper.html)
13. Teed and Deng, *DROID-SLAM: Deep Visual SLAM for Monocular, Stereo, and RGB-D Cameras*, NeurIPS 2021.[https://proceedings.neurips.cc/paper/2021/hash/89fcd07f20b6785b92134bd6c1d0fa42-Abstract.html](https://proceedings.neurips.cc/paper/2021/hash/89fcd07f20b6785b92134bd6c1d0fa42-Abstract.html)
14. Wu et al., *VINGS-Mono: Visual-Inertial Gaussian Splatting Monocular SLAM in Large Scenes*, 2025.[https://github.com/Fudan-MAGIC-Lab/VINGS-Mono](https://github.com/Fudan-MAGIC-Lab/VINGS-Mono)
15. *Monocular visual SLAM, visual odometry, and structure from motion methods applied to 3D reconstruction: A comprehensive survey*, 2024.
    [https://pmc.ncbi.nlm.nih.gov/articles/PMC11415689/](https://pmc.ncbi.nlm.nih.gov/articles/PMC11415689/)

### RGB-D、LiDAR、TSDF 与房间建模

16. Labbé and Michaud, *RTAB-Map as an Open-Source Lidar and Visual SLAM Library for Large-Scale and Long-Term Online Operation*.[https://arxiv.org/abs/2403.06341](https://arxiv.org/abs/2403.06341)
17. Open3D TSDF Integration。[https://open3d.org/docs/release/tutorial/t_reconstruction_system/integration.html](https://open3d.org/docs/release/tutorial/t_reconstruction_system/integration.html)
18. Newcombe et al., *KinectFusion: Real-Time Dense Surface Mapping and Tracking*, ISMAR 2011.[https://www.microsoft.com/en-us/research/publication/kinectfusion-real-time-dense-surface-mapping-tracking/](https://www.microsoft.com/en-us/research/publication/kinectfusion-real-time-dense-surface-mapping-tracking/)
19. Apple ARKit `sceneDepth`。[https://developer.apple.com/documentation/arkit/arframe/scenedepth](https://developer.apple.com/documentation/arkit/arframe/scenedepth)
20. Apple ARKit `sceneReconstruction`。[https://developer.apple.com/documentation/arkit/arconfiguration/scenereconstruction](https://developer.apple.com/documentation/arkit/arconfiguration/scenereconstruction)
21. Apple, *3D Parametric Room Representation with RoomPlan*.[https://machinelearning.apple.com/research/roomplan](https://machinelearning.apple.com/research/roomplan)
22. Baruch et al., *ARKitScenes: A Diverse Real-World Dataset for 3D Indoor Scene Understanding Using Mobile RGB-D Data*.[https://arxiv.org/abs/2111.08897](https://arxiv.org/abs/2111.08897)
23. *RGB-D SLAM: A Review of Methods and Performance Trade-Offs for Different Requirements*, 2026.
    [https://pmc.ncbi.nlm.nih.gov/articles/PMC13258843/](https://pmc.ncbi.nlm.nih.gov/articles/PMC13258843/)

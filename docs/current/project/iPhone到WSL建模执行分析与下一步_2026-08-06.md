# iPhone 到 WSL 建模执行分析与下一步

日期：2026-08-06

## 结论

本轮已经验证两条此前没有闭环的链路：

1. iPhone 端可以生成 Schema 1.3.0 session，真实丢帧后的视频样本编号仍与 MOV
   解码顺序一致；真机 5 秒采集、停止和完整性检查通过。
2. RTX 4050 Laptop 6 GB + 16 GB 内存的 WSL Docker 可以从空数据库完成 COLMAP
   CUDA SIFT、全匹配、增量 mapper、去畸变、PatchMatch 和 fusion。因此笔记本可
   替代服务器完成受控基线建模，主要限制是处理速度、显存和并行任务规模。

首次 COLMAP 验收按 2026-08-06 的执行决定只使用官方数据集，结果已经通过。iPhone
session 当前只用于采集格式和导入检查，不进入 COLMAP 建模；真实 iPhone 房间重建、
ARKit 内参接入和 Sim(3) 米制对齐全部列为后续工作，等待再次明确启动。

## 本轮实际验证结果

### iPhone 与跨端 session

App 已升级到 0.4.0 / Session Schema 1.3.0，并新增：

- 视频 codec、容器、源像素格式、尺寸、方向、镜像、裁剪、缩放和稳像语义；
- ARKit 位姿字段前缀、`target_T_source`、行主序、右手系和米制语义；
- CoreMotion 单位、参考系、四元数顺序、请求采样率和“不插值”声明；
- 源码提交/构建标识；提交无法注入时明确写 `unknown`；
- `video_frame_id` 改为“成功写入 MOV 的零起始连续样本编号”，写入失败为 `-1`。

真机测试：

| 项目 | 结果 |
| --- | --- |
| 视频样本索引单元测试 | 通过 |
| Schema 1.3 元数据编码测试 | 通过 |
| 5 秒 ARKit + MOV + CSV + IMU 实采 smoke | 通过 |
| 新 session | `session_20260806_200910` |

该 session 上传 WSL 后，`witwin-inspect-session` 零错误、零警告通过：

| 指标 | 实测 |
| --- | ---: |
| 校验和 | 9/9 |
| ARFrame | 240 |
| MOV 成功样本 / 解码帧 | 238 / 238 |
| 正确标记的未写入帧 | 2 |
| IMU 行数 | 3509 |
| 七路 IMU 估算频率 | 约 100.019 Hz |
| 平均重力模长 | 1.000000 g |
| ARKit 轨迹长度 | 0.0287 m |

### WSL COLMAP 从空数据库验证

测试输入是官方 South Building 的 128 张原始图片，但没有使用数据包附带的
`database.db` 或 `sparse/`。新工作区为：

```text
/data/testdata/south-building-from-empty-v1
```

配置为 COLMAP 4.0.4、CUDA SIFT、exhaustive matcher、incremental mapper、单
OPENCV 相机、最大图像尺寸 800、PatchMatch 5 samples × 2 iterations。

| 阶段 | 退出码 | 耗时 |
| --- | ---: | ---: |
| CUDA SIFT | 0 | 20.60 s |
| CUDA exhaustive matcher | 0 | 27.24 s |
| mapper | 0 | 113.81 s |
| image undistorter | 0 | 30.11 s |
| PatchMatch stereo | 0 | 371.71 s |
| stereo fusion | 0 | 11.55 s |

最终结果：

- 注册图片 128/128；
- 稀疏点 33,272；
- 平均重投影误差 0.763 px；
- 融合点云 891,539 点，`fused.ply` 约 24.1 MB；
- 全部命令、日志、退出码、耗时、配置和结果保存在 `pipeline_state.json`。

这比既有服务器记录更强：既有记录验证的是从数据包数据库继续 mapper/稠密，本次已
证明笔记本环境能从空数据库跑完整基线。

## 尚未解决的问题与端侧分工

以下条目是后续 backlog，不属于本次官方数据集 COLMAP 验收范围。

### iPhone 端

1. 采集一段真正用于建模的 30–60 秒房间扫描；当前 5 秒样例只验证数据链路。
2. 在 UI 中增加扫描引导和质量提示：镜头遮挡/低照度、移动过快、tracking limited、
   起止静止段、覆盖墙角和回到起点形成回环。
3. 补齐机器可读的颜色空间、镜头/相机标识；确认 ARKit captured image 与编码 MOV
   之间没有未声明的色彩或几何变换。
4. 为正式构建注入 40 位 workspace commit；当前测试构建按约定记录为 `unknown`。
5. 记录采集期间的中断和传感器可用性；实际采样率、缺口和饱和统计可继续由 WSL
   从原始数据计算，避免手机端改写原始样本。
6. 验证较大 session 从 iPhone 导出到 Mac 的进度、可用空间和最终校验和。

### WSL 端

1. 在现有 `inspect_session` 和 `extract_frames` 后实现 `select_keyframes`：至少计算
   亮度/过曝、Laplacian 清晰度、SIFT/ALIKED 特征数、相邻 ARKit 平移/旋转、
   tracking state 和空间覆盖。
2. 实现 `prepare_colmap`，从 `frame_manifest.csv` 读取每帧内参和尺寸，明确完成
   ARKit 图像坐标到 COLMAP 相机模型的转换；当前公共数据集验证使用的是 COLMAP
   自动初始化焦距，不能代表 iPhone 内参已经正确接入。
3. 在正式 iPhone session 上先比较 SIFT + sequential/exhaustive，再按需要加入
   ALIKED/LightGlue；不要在基线失败前同时扩大算法变量。
4. 在真实 session 上分别验证 `mapper`、`global_mapper`、`pose_prior_mapper`，保存
   注册率、失败图像、点数和重投影误差。
5. 实现 ARKit/COLMAP 相机中心对应、RANSAC + Sim(3) 和独立米制检查。
6. 在稀疏和尺度验收后运行稠密、点云分析、平面/Manhattan 约束、网格化及 WiTwin
   坐标导出。

### 已解除与仍存在的边界

| 能力 | 当前状态 |
| --- | --- |
| 笔记本 COLMAP/CUDA 可用 | 已验证 |
| 从空数据库到融合点云 | 已验证（公共数据集） |
| iPhone v1.3 真机采集、传输、导入 | 已验证 |
| 丢帧后的 MOV 样本映射 | 已验证（本次实际出现 2 个未写入帧） |
| iPhone 视频可追溯抽帧 | 工具已实现；不纳入本次建模验收 |
| iPhone 房间稀疏模型 | 按当前决定暂不执行 |
| ARKit 内参写入 COLMAP | 未实现 |
| 质量/视差关键帧选择 | 未实现 |
| ARKit/COLMAP Sim(3) 米制对齐 | 未实现 |
| iPhone 稠密点云和 WiTwin 网格 | 未验证/未实现 |

## 后续恢复 iPhone 建模时的执行顺序

以下计划暂缓，不在本轮继续执行。

### P0：取得合格房间 session

使用当前 0.4.0 App 即可先采一段 30–60 秒数据，不必等待全部 UI 功能：

1. 擦净并确认后置镜头无遮挡，选择光照稳定、纹理丰富的房间；
2. 开始后静止约 2 秒；
3. 缓慢平移并绕房间一圈，覆盖近、中、远景和墙角，避免只在原地旋转；
4. 让相邻画面有大量重叠，同时形成至少一次回环；
5. 避免大面积白墙占满画面、反光面、快速运动和严重模糊；
6. 结束前回到起点附近并静止约 2 秒；
7. 同时记录至少一处人工测距或已知长度，供最终米制独立检查。

### P0：导入、质量筛选和稀疏基线

1. 导出到 Mac，并按 `.partial` → 校验 → 正式目录的方式上传 WSL；
2. 运行 `witwin-inspect-session`，失败时不进入 COLMAP；
3. 抽帧并实现/运行质量关键帧选择，保存所有保留和拒绝原因；
4. 写入 iPhone 相机内参，从空数据库运行 SIFT + sequential matcher + mapper；
5. 首轮目标：注册率至少 80%、模型可被 PyCOLMAP 读取、平均重投影误差低于
   2 px。阈值在首个合格 session 后再冻结，不能通过静默删帧达标。

### P1：米制与稠密

1. 完成 Sim(3)，报告尺度、内点率和残差，并用人工测距独立验证；
2. 以 800–1200 最大图像尺寸先跑受控 PatchMatch；
3. Open3D 验证点云非空，随后分析平面、连通分量、孔洞和非流形边；
4. 通过小规模参数对照后再提高分辨率，RTX 4050 6 GB 上避免并行多个 GPU 重建。

## 当前命令入口

```bash
/opt/witwin-tools/venvs/geometry/bin/witwin-run-colmap \
  --image-path /data/testdata/south-building-source/south-building/images \
  --workspace /data/testdata/south-building-from-empty-v1 \
  --stage all \
  --colmap /opt/witwin-tools/colmap-4.0.4/bin/colmap \
  --matcher exhaustive \
  --mapper mapper \
  --feature-type SIFT \
  --camera-model OPENCV \
  --single-camera \
  --max-image-size 800 \
  --patchmatch-samples 5 \
  --patchmatch-iterations 2
```

首次验收的完整记录见
[COLMAP 官方数据集首次验证报告](COLMAP官方数据集首次验证报告_2026-08-06.md)。

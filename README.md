# WiTwin 多设备科研工作区

本仓库统一管理带 LiDAR 的 iPhone 多模态采集、Linux CSI 采集、服务器三维重建及
WiTwin GPU 仿真。`main` 保存经过基本验证的集成状态，各设备职责和当前迁移任务
由 `docs/current/` 统一说明。

## 目录

```text
apps/ios-recorder/              带 LiDAR iPhone 的 Swift/ARKit 采集应用
capture/csi-linux/              PicoScenes、网卡和 CSI/UDP 采集
pipelines/reconstruction/       服务器端 RGB/LiDAR/VIO 三维重建
pipelines/witwin/               服务器端 WiTwin 仿真、实验和可复现产物
schemas/session-format/         三端共享的数据、时间、坐标和 UDP 协议
datasets/                       本地原始/处理中数据，默认不进入 Git
src/                            固定版本的 WiTwin Core/Channel 子模块
docs/                           全部当前文档、历史报告和参考资料
workspace/host_snapshot/        2026-07-15 原始 Windows 快照（只读边界）
validate_witwin.py              WiTwin 环境完整验证入口，服务器迁移后需重新运行
```

`src/`、`validate_witwin.py` 和 `workspace/host_snapshot/` 保留原路径，以免破坏
editable Python 安装、历史验证命令和 Windows 快照边界。

## 分支

| 分支 | 设备与职责 |
|---|---|
| `main` | 已验证集成版本、公共协议 |
| `work/wsl-witwin` | 当前保留的分支名；目标环境改为服务器，负责重建、WiTwin 和离线分析 |
| `work/csi-linux` | Linux 网卡、PicoScenes、CSI/UDP、数据整理 |
| `work/ios-recorder` | Mac/Xcode、iPhone、ARKit/CoreMotion |

具体同步流程见 [`docs/reference/BRANCH_WORKFLOW.md`](docs/reference/BRANCH_WORKFLOW.md)。

## 文档

[`docs/`](docs/README.md) 是唯一权威文档入口：

- [`docs/current/`](docs/current/README.md)：主计划、总体进度和各分支最新状态；
- [`docs/history/`](docs/history/README.md)：旧计划、阶段报告、实验报告和环境交接；
- [`docs/reference/`](docs/reference/README.md)：Git、分支、WiTwin、网络配置和技术调研。
- [`docs/papers/`](docs/papers/README.md)：论文草稿、投稿材料和论文专用图源。

`pipelines/` 中只保留实验脚本、机器结果、图像及指向文档中心的简短 README。
`workspace/project-docs/` 是兼容旧路径的提示入口，不再维护科研文档副本。

## 当前迁移

当前改用带后置 LiDAR 的 iPhone，并将 WiTwin、重建和离线分析迁往服务器。具体
设备、环境与验收状态见
[`LiDAR iPhone 与 WiTwin 服务器迁移计划`](docs/current/project/LiDAR与服务器迁移计划.md)。
既有 WSL 验证仍是可追溯历史证据，不代表服务器迁移已经完成。

## 数据原则

连续视频、原始 CSI、IMU、稠密点云和网格不应直接提交到普通 Git。它们应放在
`datasets/`、NAS 或对象存储；Git 只保存协议、配置、采集清单、SHA-256、处理
脚本、小型测试样本和报告。

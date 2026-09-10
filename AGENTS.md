# WiTwin Mac 工作区指令

## 当前工作区

- 本文件只描述当前 Mac 上的 Git 工作树，不以 WSL、Linux 采集机、服务器或容器中的目录布局为默认依据。
- 仓库根目录是包含本文件的目录；所有路径优先写成相对仓库根目录的路径，不硬编码 `/opt/witwin`、`/root/...` 或 Windows 盘符。
- 当前 Mac 的主要职责是 `work/ios-recorder` 分支上的 iPhone 采集应用、Xcode 工程、真机验证，以及三端共享协议中与发送端有关的部分。
- 默认使用中文与用户沟通。

## 开始工作前

1. 先确认仓库根目录、当前分支和工作树状态：`pwd`、`git branch --show-current`、`git status --short --branch`。
2. 阅读 `docs/current/README.md`、`docs/current/branches/work-ios-recorder.md`，以及本次任务直接涉及目录的 `README.md`。
3. 涉及跨端结论时再阅读 `docs/current/项目当前进展与下一步方向.md`；不要为了 Mac/iOS 单端任务默认加载其他设备的全部历史资料。
4. 先检查现有未提交修改。它们可能属于用户，不得覆盖、回退或顺手整理无关改动。

## Mac 工作树架构

```text
.
├── apps/ios-recorder/          Mac 上的主开发区：Swift、ARKit、CoreMotion、Xcode
├── schemas/session-format/     三端共享的 session、时间、坐标和 UDP 协议
├── datasets/                   本机真机采集与交换数据，默认被 Git 忽略
├── docs/                       项目权威文档入口
│   ├── current/                当前计划、总体进展和各分支最新状态
│   ├── history/                已完成阶段、历史实验与交接记录
│   ├── reference/              长期有效的指南和技术调研
│   ├── papers/                 论文草稿、投稿材料和论文专用图源
│   └── server/                 旧服务器文档入口导航
├── capture/csi-linux/          Linux CSI 采集端共享代码；不是本机默认执行入口
├── pipelines/reconstruction/  重建流水线共享入口；重任务通常不在本机默认执行
├── pipelines/witwin/           WiTwin 实验和产物；GPU 环境不属于本机默认环境
├── src/                        WiTwin Core/Channel Git 子模块
├── workspace/host_snapshot/   2026-07-15 历史快照，只读边界
└── workspace/project-docs/    旧文档入口提示，不再维护当前文档
```

### iOS 工程内的职责

- `apps/ios-recorder/WiTwinRecorder/`：App 源码。
- `apps/ios-recorder/WiTwinRecorderTests/`：测试源码。
- `apps/ios-recorder/WiTwinRecorder.xcodeproj/`：可直接由 Xcode 打开的工程。
- `apps/ios-recorder/project.yml`：XcodeGen 工程定义；修改 target、文件或构建设置时保持它与生成工程一致。
- `apps/ios-recorder/scripts/`：导出 session 的离线检查脚本。
- `apps/ios-recorder/DerivedData*`、`*.xcworkspace/xcuserdata`：本机构建或用户状态，不提交 Git。

## 本机工具与执行规则

- iOS 构建使用当前激活的 Xcode：先用 `xcode-select -p` 和 `xcodebuild -version` 核对，不假定其他机器的 SDK 或 Xcode 版本。
- 打开工程使用 `apps/ios-recorder/WiTwinRecorder.xcodeproj`。
- 修改 `project.yml` 后，如本机有 XcodeGen，运行 `xcodegen generate`，并检查生成的 `project.pbxproj` 是否只有预期变化。
- 当前仓库根目录没有固定 Python 虚拟环境。不要引用 `/opt/witwin/venv`，也不要把依赖安装到系统 `/usr/bin/python3`；确需 Python 依赖时，在仓库内创建被忽略的本地虚拟环境并记录任务所需命令。
- Linux CUDA、OptiX、RayD、DrJit、PicoScenes 和服务器路径不是本机默认能力。未经用户明确要求，不在 Mac 上尝试复现或修改这些环境。

## 构建与验证

从仓库根目录执行无签名模拟器构建：

```bash
xcodebuild \
  -project apps/ios-recorder/WiTwinRecorder.xcodeproj \
  -scheme WiTwinRecorder \
  -configuration Debug \
  -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath apps/ios-recorder/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  ARCHS=arm64 \
  ONLY_ACTIVE_ARCH=YES \
  build
```

- 涉及测试 target、协议编解码或 session 逻辑时，至少将末尾动作改为 `build-for-testing` 再验证。
- 涉及真机能力、相机、ARKit、人脸跟踪、CoreMotion、UDP 或签名时，模拟器构建不能代替真机验证；清楚区分“编译通过”和“真机通过”。
- 真机操作前先解析实际设备，避免把历史设备 ID、签名 Team 或目标系统版本写死在脚本和文档中。
- 离线复核使用 `apps/ios-recorder/scripts/check_p1_session.sh <session目录>`；不得修改原始 session 来迎合检查器。
- 根据改动风险选择最小而充分的验证。报告实际执行的命令和结果，未执行的验证必须明确说明。

## 数据与源码边界

- `datasets/` 保存本机原始或处理中数据，目录内容默认不进入普通 Git。视频、CSI、IMU、点云、网格和 DerivedData 不得误提交。
- Git 只保存协议、配置、采集清单、校验和、处理脚本、受控小样例和报告。提交前检查 `git status --ignored` 与暂存区。
- `src/witwin-core` 和 `src/witwin-channel` 是固定提交的 Git 子模块。不要把它们当普通目录批量改写，也不要在没有兼容性评估时更新子模块指针。
- `workspace/host_snapshot/` 是历史快照。除非用户明确要求，不批量移动、重命名、格式化或删除其中内容。
- `capture/csi-linux/`、`pipelines/` 和 `docs/reference/server/` 可以因跨端协议或交接任务被修改，但不能据此假定相应 Linux/服务器运行环境存在于这台 Mac。

## 公共协议与分支边界

- `work/ios-recorder`：Mac/Xcode、iPhone、ARKit/CoreMotion、视频和 UDP 发送。
- `main`：已验证集成状态和公共协议。
- `work/csi-linux` 与 `work/wsl-witwin` 属于其他设备职责；本机默认不切换过去执行其环境任务。
- 涉及 session 字段、UDP 线格式、时间映射、坐标系或文件角色时，优先修改 `schemas/session-format/`，同步提升适当协议版本，并检查 App 的编码、校验与测试。
- 不在 App、CSI 端和重建端分别维护不兼容的协议副本。
- 未经用户明确要求，不切换分支、不 rebase、不推送、不提交，也不更新子模块远端状态。

## 文档管理

- `docs/` 是当前仓库科研与工程文档的权威入口。
- `docs/current/` 保存仍在维护的状态；分支状态更新到 `docs/current/branches/work-ios-recorder.md`。
- `docs/history/` 默认只读，用于带日期的阶段报告、旧计划和已完成实验。
- `docs/reference/` 保存长期有效指南，服务器指南位于 `docs/reference/server/`；`docs/server/` 只保留旧入口导航。
- `docs/papers/` 保存论文草稿和论文专用图源；论文中的结果假设不作为当前状态或实验完成证据。
- 代码目录只保留简短 `README.md` 说明职责、运行入口和权威文档链接；不要在 `apps/`、`capture/`、`pipelines/` 或 `workspace/` 新建独立进度报告。
- 阶段工作完成时，先更新 iOS 分支当前状态；需要详细留档时再写入对应历史目录。只有影响跨分支结论时，才同步更新总体进展文档。
- 新文档应链接已有证据，不复制维护另一份“当前状态”。

## 安全与故障处理

- 诊断优先使用只读检查。签名、证书、钥匙串、设备信任和系统网络设置可能影响整台 Mac，未经用户确认不要改变。
- 不删除或覆盖真机采集数据、DerivedData 之外的用户文件、历史快照或未提交修改。
- 网络、UDP 或跨端联调失败时，先分别记录 Mac/iPhone 端证据和远端可达性；不要把 Linux/服务器配置问题直接归因于本机工程。
- 文档中的历史版本号、设备状态和实验结论可能滞后；报告当前事实前应以代码、实际命令输出和最新分支状态交叉核对。

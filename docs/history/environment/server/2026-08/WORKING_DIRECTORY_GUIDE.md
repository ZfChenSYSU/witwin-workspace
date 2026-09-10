# 工作目录使用规范

## 两类目录

### Git 工程目录

```text
/root/nfs/chenzhf/witwin/repository
```

这是 `work/wsl-witwin` 分支的独立 Git worktree，也是日常工作的默认目录。代码、
配置、Schema、工程说明、实验方法、结果摘要和可复现脚本都必须在这里创建或修改。

### 本机运行时目录

```text
/root/nfs/chenzhf/witwin
```

该目录只保存不适合进入 Git 的本机内容：Conda 环境、编译产物、缓存、日志、原始
数据、稠密深度图、点云和网格。不要把它作为编辑工程代码或文档的默认目录。

## 按任务选择目录

| 工作内容                    | 应进入的目录                                                     |
| --------------------------- | ---------------------------------------------------------------- |
| 日常 Git 操作、查看整体工程 | `/root/nfs/chenzhf/witwin/repository`                          |
| SLAM/SfM/MVS 流水线代码     | `/root/nfs/chenzhf/witwin/repository/pipelines/reconstruction` |
| WiTwin 仿真与实验代码       | `/root/nfs/chenzhf/witwin/repository/pipelines/witwin`         |
| 会话格式、时间和坐标协议    | `/root/nfs/chenzhf/witwin/repository/schemas/session-format`   |
| 服务器环境与测试文档        | `/root/nfs/chenzhf/witwin/repository/docs/current/server`      |
| 小型受控测试数据            | `/root/nfs/chenzhf/witwin/testdata`                            |
| Conda/Python 环境           | `/root/nfs/chenzhf/witwin/env`                                 |
| COLMAP 源码、构建与安装     | `/root/nfs/chenzhf/witwin/tools`                               |
| 安装和重建的完整运行日志    | `/root/nfs/chenzhf/witwin/logs`                                |

## 推荐工作方式

开始代码或文档工作：

```bash
cd /root/nfs/chenzhf/witwin/repository
git status --short --branch
```

运行 COLMAP 时仍从 Git 工程目录组织命令和配置，但把大体积输出指向运行时目录：

```bash
WITWIN_ROOT=/root/nfs/chenzhf/witwin
WITWIN_REPO=$WITWIN_ROOT/repository
```

建议使用以下映射：

```text
$WITWIN_REPO/pipelines/reconstruction/   可提交的脚本与配置
$WITWIN_ROOT/testdata/                   不提交的输入和重建产物
$WITWIN_ROOT/logs/                       不提交的完整执行日志
$WITWIN_REPO/docs/current/server/        可提交的方法、摘要和结论
```

完整日志和大文件留在运行时目录；将命令、版本、关键指标和结论整理到 Git 文档中。
不要把视频、深度图、点云、网格、Conda 环境或构建树复制进 Git。

`/root/nfs/chenzhf/witwin-workspace` 是保留规划分支和历史未提交记录的另一个
worktree。后续 WSL/GPU、服务器重建和离线分析工作统一在 `repository` 进行，避免
同一文档在两个分支同时编辑。

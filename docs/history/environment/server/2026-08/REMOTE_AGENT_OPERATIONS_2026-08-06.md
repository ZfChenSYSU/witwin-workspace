# 服务器工作区与远程 Agent 操作说明

日期：2026-08-06

本文供远程登录服务器的开发者和 Agent 使用。目标是避免在非 Git 目录编辑工程文件，
同时避免把环境、数据和大型重建产物误提交到 Git。

## 1. 远程入口

服务器连接信息来自当前部署计划：

```bash
ssh -p 8048 root@192.168.3.2
```

本文不保存密码、私钥或其他凭据。登录后首先进入 Git worktree：

```bash
cd /root/nfs/chenzhf/witwin/repository
git status --short --branch
```

当前服务器开发分支是 `work/wsl-witwin`，远端跟踪分支是
`origin/work/wsl-witwin`。开始工作前先阅读：

1. 仓库根目录 `AGENTS.md`；
2. `docs/current/server/README.md`；
3. `docs/current/server/WORKING_DIRECTORY_GUIDE.md`；
4. `docs/current/server/COLMAP_CAPABILITY_BOUNDARY_2026-08-06.md`；
5. `docs/current/server/IPHONE_SESSION_IMPORT_REQUIREMENTS_2026-08-06.md`。

如果 `git status` 非干净，不要执行 `reset`、`clean`、强制 checkout 或覆盖文件。
先判断改动归属，并保留已有改动。没有明确授权时不要提交或推送。

## 2. 工作区边界

### Git 工程根目录

```text
/root/nfs/chenzhf/witwin/repository
```

这里保存可复现的代码、配置、Schema、工程文档、实验方法和结果摘要。日常编辑应以
此目录作为 VS Code/Codex 打开的工作文件夹。

### 本机运行时根目录

```text
/root/nfs/chenzhf/witwin
```

这里保存 Conda 环境、COLMAP 构建、缓存、日志、测试数据、深度图、点云和网格。
这些内容通常不进入 Git。

### 保留的规划 worktree

```text
/root/nfs/chenzhf/witwin-workspace
```

该目录保留 `agent/no-lidar-slam-server-plan` 分支及历史未提交安装记录。不要删除、
重置或将其与当前 worktree 混合。新的 WSL/GPU、重建和服务器文档统一写入
`/root/nfs/chenzhf/witwin/repository`。

## 3. 运行环境入口

```bash
WITWIN_ROOT=/root/nfs/chenzhf/witwin
WITWIN_REPO=$WITWIN_ROOT/repository
export PATH="$WITWIN_ROOT/env/bin:$WITWIN_ROOT/tools/colmap-4.0.4/bin:$PATH"
export LD_LIBRARY_PATH="$WITWIN_ROOT/env/lib:$WITWIN_ROOT/tools/colmap-4.0.4/lib:$WITWIN_ROOT/tools/colmap-4.0.4/thirdparty"
```

COLMAP 是 shared build；缺少上述 `LD_LIBRARY_PATH` 时会出现
`libcolmap_controllers.so` 等动态库无法加载的问题。不要通过复制库到系统目录解决。

常用只读探针：

```bash
df -BG /root/nfs
nvidia-smi
git status --short --branch
colmap -h
$WITWIN_ROOT/env/bin/python --version
$WITWIN_ROOT/env/bin/python -m pip check
```

## 4. 数据与输出位置

小型、受控测试可使用：

```text
/root/nfs/chenzhf/witwin/testdata/sessions/<session_id>/
```

正式 iPhone 视频和完整稠密工作区可能占用数 GB 到数十 GB，应使用用户指定的更大
数据盘。当前运行盘剩余空间约 14 GB；低于 8 GB 必须停止产生新数据，不得通过删除
其他项目、共享缓存或系统文件释放空间。

完整运行日志放在：

```text
/root/nfs/chenzhf/witwin/logs
```

可提交的运行命令、版本、关键指标和结论应整理到：

```text
/root/nfs/chenzhf/witwin/repository/docs/current/server
```

## 5. 安全操作规则

- 不修改 `/usr`、`/usr/local`、系统 CUDA、系统 Python 或其他项目环境。
- 不删除或清理现有源码、环境、缓存、日志、测试数据和重建产物。
- 不使用 `git reset --hard`、`git clean` 或强制覆盖已有改动。
- 不把视频、数据库、深度图、点云、网格、Conda 环境或构建树加入 Git。
- 运行长任务时记录命令、日志路径、退出状态和磁盘余量。
- 失败时保留现场，在文档中记录证据和可恢复方案。

## 6. 每次任务的推荐顺序

1. 登录并进入 Git 工程根目录。
2. 阅读 `AGENTS.md` 和本目录交接文档。
3. 检查分支、未提交改动、GPU、环境和磁盘空间。
4. 在 `pipelines/`、`schemas/` 或 `docs/` 中编辑可提交内容。
5. 将运行输入、输出和完整日志指向运行时根目录。
6. 运行小型探针后再扩大任务规模。
7. 更新 Git 文档中的命令、版本、结果和能力边界。
8. 提交或推送前再次检查，确保没有大文件、凭据或运行时产物进入 Git。

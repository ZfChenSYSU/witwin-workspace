# 三设备分支与同步流程

## 分支职责

```text
main
├── work/wsl-witwin
├── work/csi-linux
└── work/ios-recorder
```

- `main`：已验证集成版本和三端共享协议；
- `work/wsl-witwin`：WSL/GPU、重建、WiTwin 和离线分析；
- `work/csi-linux`：Linux 网卡、PicoScenes、CSI/UDP 和数据整理；
- `work/ios-recorder`：Mac/Xcode、iPhone、ARKit/CoreMotion 和 UDP 发送。

三个工作分支不是永久互不相交的产品版本。每项稳定修改最终合入 `main`，其他
设备再从 `main` 同步。

## 每台设备首次设置

WSL：

```bash
git fetch origin
git switch work/wsl-witwin
git branch --set-upstream-to=origin/work/wsl-witwin
```

CSI Linux：

```bash
git fetch origin
git switch work/csi-linux
git branch --set-upstream-to=origin/work/csi-linux
```

Mac/iOS：

```bash
git fetch origin
git switch work/ios-recorder
git branch --set-upstream-to=origin/work/ios-recorder
```

## 日常工作

开始前：

```bash
git status
git fetch origin
git rebase origin/main
```

完成一个逻辑单元后：

```bash
git add <明确文件>
git diff --cached
git commit -m "说明本次修改"
git push
```

稳定并验证后，通过 GitHub Pull Request 合入 `main`。不要从三台设备直接并发
推送 `main`，也不要使用普通 `git push --force`。

如果工作分支 rebase 后需要更新远端，应先确认该分支没有他人未同步提交，再用：

```bash
git push --force-with-lease
```

不希望改写工作分支历史时，可以用 `git merge origin/main` 代替 rebase。

## 公共协议修改

涉及 session 字段、UDP 线格式、时间映射、坐标系或文件角色时：

1. 修改 `schemas/session-format/`；
2. 提升适当协议版本；
3. 先通过 Pull Request 合入 `main`；
4. 三个工作分支同步 `main`；
5. 分别实现发送、采集和解析；
6. 用同一个小型 session 做端到端兼容性验证。

不要在三个分支分别复制和修改协议文档。

## 大文件同步

视频、原始 CSI、IMU、点云和网格不通过普通 Git 分支同步。使用 NAS、移动硬盘或
对象存储，并在 Git 中提交：

- session 元数据；
- 文件清单、字节数和 SHA-256；
- 采集与处理配置；
- 软件、固件和 Git 版本；
- 小型脱敏测试样本。

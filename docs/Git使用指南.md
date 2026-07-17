# Git 使用指南（WiTwin 工作区）

本文适用于容器内的 WiTwin 工作区：

```text
/opt/witwin
```

远程仓库：<https://github.com/ZfChenSYSU/witwin-workspace>

默认分支是 `main`。下面的命令除特别说明外，都应在 `/opt/witwin` 中运行。

## 1. 开始工作

进入工作区并检查状态：

```bash
cd /opt/witwin
git status
```

建议每次修改前先同步远程更新：

```bash
git pull --ff-only
```

`--ff-only` 可以避免 Git 在不知情的情况下自动生成合并提交。如果本地和远程各自有新提交，命令会停止并要求人工处理。

## 2. 用 Git 做版本管理

Git 版本管理的核心是：把项目在某个时间点的可靠状态保存为一次“提交”（commit），形成可查询、可比较、可恢复的历史。每次提交都有唯一哈希，例如当前仓库首次提交的短哈希是 `f117384`。

一个实用的版本管理循环如下：

```text
同步远程 → 修改文件 → 检查差异 → 验证结果 → 创建提交 → 推送备份
```

### 2.1 建立版本快照

完成一项逻辑上独立、能够说明清楚的修改后，创建一次提交：

```bash
git status
git diff
git add <本次修改的文件>
git diff --cached
git commit -m "说明这个版本完成了什么"
```

一次提交应尽量只处理一个主题。例如“修复信道模型参数检查”和“重写实验说明”适合分成两个提交。这样以后可以准确定位问题，也可以只撤销其中一项改动。

不要等到修改了几十个互不相关的文件后才提交，也不要提交无法运行的中间状态。对 WiTwin 代码的重要修改，建议提交前执行：

```bash
export DRJIT_LIBOPTIX_PATH=/usr/lib/x86_64-linux-gnu/libnvoptix.so.1
/opt/witwin/venv/bin/python /opt/witwin/validate_witwin.py
```

### 2.2 查看和比较历史版本

查看简洁版本历史：

```bash
git log --oneline --decorate --graph --all
```

查看某次提交的内容：

```bash
git show <提交哈希>
```

比较两个版本：

```bash
git diff <旧提交哈希> <新提交哈希>
```

只比较某个文件：

```bash
git diff <旧提交哈希> <新提交哈希> -- <文件路径>
```

查看某个文件的版本历史：

```bash
git log --oneline --follow -- <文件路径>
```

### 2.3 用分支隔离不同版本的开发

`main` 应保存相对稳定、已经验证的版本。实验性功能或较大改动使用独立分支：

```bash
git switch main
git pull --ff-only
git switch -c experiment/reflection-path
```

在实验分支中可以多次提交，不影响 `main`。验证完成后再通过合并或 GitHub Pull Request 纳入主分支。尚未验证的 `max_bounces > 0` 反射路径尤其适合放在独立分支中，避免被误认为主分支已经支持。

### 2.4 用标签标记里程碑版本

分支会继续移动；标签（tag）用于给某个确定提交取一个永久版本名。完成阶段性验证后，可以创建带说明的标签：

```bash
git tag -a v0.1.0 -m "WiTwin baseline with validated LOS, CIR and CFR"
git push origin v0.1.0
```

查看标签：

```bash
git tag --list
git show v0.1.0
```

推荐使用语义化版本号：

- `v0.1.0`：增加一组可用功能或形成新的阶段基线。
- `v0.1.1`：修复问题，不改变主要使用方式。
- `v1.0.0`：形成明确、稳定并经过完整验证的正式版本。

不要给尚未验证或经常变化的提交随意创建正式标签。标签推送到远程后不应反复移动或覆盖。

### 2.5 恢复旧版本

只查看旧版本而不改变分支：

```bash
git show <提交哈希>:<文件路径>
```

把某个文件恢复成旧版本，但保留为待提交修改：

```bash
git restore --source=<提交哈希> -- <文件路径>
git diff
```

如果某个错误版本已经推送，推荐使用 `git revert` 创建一条可审计的反向提交：

```bash
git revert <错误提交哈希>
git push
```

不要通过删除历史或强制推送来“回到旧版本”。共享仓库优先保留完整历史，使其他人能够看到发生了什么以及如何修复。

### 2.6 推荐的 WiTwin 版本管理方式

建议采用以下规则：

1. `main` 只保存已经完成基本验证的工作区状态。
2. 新功能、实验和兼容性研究使用独立分支。
3. 一项独立改动对应一个或少量主题明确的提交。
4. 代码提交前运行相关测试；影响完整环境时运行 `validate_witwin.py`。
5. 推送前用 `git diff --cached` 检查是否误含凭据、日志、驱动或宿主快照。
6. 阶段性可复现版本使用带说明的标签，例如 `v0.1.0`。
7. 在实验记录中同时写下 Git 提交哈希，使结果能够对应到准确代码版本。

记录实验版本时可以使用：

```bash
git rev-parse HEAD
git submodule status
```

前一条记录工作区版本，后一条记录 WiTwin Core 和 Channel 的固定版本。两者与环境依赖版本共同构成可复现的实验基线。

## 3. 查看修改

查看哪些文件发生了变化：

```bash
git status --short
```

查看尚未暂存的具体内容：

```bash
git diff
```

查看已经暂存、准备提交的内容：

```bash
git diff --cached
```

查看最近的提交记录：

```bash
git log --oneline --decorate -10
```

## 4. 提交修改

推荐只添加本次确实需要提交的文件，不要习惯性使用 `git add .`：

```bash
git add docs/Git使用指南.md
git diff --cached
git commit -m "Add Git usage guide"
```

提交信息应简短说明本次改动，例如：

```text
Update WiTwin validation instructions
Fix deterministic channel example
Add experiment notes
```

提交只保存在本地。要同步到 GitHub，还需要推送：

```bash
git push
```

完整的日常流程通常是：

```bash
git status
git pull --ff-only
git add <文件路径>
git diff --cached
git commit -m "说明本次改动"
git push
```

## 5. 当前仓库不会上传的内容

`.gitignore` 已排除以下本地内容：

- `venv/`：约 7 GB 的 Python 虚拟环境，可重新创建，不应上传。
- `logs/`：验证过程产生的日志。
- `workspace/host_snapshot/`：Windows 文件快照、驱动文件和备份。
- `workspace/project-docs/`：指向宿主快照的本地符号链接入口。
- `workspace/support/`：OptiX 处理材料等本地支持文件。
- Python 缓存、编辑器配置和常见系统元数据。

检查某个文件为什么被忽略：

```bash
git check-ignore -v <文件路径>
```

不要用 `git add -f` 强制上传虚拟环境、驱动库、凭据、宿主备份或敏感科研资料。

## 6. WiTwin 源码子模块

以下两个目录是独立 Git 仓库，并以子模块形式固定到已验证版本：

```text
src/witwin-core
src/witwin-channel
```

第一次克隆本仓库时，应同时初始化子模块：

```bash
git clone --recurse-submodules https://github.com/ZfChenSYSU/witwin-workspace.git
```

如果已经完成普通克隆，则运行：

```bash
git submodule update --init --recursive
```

查看当前固定的子模块版本：

```bash
git submodule status
```

不要随意更新这两个子模块。当前验证组合依赖特定版本，尤其不要在没有兼容性评估和回归验证的情况下升级 WiTwin Channel、RayD 或 DrJit。

如果确实修改了子模块中的源码，应分别进入对应目录提交，然后回到根仓库提交新的子模块指针：

```bash
cd /opt/witwin/src/witwin-core
git status
# 在子模块仓库中提交并推送源码修改

cd /opt/witwin
git add src/witwin-core
git commit -m "Update witwin-core submodule"
git push
```

只有在拥有上游仓库写权限、明确知道目标分支，并完成验证后才应这样操作。

## 7. 使用分支开发

较大的修改建议放在单独分支中：

```bash
git switch -c feature/简短名称
```

完成并提交后首次推送：

```bash
git push -u origin feature/简短名称
```

切回主分支：

```bash
git switch main
git pull --ff-only
```

查看本地和远程分支：

```bash
git branch -vv
git branch --remotes
```

## 8. 安全撤销操作

丢弃某个文件尚未暂存的修改：

```bash
git restore <文件路径>
```

取消暂存，但保留文件修改：

```bash
git restore --staged <文件路径>
```

修改最近一次尚未推送的提交信息：

```bash
git commit --amend
```

为已经推送的错误提交创建反向提交：

```bash
git revert <提交哈希>
git push
```

操作前务必先运行 `git status` 和 `git diff`。不要随意使用以下破坏性命令：

```text
git reset --hard
git clean -fd
git push --force
```

它们可能永久删除未提交内容或覆盖远程历史。确需使用时，应先确认备份、影响范围和协作者状态。

## 9. 处理合并冲突

当 `git pull --ff-only` 提示本地与远程发生分叉时，先查看状态和提交关系：

```bash
git status
git log --oneline --graph --decorate --all -20
```

不要立刻强制推送。常见做法是先保存当前工作，然后选择合并或变基：

```bash
git pull --rebase
```

发生冲突后，Git 会在文件中标出冲突区域。人工编辑并确认内容后：

```bash
git add <已解决的文件>
git rebase --continue
```

如果不想继续本次变基：

```bash
git rebase --abort
```

不确定如何处理时，应保留现场并请求协助，不要删除 `.git` 或强制覆盖分支。

## 10. GitHub 登录与代理问题

GitHub 不再接受账户密码用于 HTTPS Git 推送。应通过 VS Code 的 GitHub 登录、GitHub CLI、个人访问令牌或 SSH 密钥进行认证。不要把密码、令牌、Cookie 或私钥发到聊天中，也不要提交进仓库。

查看远程地址：

```bash
git remote -v
```

当前远程地址应为：

```text
https://github.com/ZfChenSYSU/witwin-workspace.git
```

如果看到 `Invalid username or token`，应先暂停推送并重新完成 GitHub 登录。

如果看到无法连接 `127.0.0.1:7890`，说明 Git 或宿主端凭据助手仍在使用本地代理。只读检查容器内 Git 代理：

```bash
git config --show-origin --get-regexp '^(http|https)\.proxy$'
```

确认代理已经失效并获得授权后，才可清除容器内全局 Git 代理：

```bash
git config --global --unset-all http.proxy
git config --global --unset-all https.proxy
```

VS Code Dev Container 的凭据助手可能调用 Windows 宿主端配置。如果容器内没有代理但仍报同样错误，需要在 Windows PowerShell 中检查：

```powershell
git config --global --get-regexp "proxy"
```

修改 Windows、WSL 或 Docker Desktop 网络和代理配置前，应先确认故障证据及影响范围。

## 11. 克隆后恢复开发环境

Git 仓库只保存源码、说明和版本引用，不包含 Python 虚拟环境。克隆后需要按项目说明重新创建或恢复环境。

当前容器内的 WiTwin Python 环境固定为：

```text
/opt/witwin/venv
```

运行验证：

```bash
export DRJIT_LIBOPTIX_PATH=/usr/lib/x86_64-linux-gnu/libnvoptix.so.1
/opt/witwin/venv/bin/python /opt/witwin/validate_witwin.py
```

当前已验证 LOS、确定性信道、CIR 和 CFR。`max_bounces > 0` 的反射路径尚未通过当前上游组合验证，不能将 LOS 验证视为完整反射能力已经通过。

## 12. 常用检查命令速查

```bash
# 当前状态
git status --short --branch

# 文件差异
git diff
git diff --cached

# 最近提交
git log --oneline --decorate -10

# 远程地址
git remote -v

# 拉取（仅允许快进）
git pull --ff-only

# 推送当前分支
git push

# 子模块状态
git submodule status

# 检查忽略规则
git check-ignore -v <文件路径>
```

最重要的习惯是：修改前先同步，提交前检查差异，推送前确认分支，遇到认证、代理或冲突问题时先停止并保留现场。

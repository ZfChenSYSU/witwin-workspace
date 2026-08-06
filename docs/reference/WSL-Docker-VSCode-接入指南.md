# Mac 通过 SSH 接入 Windows WSL Docker

本文记录已验证的接入方式：Mac 上的 VS Code 通过 SSH 进入 Windows 11 的 Ubuntu WSL2，再使用 Docker Desktop 的 WSL Integration 管理容器。

## 已验证环境

| 项目 | 值 |
|---|---|
| Windows | Windows 11 |
| WSL | Ubuntu 24.04，WSL 2，mirrored 网络模式 |
| WSL 用户 | `chenzhf` |
| SSH 地址 | `192.168.3.37:2222` |
| Docker | Docker Desktop 4.76.0 + WSL Integration |
| 运行中的容器 | `witwin-dev-20260714` |
| 容器工作目录 | `/opt/witwin` |

实际使用时，Windows 局域网 IP 可能变化，应以当前 IP 替换 `192.168.3.37`。

## 1. WSL 端配置

安装并启动 SSH：

```bash
sudo apt update
sudo apt install -y openssh-server
sudo service ssh start
```

在 `/etc/ssh/sshd_config.d/90-wsl-remote.conf` 中配置：

```text
Port 2222
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication yes
AllowUsers chenzhf
```

检查并重启：

```bash
sudo sshd -t
sudo service ssh restart
sudo sshd -T | grep -Ei 'passwordauthentication|kbdinteractiveauthentication|authenticationmethods|allowusers|usepam'
```

## 2. WSL 中确认 Docker

本次使用 Docker Desktop 的 WSL Integration，不是在 WSL 内单独安装 Docker Engine。

在 Docker Desktop 中打开：

```text
Settings → Resources → WSL Integration
```

启用 Ubuntu 后，在 WSL 中验证：

```bash
docker version
docker ps
```

Docker Socket 通常为 `/var/run/docker.sock`。登录用户需要属于 `docker` 组：

```bash
groups
sudo usermod -aG docker "$USER"
```

## 3. Windows 防火墙

使用 mirrored 网络模式时，Windows 与 WSL 共用局域网 IP，不要配置传统 `portproxy`。

在“管理员 PowerShell”执行：

```powershell
New-NetFirewallRule `
  -DisplayName "WSL SSH 2222" `
  -Direction Inbound `
  -Action Allow `
  -Protocol TCP `
  -LocalPort 2222 `
  -Profile Any `
  -RemoteAddress LocalSubnet
```

如果 `.wslconfig` 启用了 WSL Hyper-V 防火墙，再执行：

```powershell
New-NetFirewallHyperVRule `
  -Name "WSL-SSH-2222" `
  -DisplayName "WSL SSH 2222" `
  -Direction Inbound `
  -VMCreatorId "{40E0AC32-46A5-438A-A0B2-2B479E8F2E90}" `
  -Protocol TCP `
  -LocalPorts 2222 `
  -RemoteAddresses LocalSubnet `
  -Action Allow `
  -Profiles Any
```

验证：

```powershell
Test-NetConnection -ComputerName 192.168.3.37 -Port 2222
```

## 4. Mac SSH 配置

如果 Mac 尚无专用密钥：

```bash
mkdir -p ~/.ssh
chmod 700 ~/.ssh
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519 -C "mac-to-wsl"
```

将以下内容加入 Mac 的 `~/.ssh/config`：

```sshconfig
Host wsl-docker
    HostName 192.168.3.37
    User chenzhf
    Port 2222
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
```

## 5. 部署公钥

密码认证可用时，在 Mac 执行：

```bash
cat ~/.ssh/id_ed25519.pub | ssh -p 2222 chenzhf@192.168.3.37 \
  'umask 077; mkdir -p ~/.ssh; touch ~/.ssh/authorized_keys; key=$(cat); grep -qxF "$key" ~/.ssh/authorized_keys || printf "%s\n" "$key" >> ~/.ssh/authorized_keys; chmod 600 ~/.ssh/authorized_keys'
```

如果密码认证失败，可在 WSL 的 root shell 中直接部署 Mac 公钥：

```bash
install -d -m 700 -o chenzhf -g chenzhf /home/chenzhf/.ssh
cat ~/.ssh/id_ed25519.pub >> /home/chenzhf/.ssh/authorized_keys
chown chenzhf:chenzhf /home/chenzhf/.ssh/authorized_keys
chmod 600 /home/chenzhf/.ssh/authorized_keys
```

若公钥只在 Mac 上，请将 `cat ~/.ssh/id_ed25519.pub` 的输出复制到 WSL 的 `/home/chenzhf/.ssh/authorized_keys`。

## 6. 测试 Mac 到 WSL

```bash
ssh -o BatchMode=yes -o PasswordAuthentication=no wsl-docker
```

登录后确认：

```bash
id
docker ps
```

本次验证结果为：Mac 公钥登录成功，用户为 `chenzhf`，Docker 可用。

## 7. VS Code 接入 WSL

Mac VS Code 安装：

- `Remote - SSH`
- `Docker`
- 如需附加到容器，再安装 `Dev Containers`

执行 `Cmd + Shift + P`，选择：

```text
Remote-SSH: Connect to Host → wsl-docker
```

连接后，VS Code 的远程终端运行在 Ubuntu WSL 中，执行 `docker ps` 可以看到 Docker Desktop 中的容器。

## 8. 直接附加到运行中的容器

先通过 `Remote-SSH` 进入 WSL，再执行：

```text
Dev Containers: Attach to Running Container
```

选择：

```text
/witwin-dev-20260714
```

容器工作目录为 `/opt/witwin`。命令行验证：

```bash
docker exec -it witwin-dev-20260714 sh
```

## 9. 重要注意事项

当前容器没有挂载宿主机目录（`mounts=0`），容器删除或重建后，直接在容器内修改的文件可能丢失。

长期开发建议使用项目目录挂载、`devcontainer.json`，或在 WSL 中打开项目并让容器使用该目录。

## 10. 故障排查

### 端口不通

在 Mac 执行：

```bash
nc -vz 192.168.3.37 2222
```

检查 Windows 防火墙、Windows IP 和 WSL SSH 服务。

### `Permission denied (publickey,password)`

在 WSL 检查：

```bash
sudo sshd -T | grep -Ei 'passwordauthentication|allowusers|authenticationmethods'
sudo ls -ld /home/chenzhf/.ssh
sudo ls -l /home/chenzhf/.ssh/authorized_keys
```

权限应为：

```text
/home/chenzhf/.ssh                     700
/home/chenzhf/.ssh/authorized_keys     600
```

两个文件的所有者应为 `chenzhf`。

### IP 变化

mirrored 模式下通常使用 Windows 局域网 IP。若 IP 变化，只需更新 Mac `~/.ssh/config` 的 `HostName`，通常不需要 `portproxy`。

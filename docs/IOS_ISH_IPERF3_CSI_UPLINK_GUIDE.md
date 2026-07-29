# iPhone/iSH 可复现 iPerf3 上行流量配置

## 1. 目的与适用范围

本文用于让 iPhone 11 Pro 通过可复现的命令持续产生上行 UDP 流量，配合 Linux 主机上的 iPerf3 服务和 PicoScenes CSI 采集。推荐使用免费的 iSH Shell，在手机端通过脚本固定服务端、端口、带宽、报文长度和并发数，避免图形客户端误设为 TCP、多流或反向传输。

实验数据方向为：

```text
iPhone 11 Pro（iPerf3 客户端）
        │  Wi-Fi 上行 UDP
        ▼
无线接入点
        │
        ├── Linux 主机（iPerf3 服务端）
        └── AX200/PicoScenes（监听并采集 CSI）
```

AX200 是监听和采集设备，不需要充当接入点。手机应连接实验使用的 Wi-Fi，Linux 主机可以通过网线接入同一局域网。

## 2. 主机端基准配置

此前配置的主机端参数为：

- iPerf3 服务地址：`192.168.3.31`
- iPerf3 服务端口：`5201`
- systemd 服务：`picoscenes-iperf3.service`

每次实验前都应重新确认网卡地址，避免 DHCP 变化：

```bash
ip -4 -brief address show enp1s0
```

确认 iPerf3 服务正在运行：

```bash
systemctl is-active picoscenes-iperf3.service
systemctl status --no-pager picoscenes-iperf3.service
```

若主机地址不再是 `192.168.3.31`，应把手机端脚本中的服务地址改为上述命令显示的新地址。

无线接入点的信道和带宽也可能自动变化。开始采集前必须重新检查实际信道，不能长期硬编码此前使用的信道值。

## 3. iPhone 一次性系统配置

### 3.1 固定实验网络的私有 Wi-Fi 地址

打开：

```text
设置 → Wi-Fi → 当前实验网络右侧的“信息”按钮 → 私有 Wi-Fi 地址
```

在支持该选项的 iOS 版本中选择“固定”，然后记录此页面显示的 Wi-Fi 地址。这个地址是实验中需要使用的 iPhone 发送端 MAC，不能继续沿用之前 Android 手机的 MAC。

iOS 不允许普通应用通过脚本关闭或修改这个系统隐私设置，因此这一步需要在系统设置中完成一次。更换 SSID、重置网络设置或改变私有地址模式后，应重新核对 MAC。

### 3.2 允许 iSH 访问局域网

打开：

```text
设置 → 隐私与安全性 → 本地网络 → iSH
```

确保 iSH 的开关已打开。若尚未出现该项目，先在 iSH 中运行一次连接命令，待系统弹出权限请求时选择“允许”。

### 3.3 避免后台挂起

实验期间建议：

- 保持 iSH 位于前台；
- 临时把自动锁定设为“永不”；
- 关闭低电量模式；
- 手机保持固定位置和朝向；
- 避免实验过程中切换 Wi-Fi、蜂窝网络或应用。

## 4. 安装 iSH 和 iPerf3

iSH 中国大陆 App Store 页面：

<https://apps.apple.com/cn/app/ish-shell/id1436902243>

安装并打开 iSH 后，在其终端执行：

```sh
apk update
apk add iperf3
iperf3 --version
```

`apk update` 或软件下载较慢时，可以先换到速度较好的网络完成安装；正式实验时再连接实验 Wi-Fi。安装成功后无需每次重新下载。

## 5. 创建可复现的上行流量脚本

在 iSH 中完整执行以下命令：

```sh
cat > ~/csi-uplink.sh <<'EOF'
#!/bin/sh
set -eu

SERVER="${IPERF_SERVER:-192.168.3.31}"
PORT="${IPERF_PORT:-5201}"
BANDWIDTH="${IPERF_BANDWIDTH:-2M}"
PAYLOAD="${IPERF_PAYLOAD:-1200}"
DURATION="${1:-120}"

exec iperf3 \
  -c "$SERVER" \
  -p "$PORT" \
  -u \
  -b "$BANDWIDTH" \
  -l "$PAYLOAD" \
  -t "$DURATION" \
  -P 1
EOF

chmod +x ~/csi-uplink.sh
```

默认运行 120 秒：

```sh
~/csi-uplink.sh
```

运行 180 秒：

```sh
~/csi-uplink.sh 180
```

如果主机 IP 发生变化，可以在不修改脚本的情况下临时覆盖：

```sh
IPERF_SERVER=192.168.3.32 ~/csi-uplink.sh 120
```

也可以按实验需求临时覆盖带宽、端口或 UDP 负载长度：

```sh
IPERF_BANDWIDTH=4M IPERF_PAYLOAD=1200 ~/csi-uplink.sh 120
```

脚本的关键约束是：

- `-u`：使用 UDP；
- 不使用 `-R`：流量方向是 iPhone 到主机；
- `-P 1`：只建立一个流；
- `-b 2M`：默认目标速率为 2 Mbit/s；
- `-l 1200`：使用 1200 字节 UDP 负载，减少 IP 分片风险。

## 6. 推荐联调顺序

1. 在 Linux 主机上确认有线网卡 IP 和 `picoscenes-iperf3.service` 状态。
2. 确认 iPhone 已连接实验 SSID，并记录当前固定私有 Wi-Fi 地址。
3. 检查接入点的实际信道和带宽，使 AX200/PicoScenes 监听参数与之匹配。
4. 先启动 PicoScenes CSI 采集，并等待采集程序确认已成功启动。
5. 再在 iSH 中运行 `~/csi-uplink.sh 120`。
6. 采集结束后保存 iPerf3 输出、CSI 文件和本次实验元数据。

iPerf3 正常运行时，输出中应出现服务端连接信息、周期性传输统计，以及最终的 `sender`/`receiver` UDP 统计。若输出显示多个并发连接、TCP 或反向流量，则参数不符合本方案。

## 7. CSI 过滤条件

上行数据帧的建议识别条件为：

```text
Addr2 == 本次记录的 iPhone Wi-Fi MAC
ToDS  == 1
FromDS == 0
```

其中 `Addr2` 应使用 iPhone 当前实验 SSID 对应的私有 Wi-Fi 地址。不要使用蜂窝网络地址、蓝牙地址、旧 Android 手机地址或 iPhone 的其他接口地址。

建议在正式采集前先做一个较短的 20～30 秒测试，确认能够观察到该 MAC 的上行帧，再开始长时间实验。

## 8. 常见问题

### iPerf3 显示无法连接

依次检查：

1. iSH 是否获得“本地网络”权限；
2. iPhone 和 Linux 主机是否位于同一局域网；
3. 主机 IP 是否仍与脚本中的 `SERVER` 一致；
4. `picoscenes-iperf3.service` 是否处于 `active` 状态；
5. 是否有防火墙阻断 UDP/TCP 5201 端口。

### iPerf3 正常，但没有目标 CSI

依次检查：

1. iPhone 的私有 Wi-Fi 地址是否发生变化；
2. PicoScenes 是否监听了接入点当前实际信道和带宽；
3. 是否在 CSI 采集程序成功启动后才开始发送流量；
4. 过滤条件是否使用 `Addr2`、`ToDS=1`、`FromDS=0`；
5. 手机是否确实仍连接 Wi-Fi，而不是切换到了蜂窝网络。

### 流量运行一段时间后停止

保持 iSH 在前台，临时关闭自动锁定和低电量模式。iOS 会限制后台应用持续执行，普通第三方应用无法通过脚本永久绕过这一系统策略。

### `apk update` 或安装速度很慢

iSH 使用 Alpine Linux 软件仓库，网络跨境路径、DNS 或当前网络质量都可能影响速度。可以先在其他稳定网络中完成一次性安装，实验阶段只运行已经安装好的 `iperf3`。

## 9. 每次实验应保存的元数据

至少记录：

- iPhone 型号和 iOS 版本；
- 实验 SSID；
- 当前固定私有 Wi-Fi 地址；
- Linux 主机 IP 和 iPerf3 端口；
- iPerf3 版本；
- 实际执行命令和环境变量；
- UDP 带宽、负载长度、持续时间和并发数；
- 接入点实际信道、带宽和频段；
- PicoScenes 启停时间与输出文件名；
- 手机位置、朝向和是否移动；
- iPerf3 最终发送端/接收端统计。

这些信息应与 CSI 原始文件放在同一实验会话目录或其元数据文件中，便于复现和排查。

## 10. 参考资料

- iSH Shell（中国大陆 App Store）：<https://apps.apple.com/cn/app/ish-shell/id1436902243>
- Alpine Linux `iperf3` 软件包：<https://pkgs.alpinelinux.org/package/v3.21/main/x86_64/iperf3>
- Apple：控制 App 对本地网络的访问：<https://support.apple.com/en-gb/102229>
- Apple：私有 Wi-Fi 地址：<https://support.apple.com/en-mide/102509>

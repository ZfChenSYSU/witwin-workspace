# iPhone/Bonjour 可复现 iPerf3 上行流量配置

## 1. 方案结论

本方案用于让 iPhone 11 Pro 在主机 DHCP 地址变化后，仍能以固定名称产生可复现的上行 UDP 流量，配合 PicoScenes CSI 采集。

主方案不再使用 iSH 直接连接 IP，而是采用：

```text
iPhone 原生 iPerf3 客户端
        │
        │  连接 witwin-csi.local:5201
        │  UDP 上行
        ▼
无线接入点
        │
        ├── Linux 有线接口 enp1s0
        │       └── iPerf3 服务端
        │
        └── AX200/PicoScenes
                └── 监听同一无线信道并采集 CSI
```

底层网络仍然使用 IP，但 Bonjour/mDNS 会把固定名称 `witwin-csi.local` 动态解析为主机有线接口的当前地址。手机端不再保存或手工更新 `192.168.3.x` 地址。

## 2. 当前主机状态与问题

制定本方案时，主机状态为：

- 有线接口：`enp1s0`，当前地址 `192.168.3.31/24`；
- 无线接口：`wlp2s0`，当前地址 `192.168.3.38/24`；
- 两个接口都由 DHCP 自动分配，租期为 7200 秒；
- 两个接口位于同一 `192.168.3.0/24` 子网，共用网关 `192.168.3.100`；
- Avahi 已安装、启用并运行；
- 当前 `zyh-SER.local` 解析到无线地址 `192.168.3.38`；
- `picoscenes-iperf3.service` 硬绑定 `192.168.3.31:5201`。

现有配置有两个故障点：

1. 有线 DHCP 地址变化后，iPerf3 仍绑定旧地址，服务可能启动失败或无法连接；
2. 默认 mDNS 可能公布无线接口，手机可能连接到 `wlp2s0`，不符合“手机 Wi-Fi 上行、主机有线接收、AX200 采集”的实验路径。

## 3. 目标配置

目标行为如下：

- 手机始终使用 `witwin-csi.local`；
- Avahi 只在 `enp1s0` 上公布该名称；
- 只公布 IPv4，减少双栈选择带来的实验路径差异；
- iPerf3 监听通配地址，不硬编码 DHCP 地址；
- 无线接口 `wlp2s0` 可以脱离普通 Wi-Fi 连接并交给 PicoScenes；
- 端口固定为 `5201`；
- iPhone 使用固定的私有 Wi-Fi MAC，便于 CSI 帧过滤。

## 4. 主机端配置

### 4.1 配置 Avahi 固定名称和接口

编辑 `/etc/avahi/avahi-daemon.conf` 的 `[server]` 段，设置：

```ini
[server]
host-name=witwin-csi
domain-name=local
use-ipv4=yes
use-ipv6=no
allow-interfaces=enp1s0
```

文件中的其他段和现有安全设置应保留，不要用上述片段替换整个配置文件。

配置含义：

- `host-name=witwin-csi`：固定名称为 `witwin-csi.local`；
- `allow-interfaces=enp1s0`：只公布有线接口地址；
- `use-ipv6=no`：本实验固定使用 IPv4，避免 IPv6 隐私地址轮换和路径选择差异。

重新启动并检查：

```bash
systemctl restart avahi-daemon
systemctl is-active avahi-daemon
avahi-resolve-host-name -4 witwin-csi.local
```

最后一条命令应返回 `enp1s0` 当前地址，不应返回 `wlp2s0` 地址。

### 4.2 取消 iPerf3 的固定 IP 绑定

将 `/etc/systemd/system/picoscenes-iperf3.service` 中的：

```ini
ExecStart=/usr/bin/iperf3 --server --bind 192.168.3.31 --port 5201
```

改为：

```ini
ExecStart=/usr/bin/iperf3 --server --port 5201
```

然后执行：

```bash
systemctl daemon-reload
systemctl restart picoscenes-iperf3.service
systemctl is-active picoscenes-iperf3.service
ss -lntup 'sport = :5201'
```

监听结果应为通配地址的 `5201` 端口，而不是某个具体的 `192.168.3.x:5201`。

虽然 iPerf3 会监听所有本机地址，但手机通过 `witwin-csi.local` 只会获得 Avahi 在 `enp1s0` 上公布的地址，因此实验流量仍走有线接收路径。

### 4.3 主机端快速验证

在另一台支持 Bonjour 的设备上测试：

```bash
iperf3 \
  -c witwin-csi.local \
  -p 5201 \
  -u \
  -b 2M \
  -l 1200 \
  -t 10 \
  -P 1
```

应能正常连接并显示 UDP `sender`/`receiver` 统计。

## 5. iPhone 客户端

### 5.1 推荐应用

推荐使用原生应用“iPerf3 客户端与服务器”：

[https://apps.apple.com/cn/app/iperf3-%E5%AE%A2%E6%88%B7%E7%AB%AF%E4%B8%8E%E6%9C%8D%E5%8A%A1%E5%99%A8/id6755545337](https://apps.apple.com/cn/app/iperf3-%E5%AE%A2%E6%88%B7%E7%AB%AF%E4%B8%8E%E6%9C%8D%E5%8A%A1%E5%99%A8/id6755545337)

该应用支持：

- 主机名和 IP；
- TCP、UDP、上传、下载和双向测试；
- 持续时间、并行流、带宽和报文长度等高级参数；
- Apple 快捷指令；
- `x-callback-url` 自动化；
- 测试历史及 CSV/JSON 导出。

这是一次性付费应用。若不采用付费客户端，应使用第 9 节的后备方案。

### 5.2 一次性系统设置

在 iPhone 上：

1. 连接实验 SSID；
2. 打开“设置 → Wi-Fi → 当前网络 → 私有 Wi-Fi 地址”；
3. 选择“固定”，并记录当前显示的 Wi-Fi MAC；
4. 打开“设置 → 隐私与安全性 → 本地网络”；
5. 允许 iPerf3 客户端访问本地网络；
6. 实验期间关闭低电量模式并保持应用位于前台；
7. 临时关闭自动锁定，保持手机位置和朝向不变。

iOS 不允许普通应用通过脚本修改私有 Wi-Fi 地址或本地网络权限，因此这些系统设置需要手动完成一次。

### 5.3 保存实验配置

在客户端的高级模式中建立并保存配置：

- Server：`witwin-csi.local`
- Port：`5201`
- Protocol：UDP
- Direction：Upload
- Bandwidth：`2 Mbit/s`
- Packet size：`1200 bytes`
- Duration：`120 s`
- Streams：`1`
- Reverse：关闭
- Bidirectional：关闭

配置目标是单个、受控、持续的 iPhone 上行 UDP 流，不能使用多流 TCP 或反向下载。

### 5.4 Apple 快捷指令和 URL 自动化

应用公开的自动化 URL 为：

```text
iperf3cs://x-callback-url/run-test?server=witwin-csi.local&protocol=udp&direction=upload&durationSec=120&streams=1
```

可以在 Safari 中打开该 URL，也可以在 Apple“快捷指令”中使用“打开 URL”动作。

公开 URL API 当前包含服务器、协议、方向、持续时间和流数量；带宽与报文长度应先在应用高级模式中配置并保存。正式实验前必须核对仍为 `2 Mbit/s` 和 `1200 bytes`。

推荐快捷指令流程：

```text
打开 iPerf3 测试 URL
        ↓
保持应用前台运行 120 秒
        ↓
获取最近一次结果
        ↓
保存或导出结果
```

## 6. 推荐联调顺序

1. 主机确认有线连接、Avahi 和 iPerf3 服务正常；
2. 确认 `witwin-csi.local` 解析为 `enp1s0` 当前地址；
3. iPhone 连接实验 SSID，并核对固定私有 Wi-Fi MAC；
4. 检查接入点当前实际频段、信道和带宽；
5. 将 AX200 切换到 PicoScenes 所需模式和信道；
6. 先启动 CSI 采集，等待程序明确报告启动成功；
7. 再由 iPhone 快捷指令启动 120 秒 UDP 上行；
8. 采集结束后保存 CSI、客户端结果和实验元数据。

每次正式实验前，建议先运行 10～30 秒短测试。

## 7. CSI 过滤条件

上行数据帧建议按以下条件识别：

```text
Addr2  == 本次记录的 iPhone Wi-Fi MAC
ToDS   == 1
FromDS == 0
```

不要继续使用此前 Android 手机的 MAC，也不要使用 iPhone 的蜂窝、蓝牙或其他接口地址。

## 8. 故障排查

### `witwin-csi.local` 无法解析

检查：

```bash
systemctl status --no-pager avahi-daemon
avahi-resolve-host-name -4 witwin-csi.local
tcpdump -ni enp1s0 udp port 5353
```

同时确认：

- iPhone 与 `enp1s0` 位于同一局域网广播域；
- 接入点未启用客户端隔离、访客网络隔离或 mDNS 过滤；
- iOS 客户端已获得本地网络权限；
- Avahi 的 `allow-interfaces` 确实为 `enp1s0`。

### 名称解析成功但 iPerf3 无法连接

检查：

```bash
systemctl status --no-pager picoscenes-iperf3.service
ss -lntup 'sport = :5201'
journalctl -u picoscenes-iperf3.service -n 50 --no-pager
```

确认服务不再硬绑定旧 DHCP 地址，并检查防火墙是否阻断 TCP/UDP 5201。iPerf3 的 UDP 测试仍需要 TCP 控制连接。

### iPerf3 正常但没有目标 CSI

检查：

1. AX200 是否监听接入点当前实际信道和带宽；
2. iPhone 私有 Wi-Fi MAC 是否发生变化；
3. CSI 采集是否先于手机流量启动；
4. 过滤条件是否为 `Addr2`、`ToDS=1`、`FromDS=0`；
5. iPhone 是否仍使用 Wi-Fi，而不是蜂窝网络或 VPN。

### 地址变化后短时间无法连接

mDNS 客户端可能暂存旧记录。先等待数秒并重试；必要时切换一次 iPhone Wi-Fi，促使系统重新发现。不要把新 IP 写回快捷指令。

## 9. 保留 iSH 时的后备方案

iSH 当前不能可靠解析 `.local` 地址，原因包括 musl/mDNS 支持和 iOS 多播权限限制。因此，主方案不能在 iSH 中直接执行：

```sh
iperf3 -c witwin-csi.local
```

如果必须保留 iSH，应在路由器中为有线接口 MAC `70:70:FC:04:ED:54` 配置 DHCP 地址保留，再在 iSH `/etc/hosts` 中设置本地别名，例如：

```text
192.168.3.31 witwin-csi
```

iSH 脚本随后可以使用：

```sh
iperf3 -c witwin-csi -p 5201 -u -b 2M -l 1200 -t 120 -P 1
```

该方式只是把固定 IP 隐藏在 `/etc/hosts` 中，仍依赖路由器地址保留，不具备 Bonjour 的自动发现能力。

## 10. 实验元数据

每次实验至少保存：

- iPhone 型号和 iOS 版本；
- 客户端应用及版本；
- 实验 SSID 和固定私有 Wi-Fi MAC；
- 服务名称 `witwin-csi.local`；
- 名称实际解析到的有线 IPv4；
- iPerf3 端口和版本；
- UDP 带宽、报文长度、持续时间和流数量；
- 接入点频段、信道和带宽；
- PicoScenes 启停时间与输出文件名；
- 手机位置、朝向和移动情况；
- iPerf3 最终发送端与接收端统计。

这些信息应与 CSI 原始文件放在同一实验会话目录或其元数据文件中。

## 11. 参考资料

- Apple Bonjour 和 `.local` 名称：[https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/NetServices/Articles/about.html](https://developer.apple.com/library/archive/documentation/Cocoa/Conceptual/NetServices/Articles/about.html)
- Apple 本地网络权限：[https://support.apple.com/en-gb/102229](https://support.apple.com/en-gb/102229)
- Apple 私有 Wi-Fi 地址：[https://support.apple.com/en-mide/102509](https://support.apple.com/en-mide/102509)
- iSH `.local` 解析限制：[https://github.com/ish-app/ish/issues/2748](https://github.com/ish-app/ish/issues/2748)
- iPerf3 iOS 客户端：[https://apps.apple.com/cn/app/iperf3-%E5%AE%A2%E6%88%B7%E7%AB%AF%E4%B8%8E%E6%9C%8D%E5%8A%A1%E5%99%A8/id6755545337](https://apps.apple.com/cn/app/iperf3-%E5%AE%A2%E6%88%B7%E7%AB%AF%E4%B8%8E%E6%9C%8D%E5%8A%A1%E5%99%A8/id6755545337)
- iPerf3 客户端自动化接口：[https://iperf3app.com/ios/shortcuts/](https://iperf3app.com/ios/shortcuts/)

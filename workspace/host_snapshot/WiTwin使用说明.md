# WiTwin 使用说明：面向 `w_{hd}` 仿真验证

版本：2026-07-08

本文基于 WiTwin 官网、官方文档和 GitHub 仓库信息整理，目标是说明如何把 WiTwin 用于本项目的 `w_{hd}` 仿真科学假设验证。

参考资料：

- WiTwin 官网：https://witwin.ai/
- WiTwin 文档：https://witwin.ai/docs/witwin/v0.1.0/en
- Installation：https://witwin.ai/docs/witwin/v0.1.0/en/getting-started/installation
- Quick Start：https://witwin.ai/docs/witwin/v0.1.0/en/getting-started/overview
- Design Principle：https://witwin.ai/docs/witwin/v0.1.0/en/getting-started/design-principle
- Core Classes：https://witwin.ai/docs/witwin/v0.1.0/en/api/core-classes
- `witwin-channel` GitHub：https://github.com/witwin-ai/witwin-channel
- `witwin-maxwell` GitHub：https://github.com/witwin-ai/witwin-maxwell

## 1. WiTwin 是什么

WiTwin，也称 RF Digital Twin，是面向无线系统的物理可微仿真平台。官网将其定位为面向无线感知和通信研究的下一代 RF digital twin 平台，核心特点包括：

- 物理建模。
- 可微计算。
- RF 渲染和反演优化。
- Python API。
- Web Studio 可视化编辑器。
- 与神经网络和梯度优化流程结合。

对本项目而言，最重要的是它可以用于构造室内无线传播场景，并对发射端、接收端、墙体材料、人体模型位置等参数做仿真和优化。

## 2. 哪个模块最适合本项目

WiTwin 生态中有几个相关模块：

| 模块 | 作用 | 本项目推荐度 |
|---|---|---:|
| `witwin` / Core | 场景、几何、材料、组件系统和 Studio 基础 | 中 |
| `witwin-channel` | 可微无线信道仿真，支持 radiomap、path、CIR/CFR | 高 |
| `witwin-maxwell` | 可微全波电磁 FDTD 求解器 | 中低 |
| Studio | Web 可视化编辑器 | 辅助使用 |

本项目第一阶段是验证：

```text
人体-手机距离扰动 d_t 是否显著影响 CSI
```

因此优先建议使用：

```text
witwin-channel
```

原因是 `witwin-channel` 明确面向无线信道仿真，支持几何可微、材料参数、发射端、接收端、ReceiverGrid、path-level CIR/CFR、LOS、多次反射和 UTD-style diffraction。它比全波 FDTD 更适合先做室内尺度的快速假设验证。

`witwin-maxwell` 更适合之后做小尺度、高精度局部验证，例如人体近场、手机附近局部散射、材料参数灵敏度等。它是 full-wave solver，计算成本更高，不建议作为第一阶段主线。

## 3. 当前成熟度判断

需要注意：WiTwin 当前仍处于较早版本。

根据官方页面和 GitHub 信息：

- 官网展示了 `pip install witwin`、`pip install witwin[maxwell]`、`pip install witwin[radar]` 等安装入口。
- 官方文档的 Installation 页面仍写着 Python package 将很快在 PyPI 发布。
- `witwin-channel` GitHub README 明确提示这是 experimental early release，API 可能频繁变化。
- `witwin-channel` 的推荐公共使用形式是：

```text
Scene + solver.solve(scene, config) + Result
```

因此建议把 WiTwin 作为“仿真验证工具候选”，而不是一开始就假设它一定能无缝跑通完整项目。

## 4. 环境要求

### 4.1 通用要求

官方文档给出的基本要求包括：

- Python 3.9 或更高。
- CUDA 11.8 或 12.x。
- Windows 10/11、Ubuntu 20.04+ 或 macOS 12+。
- GPU 加速需要 NVIDIA GPU，建议 RTX 20 系列或更新。

### 4.2 `witwin-channel` 建议环境

`witwin-channel` GitHub README 中更具体地给出：

- Windows 或 Linux。
- NVIDIA GPU。
- CUDA-capable Python 环境。
- Python 3.10 或更新。
- Dr.Jit 1.3.1。
- 支持 CUDA 的 PyTorch。

建议本项目采用：

```text
Windows 或 Ubuntu
Python 3.11
NVIDIA GPU
CUDA 12.1 或与本机驱动匹配的版本
PyTorch CUDA build
```

## 5. 安装建议

### 5.1 优先尝试 PyPI 安装

先尝试官网给出的安装方式：

```bash
pip install witwin
```

如果需要 Maxwell：

```bash
pip install witwin-maxwell
```

或：

```bash
pip install witwin[maxwell]
```

如果安装失败，说明 PyPI 包或 extras 仍未完全开放，应转向 GitHub 本地安装。

### 5.2 `witwin-channel` 本地安装

推荐为本项目单独建环境：

```bash
conda create -n witwin python=3.11 -y
conda activate witwin
```

安装 CUDA 版 PyTorch。以下只是 CUDA 12.1 示例，实际应与本机驱动匹配：

```bash
python -m pip install torch --index-url https://download.pytorch.org/whl/cu121
```

然后获取 `witwin-channel` 仓库并安装：

```bash
git clone https://github.com/witwin-ai/witwin-channel.git
cd witwin-channel
python -m pip install -e . --no-build-isolation --no-deps
```

如果不需要 editable install：

```bash
python -m pip install . --no-deps
```

安装后建议先运行测试或最小示例，确认 CUDA、PyTorch 和 native extension 没有问题。

## 6. WiTwin 基本概念

### 6.1 Scene

`Scene` 是整个仿真环境，包含：

- 几何结构。
- 材料。
- 发射端。
- 接收端。
- 频率。
- 设备，例如 `cuda`。

### 6.2 Structure

`Structure` 表示场景里的物体，例如：

- 墙体。
- 地面。
- 天花板。
- 人体近似模型。
- 家具。

结构通常由几何和材料组成。

### 6.3 Material

`Material` 表示电磁材料属性，例如：

- 相对介电常数 `eps_r`。
- 电导率 `sigma_e`。

本项目中，墙体、人体、衣物都可以先用简化材料建模。

### 6.4 Transmitter 和 Receiver

本项目对应关系建议为：

```text
Transmitter = 手机 Wi-Fi 发射端
Receiver = AX210/AX200 监听网卡，或仿真中的 AP/接收端
```

如果使用旁路监听方案，真实测量链路是：

```text
phone -> monitoring NIC
```

因此 WiTwin 仿真中也应把接收端放在监听网卡位置，而不是路由器位置。

### 6.5 Solver

`witwin-channel` 提供三类主要 solver：

- `deterministic.solve(...)`：适合做可重复的 radiomap。
- `montecarlo.solve(...)`：适合采样式 radiomap。
- `path.solve(...)`：适合导出离散路径、CIR、CFR、delay、AoA/AoD、交互类型和几何信息。

本项目建议优先使用：

```text
path.solve(...)
```

原因是你关心的是人体距离扰动对 CSI 的影响，而 path solver 可以直接给出路径、CIR/CFR 和几何 payload，更容易分析人体参与了哪些路径。

## 7. 面向本项目的使用流程

### 7.1 第一步：最小房间

先构建一个非常简单的室内场景：

```text
房间：长方体空间
墙体：4 面墙 + 地面 + 天花板
发射端：手机
接收端：监听网卡或 AP
人体：圆柱体或椭球体
频率：2.4 GHz 或 5 GHz
```

不要一开始导入复杂 SLAM mesh。第一阶段要验证的是 `w_{hd}` 是否显著，不是追求真实房间高保真。

### 7.2 第二步：定义人体-手机距离

定义：

```text
d_t = 手机天线中心到人体躯干参考点的距离
```

仿真时设置：

```text
d_0 = 0.40 m
d_t in [0.25 m, 0.70 m]
```

然后让人体模型相对手机移动，而不是让整个房间变化。

### 7.3 第三步：生成对照数据

至少生成三类数据：

| 组别 | 设置 | 目的 |
|---|---|---|
| BASE | 固定 `d_t = d_0` | 无距离扰动基线 |
| WHD | `d_t` 随时间扰动 | 观察 `w_{hd}` 是否改变 CSI |
| ORACLE | 优化时知道真实 `d_t` | 作为上限对照 |

### 7.4 第四步：输出 CSI 相关指标

对每个接收点或时间戳，尽量输出：

- CFR：子载波频率响应。
- CIR：时延域冲激响应。
- path coefficient。
- path delay。
- AoA/AoD。
- path interaction type。
- optional geometry payload。

如果 path solver 可以直接返回 CFR，则最适合和实测 CSI 对齐。

### 7.5 第五步：判断 `w_{hd}` 是否显著

计算：

```math
\Delta s(d_t) = s(d_t) - s(d_0)
```

分别分析：

```math
\Delta A = |s(d_t)| - |s(d_0)|
```

```math
\Delta \phi = wrap(angle(s(d_t)) - angle(s(d_0)))
```

判断：

- 如果 `d_t` 改变 5-10 cm 就能造成稳定可观测变化，`w_{hd}` 值得继续建模。
- 如果只有极端变化才明显，可以把 `w_{hd}` 降级为鲁棒损失或域随机化问题。

## 8. 项目最小代码框架

下面是面向本项目的伪代码框架。具体 API 可能随 WiTwin 版本变化，需要以安装后的仓库示例和 README 为准。

```python
import numpy as np
import witwin.channel as wc

def make_scene(phone_pos, rx_pos, body_pos, frequency=2.4e9):
    structures = []

    # 一面墙示例；实际应加入四面墙、地面、天花板
    structures.append(
        wc.Structure(
            name="wall_x0",
            geometry=wc.Box(
                position=(0.0, 0.0, 1.5),
                size=(0.20, 5.0, 3.0),
                device="cuda",
            ),
            material=wc.Material(eps_r=4.0, sigma_e=0.01),
        )
    )

    # 人体简化为圆柱体或 box；若当前版本没有 Cylinder，可先用 Box 近似
    structures.append(
        wc.Structure(
            name="human_body",
            geometry=wc.Box(
                position=body_pos,
                size=(0.45, 0.25, 1.70),
                device="cuda",
            ),
            material=wc.Material(eps_r=40.0, sigma_e=1.0),
        )
    )

    scene = wc.Scene(
        structures=structures,
        transmitters=[
            wc.Transmitter("phone_tx", tuple(phone_pos)),
        ],
        receivers=[
            wc.Receiver("rx0", tuple(rx_pos)),
        ],
        frequency=frequency,
        device="cuda",
    )

    return scene

def body_position_from_distance(phone_pos, d, direction=(0.0, -1.0, 0.0)):
    direction = np.asarray(direction, dtype=float)
    direction = direction / np.linalg.norm(direction)
    return tuple(np.asarray(phone_pos) + d * direction + np.array([0.0, 0.0, 0.0]))

phone_pos = np.array([0.0, 0.0, 1.2])
rx_pos = np.array([3.0, 0.0, 1.2])

subcarriers_hz = np.linspace(-10e6, 10e6, 64)
d_values = [0.25, 0.35, 0.40, 0.50, 0.60]

records = []

for d in d_values:
    body_pos = body_position_from_distance(phone_pos, d)
    scene = make_scene(phone_pos, rx_pos, body_pos)

    result = wc.path.solve(
        scene=scene,
        transmitter="phone_tx",
        receiver=["rx0"],
        config=wc.path.Config(
            num_samples=256,
            max_bounces=1,
            max_diffraction_order=0,
            max_num_paths=16,
            return_geometry=True,
            edge_policy=wc.EdgePolicy(edge_selection_mode="all_edges"),
        ),
    )

    cir_coeff, cir_delay = result.cir()
    cfr = result.cfr(subcarriers_hz)

    records.append({
        "d": d,
        "cir_coeff": cir_coeff,
        "cir_delay": cir_delay,
        "cfr": cfr,
    })
```

## 9. 推荐实验设计

### 9.1 实验 A：距离敏感性

固定：

- 手机位置。
- 接收端位置。
- 房间材料。
- 人体材料。

只改变：

```text
d_t = 0.25, 0.30, 0.35, ..., 0.70 m
```

输出：

- `|CFR|` 随 `d_t` 变化。
- `angle(CFR)` 随 `d_t` 变化。
- path delay 和 path coefficient 随 `d_t` 变化。

### 9.2 实验 B：错误固定 `d_0`

生成数据时使用真实扰动 `d_t`，优化时固定 `d_0 = 0.40 m`。

目标：

```text
验证忽略 w_hd 是否会让环境参数 theta 被错误更新。
```

### 9.3 实验 C：`d_t` 可辨识性

固定 `theta = theta^*`，只估计 `d_t`。

如果此时 `d_t` 都恢复不好，就不要急着做 EKF/UKF；如果恢复稳定，再考虑：

- 离线平滑估计。
- 交替优化 `d_t` 和 `theta`。
- EKF/UKF 在线估计。

## 10. 与真实 CSI 的对接方式

真实数据来自 AX210/AX200 时，应把链路写成：

```text
phone -> monitoring NIC
```

WiTwin 中对应：

```text
Transmitter.position = 手机 SLAM 轨迹位置
Receiver.position = AX210/AX200 天线位置
```

如果真实测量使用 AP 端 CSI，则对应：

```text
Transmitter.position = 手机 SLAM 轨迹位置
Receiver.position = AP 天线位置
```

这两种不能混用。

## 11. 注意事项

1. **不要一开始就追求真实房间 mesh。**

   先用 box 墙体和简化人体跑通 `w_{hd}` 敏感性验证。

2. **优先使用 path solver。**

   它能给出 CIR/CFR 和路径级信息，更适合分析人体距离扰动。

3. **谨慎使用相位。**

   仿真相位和真实 CSI 相位之间还有硬件频偏、采样偏移、时钟不同步等问题。第一阶段可先看相对相位变化。

4. **注意 WiTwin 版本变化。**

   `witwin-channel` 明确是 early release，API 可能变化。所有代码都应以当前安装版本的 README、examples、tests 为准。

5. **Maxwell 不建议作为第一阶段主线。**

   它适合 full-wave、小尺度、高精度验证，但算力成本高。阶段一更适合 `witwin-channel`。

## 12. 本项目推荐执行顺序

```text
1. 安装或拉取 witwin-channel
2. 跑通官方 quick start
3. 用一个墙体 + 一个 Tx + 一个 Rx 复现 path/radiomap 输出
4. 加入简化人体模型
5. 扫描 d_t，画出 CFR/CIR 变化
6. 加入简单 theta 参数，例如墙体 eps_r
7. 验证错误固定 d_0 是否导致 theta 偏差
8. 判断 d_t 是否可辨识
9. 再决定是否进入真实 CSI 对齐
```

## 13. 结论

WiTwin 很适合作为本项目 `w_{hd}` 仿真验证的候选工具，尤其是 `witwin-channel`。建议先用它完成一个最小实验：

```text
phone Tx + monitoring NIC Rx + wall + simplified human body
```

然后扫描人体-手机距离 `d_t`，观察 CFR/CIR 是否出现稳定变化。如果该实验成立，再继续做 `theta` 偏差分析、`d_t` 可辨识性和真实 CSI 对接。


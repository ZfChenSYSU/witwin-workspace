# 前置深度传感器实时获取人体—手机距离 `d_t` 的实现与算法方案

版本：2026-07-17

## 0. 结论摘要

使用手机前置深度传感器实时获取人体—手机相对距离是可行的，但必须先区分三个量：

1. 前置传感器直接测得的是“前摄像头到人脸或可见人体表面”的距离；
2. 无线仿真真正需要的是“手机 Wi-Fi 天线到人体电磁模型参考点”的相对位置；
3. `w_hd` 是错误人体几何在 CSI 中造成的建模误差，而 `d_t` 是产生该误差的物理状态，二者不应混用。

本项目推荐的首选路线是：

```text
后摄像头 + IMU：ARKit 世界跟踪，输出手机位姿
前置 TrueDepth：ARKit 人脸跟踪，输出人脸三维位姿
设备/人体标定：将“相机—人脸”换算为“天线—胸腔参考点”
质量控制：物理门限 + Hampel/MAD 异常检测
在线处理：自适应卡尔曼滤波
离线处理：RTS 平滑或因子图平滑
最终输出：人体相对手机的三维向量、标量距离和协方差
```

如果 ARKit 的人脸三维锚点已经满足精度要求，没有必要为了获得 `d_t` 强行读取和处理整张原始深度图。只有在需要直接定位胸口、肩部或人体表面时，才优先考虑原始 TrueDepth 深度图路线。

---

## 1. 首先定义真正需要估计的量

### 1.1 `d_t` 的物理定义

沿用当前项目定义：

```math
d_t = \left\|\mathbf p^A_{B,t}\right\|_2
```

其中：

- `A`：手机 Wi-Fi 天线坐标系；
- `B`：人体电磁模型参考点，初期可定义为胸腔近似反射中心；
- `\mathbf p^A_{B,t}`：时刻 `t` 人体参考点在手机天线坐标系中的三维位置。

仅保存标量 `d_t` 会丢失方向信息。对射线追踪更有价值的状态实际上是：

```math
\mathbf r_t = \mathbf p^A_{B,t}
= [x_t, y_t, z_t]^T
```

也可以表示成：

```math
h_t = [d_t, \alpha_t, \beta_t]^T
```

其中 `\alpha_t`、`\beta_t` 分别为人体相对手机的方位角和俯仰角。建议数据文件同时保存 `\mathbf r_t` 和 `d_t`，仿真阶段优先使用三维向量。

### 1.2 前置深度传感器直接提供什么

根据具体接口，前置传感器可能提供：

- 人脸锚点在世界坐标系中的三维变换矩阵；
- 人脸网格或人眼等关键点的三维位置；
- 原始逐像素深度图或视差图；
- 深度时间戳；
- 部分接口下的深度置信度或数据有效性信息。

这些量均不直接等于 `\mathbf p^A_{B,t}`。中间还需要两个标定关系：

```math
{}^C\mathbf p_A
```

表示 Wi-Fi 天线参考点在前摄像头坐标系 `C` 中的位置；以及：

```math
{}^F\mathbf p_B
```

表示胸腔参考点相对于人脸参考系 `F` 的近似位置。

### 1.3 坐标变换

若 ARKit 给出世界坐标系下的手机相机位姿和人脸位姿：

```math
{}^WT_C(t), \qquad {}^WT_F(t)
```

则人脸在相机坐标系下的变换为：

```math
{}^CT_F(t) = ({}^WT_C(t))^{-1}{}^WT_F(t)
```

若已有胸腔相对人脸的标定 `{}^FT_B`，则：

```math
{}^CT_B(t) = {}^CT_F(t){}^FT_B
```

设天线在相机坐标系中的位置为 `{}^C\mathbf p_A`，胸腔点为 `{}^C\mathbf p_{B,t}`，则：

```math
\mathbf p^C_{B-A,t} = {}^C\mathbf p_{B,t} - {}^C\mathbf p_A
```

```math
d_t = \left\|\mathbf p^C_{B-A,t}\right\|_2
```

由于相机坐标系和天线坐标系刚性连接，可以再通过固定旋转将相对向量变换到天线或手机机体坐标系。

需要注意：头部相对躯干会转动，不能无条件认为 `{}^FT_B` 是严格刚体变换。初期可以使用该近似，但必须通过动态实验量化它带来的误差。

---

## 2. 算法设计前的思考方向

本节先讨论“问题应如何建模”，下一节之后再给出具体算法。

### 2.1 先解决可观测性，而不是先选择滤波器

首先应验证前置传感器在真实手持姿态下能否持续看到目标：

- 人脸是否稳定处于前摄像头视场内；
- 胸口或肩部是否可见；
- 手机横竖屏、低头、转头时人脸锚点是否稳定；
- 行走产生的运动模糊是否导致跟踪中断；
- 口罩、眼镜、帽子及弱光是否影响深度或人脸跟踪；
- 双摄并发时帧率、分辨率和发热是否可接受。

如果只能稳定看到人脸，研究对象应写成“通过人脸三维位姿和人体标定间接估计胸腔位置”，不能写成“前置深度传感器直接测得胸腔距离”。

### 2.2 应优先估计三维相对几何，而不只是一个距离标量

无线传播不仅对人体—手机距离敏感，也对人体处于手机的哪个方向敏感。两个状态可能具有相同 `d_t`，但一个人体位于手机正后方，另一个位于手机侧方，对 LOS 遮挡和人体反射路径的影响完全不同。

因此推荐输出：

```text
主输出：r_body_phone = [x, y, z]
派生输出：d_t = norm(r_body_phone)
可选输出：方位角、俯仰角、人体姿态类别
```

### 2.3 实时深度使 `d_t` 从隐变量变成“带噪观测量”

没有前置深度时，`d_t` 可能需要通过 CSI 反推，是一个容易与环境参数 `\theta` 混淆的隐变量。

有实时前置深度后，更合理的观测模型是：

```math
\mathbf z_t^{depth} = \mathbf r_t + \mathbf v_t,
\qquad \mathbf v_t \sim \mathcal N(0, R_t)
```

此时算法任务变成：

1. 从传感器数据中提取有效人体位置；
2. 去除跳变和错误人脸；
3. 估计平滑但允许真实动作变化的状态；
4. 输出每一时刻的不确定度；
5. 将该观测作为射线追踪输入或软约束。

这比“只根据 CSI 用 EKF/UKF 估计 `d_t`”更稳定，也更容易分离人体误差与环境参数误差。

### 2.4 不应把滤波后的数值当成无误差真值

误差至少来自：

- TrueDepth 或人脸锚点测量噪声；
- 前摄像头到天线的标定误差；
- 人脸到胸腔参考点的近似误差；
- 头部相对躯干运动；
- 时间同步误差；
- 人体电磁反射中心本身不是一个固定解剖点。

因此输出应包含：

```text
timestamp
r_body_phone_x/y/z
d_body_phone
velocity_x/y/z 或 d_dot
measurement_quality
tracking_state
covariance 或 sigma_d
source
```

后续优化使用 `\sigma_{d,t}` 或协方差 `P_t`，而不是把 `\hat d_t` 当成完全准确的硬真值。

### 2.5 在线与离线的目标不同

- 在线算法要求低延迟、连续输出和掉帧恢复，适合自适应卡尔曼滤波或 One Euro Filter；
- 离线科研分析可以利用整段序列，适合 RTS smoother、滑窗优化或因子图；
- 用于论文报告的高质量 `d_t` 参考序列，应该优先采用离线平滑结果；
- 用于实时数字孪生更新的输入，采用因果在线滤波结果。

### 2.6 `d_t` 处理应尽量独立于 CSI

主实验中应先由视觉/深度传感器独立得到 `d_t`，再用于解释 CSI。若一开始就让 CSI 同时校正 `d_t` 和 `\theta`，会重新引入参数混淆，难以证明改进究竟来自人体几何测量还是 CSI 过拟合。

推荐分两步：

```text
第一步：只用前置深度 + 几何标定产生 d_t 和不确定度
第二步：把 d_t 输入可微射线追踪，优化环境参数 theta
```

只有在上述独立路线验证通过后，才尝试视觉、CSI 与射线追踪的联合优化。

---

## 3. 数据获取的具体实现路径

### 3.1 路线 A：ARKit 世界跟踪 + 前置人脸三维锚点（首选）

#### 3.1.1 适用条件

- 使用支持前置 TrueDepth 的兼容 iPhone/iPad；
- 设备返回 `ARWorldTrackingConfiguration.supportsUserFaceTracking == true`；
- 后摄像头负责世界跟踪；
- 前摄像头只需输出使用者人脸的三维位姿，不要求保存原始前置深度图。

Apple 官方提供了“世界跟踪过程中同时跟踪使用者人脸”的配置。它能够在后摄像头进行世界跟踪时，通过前摄像头产生 `ARFaceAnchor`。人脸锚点的 `transform` 位于 ARKit 世界坐标系中，单位为米。

#### 3.1.2 Swift 实现骨架

以下代码是实现结构示意，实际工程还需加入权限、错误处理、数据写盘和线程同步：

```swift
import ARKit
import simd

final class CaptureController: NSObject, ARSessionDelegate {
    let session = ARSession()

    // 由设备标定得到：前摄像头光心到 Wi-Fi 天线参考点，单位 m
    let antennaInCamera = SIMD3<Float>(0.0, 0.0, 0.0)

    // 由人体标定得到；这里只是示意，不能直接作为所有人的固定真值
    let faceToChest = matrix_identity_float4x4

    func start() {
        guard ARWorldTrackingConfiguration.supportsUserFaceTracking else {
            fatalError("当前设备不支持世界跟踪与用户人脸跟踪并发")
        }

        let config = ARWorldTrackingConfiguration()
        config.userFaceTrackingEnabled = true
        config.worldAlignment = .gravity

        session.delegate = self
        session.run(config, options: [.resetTracking, .removeExistingAnchors])
    }

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        guard let face = frame.anchors.compactMap({ $0 as? ARFaceAnchor }).first else {
            // 记录 tracking_lost，不要用 0 或上一帧冒充当前测量
            return
        }

        let worldFromCamera = frame.camera.transform
        let worldFromFace = face.transform
        let cameraFromFace = simd_inverse(worldFromCamera) * worldFromFace
        let cameraFromChest = cameraFromFace * faceToChest

        let chestInCamera = SIMD3<Float>(
            cameraFromChest.columns.3.x,
            cameraFromChest.columns.3.y,
            cameraFromChest.columns.3.z
        )

        let relative = chestInCamera - antennaInCamera
        let dRaw = simd_length(relative)

        // frame.timestamp、relative、dRaw、跟踪状态和质量指标进入后续滤波器
        saveOrFilter(timestamp: frame.timestamp,
                     relative: relative,
                     distance: dRaw)
    }
}
```

#### 3.1.3 这条路线实际测得的是什么

`ARFaceAnchor` 给出的是人脸参考系，不是胸腔。建议依次验证三种换算模型：

1. **固定偏移模型**

   ```math
   {}^F\mathbf p_B = \text{constant}
   ```

   实现最简单，但头部转动时误差较大。
2. **个体线性标定模型**

   ```math
   d_t^{body} = a_i d_t^{face} + b_i
   ```

   `a_i,b_i` 针对第 `i` 个实验人员，通过若干固定距离标定得到。适合只需要标量距离的初期实验。
3. **姿态条件模型**

   ```math
   \mathbf r_t^{body}
   = g(\mathbf r_t^{face}, R_t^{face}, \text{shoulder landmarks})
   ```

   将人脸位置、头部姿态和肩部关键点共同用于推算胸腔参考点。精度潜力最高，但需要前摄画面能看到肩部或上身。

首轮实验建议使用模型 1 和模型 2 做 baseline，再根据误差决定是否实现模型 3。

### 3.2 路线 B：读取原始 TrueDepth 深度图并定位胸腔 ROI

#### 3.2.1 适用条件

- 前摄画面能覆盖胸部或肩部；
- 研究需要人体表面深度，而不只是人脸锚点；
- 具体设备支持所需的前后摄像头组合；
- 可以接受自行处理后摄视频的 SLAM，或采用与 ARKit 不冲突的数据采集架构。

AVFoundation 的 `AVCaptureDepthDataOutput` 可以流式输出 `AVDepthData`。通常还需要：

- `AVCaptureVideoDataOutput`：前摄 RGB；
- `AVCaptureDepthDataOutput`：前摄深度；
- `AVCaptureDataOutputSynchronizer`：同步 RGB 与深度；
- `AVCaptureMultiCamSession`：在设备支持时并发前后摄像头；
- 后摄视频输出：供独立 SLAM/VIO 使用。

启动前必须运行时检查：

```text
AVCaptureMultiCamSession.isMultiCamSupported
前后摄像头是否属于支持的并发设备组合
前摄 activeFormat 是否存在 supportedDepthDataFormats
session.canAddInput / canAddOutput
hardwareCost 和 systemPressureCost
```

不能假设所有带 TrueDepth 的手机都能在任意分辨率下同时输出前摄 RGB、前摄深度和后摄 RGB。

#### 3.2.2 一个重要 API 边界

ARKit 的 `ARFrame.capturedDepthData` 官方定义为前摄人脸类体验中的深度数据；在其他 AR 配置下可能为 `nil`。因此：

- `ARWorldTrackingConfiguration + userFaceTrackingEnabled` 路线应主要使用 `ARFaceAnchor` 获取实时人脸距离；
- 不应假设它同时提供可直接读取的完整前置原始深度图；
- 如果必须取得原始前置深度图，应单独验证 `ARFaceTrackingConfiguration` 或 AVFoundation 采集路线；
- 如果 AVFoundation 接管前后摄像头，不能再默认 ARKit 可同时接管同一摄像头完成世界跟踪，应通过后摄视频运行独立 SLAM/VIO，或重新设计采集模式。

#### 3.2.3 从深度图提取胸腔距离

推荐流程：

```text
前摄 RGB
  -> 人体/人脸/肩部关键点检测
  -> 定义胸腔 ROI 或人体躯干 mask

前摄深度图
  -> 对齐到 RGB
  -> 过滤无效像素和低置信度像素
  -> 在胸腔 ROI 内计算稳健深度
  -> 反投影为三维胸腔点
  -> 减去相机—天线固定外参
  -> 得到 r_t 和 d_t
```

不建议直接使用胸腔 ROI 的中心像素深度，因为单个像素容易受空洞、衣物边缘和背景污染。推荐使用：

```math
z_t = \operatorname{median}\{D_t(u,v):(u,v)\in\Omega_{chest}\}
```

或使用 10%–90% 截尾均值。深度离散程度可用 MAD 估计：

```math
\operatorname{MAD}_t
= \operatorname{median}_{i}\left|D_{t,i}
- \operatorname{median}_{j}(D_{t,j})\right|
```

将像素 `(u,v)` 和深度 `z` 反投影为相机坐标：

```math
x = \frac{(u-c_x)z}{f_x},\qquad
y = \frac{(v-c_y)z}{f_y},\qquad
z=z
```

随后用相机—天线外参得到人体相对天线的三维位置。

### 3.3 路线选择建议

| 路线                      | 直接输出           | 与后摄世界跟踪关系         | 实现难度 | 建议定位             |
| ------------------------- | ------------------ | -------------------------- | -------: | -------------------- |
| ARKit 世界跟踪 + 人脸锚点 | 人脸三维位姿       | 官方支持的兼容组合         |       低 | 首选 MVP             |
| 原始 TrueDepth + 胸腔 ROI | 人体表面逐像素深度 | 需验证多摄并发和 SLAM 架构 |       高 | 高精度增强           |
| 普通前摄 RGB 单目估计     | 人脸/人体尺度代理  | 多数设备可做               |       中 | 无深度硬件时的对照组 |

---

## 4. 必须完成的标定

### 4.1 手机相机—Wi-Fi 天线外参

需要记录具体手机型号和 Wi-Fi 天线大致位置。初期可以根据拆机资料或设备结构估计，随后通过实验校正。

建议保存：

```yaml
device_model: "..."
front_camera_to_wifi_antenna_m: [x, y, z]
rotation_camera_to_phone: [qx, qy, qz, qw]
calibration_method: "..."
estimated_sigma_m: 0.01
```

如果天线偏移只有数厘米，它对标量距离的影响可能小于人脸—胸腔换算误差，但对相位敏感的射线追踪仍不应完全忽略。

### 4.2 人脸—胸腔参考点标定

建议对每位实验人员采集若干静态姿态：

```text
手机—胸腔距离：25、35、45、55、65 cm
手机高度：胸前、略高、略低
头部姿态：正视、低头、左右转头
手持方式：单手、双手、稳定器
```

同步使用侧拍标尺、深度相机或动作捕捉作为参考，拟合：

- 固定三维偏移；
- 个体线性距离模型；
- 带头部姿态特征的回归模型。

如果个体间差异很大，应保存个人参数；如果差异较小，可以建立总体先验并将个体差异并入测量协方差。

### 4.3 时间标定

需要区分：

- `t_depth`：深度或人脸锚点时间戳；
- `t_slam`：手机位姿时间戳；
- `t_csi`：监听网卡的 CSI 时间戳。

ARKit 内部的人脸锚点与世界跟踪共享会话时间基准，便于对齐。但 CSI 位于另一台主机或网卡时，仍需估计：

```math
t_{phone} = a t_{csi} + b
```

其中 `b` 是时钟偏移，`a` 是长期漂移比例。短实验可先只估计 `b`，10–30 分钟采集应同时评估 `a`。

---

## 5. 可能使用的算法

本节在前述思考和实现边界基础上，按从简单到复杂的顺序给出候选算法。

### 5.1 深度 ROI 的稳健统计

适用于原始深度图路线。

候选方法：

- 中位数；
- 截尾均值；
- 基于 MAD 的像素剔除；
- RANSAC 拟合局部胸腔平面；
- 深度置信度加权均值。

推荐首选“中位数 + MAD”，因为人体衣物表面并不严格是平面，RANSAC 平面模型未必带来稳定收益。

测量方差可以由 ROI 内深度离散程度、有效像素比例和人脸/人体检测置信度联合构造：

```math
\sigma_{z,t}^2
= \sigma_{min}^2
+ k_1\operatorname{MAD}_t^2
+ k_2(1-r_{valid,t})^2
+ k_3(1-c_{track,t})^2
```

其中：

- `r_valid`：有效深度像素比例；
- `c_track`：跟踪置信度；
- `\sigma_min`：传感器噪声下限。

### 5.2 物理门限与 Hampel/MAD 异常检测

在滤波前先排除明显不可能的观测：

```math
d_{min} \le z_t \le d_{max}
```

例如初始可用 `[0.20, 1.00] m`，最终范围应由标定数据决定。

再对滑动窗口使用 Hampel 判决：

```math
|z_t-\operatorname{median}(z)|
> k\cdot1.4826\operatorname{MAD}(z)
```

满足条件时不要立即把观测替换成窗口均值；更稳妥的做法是将该帧标记为异常，增大测量协方差 `R_t`，或跳过这次滤波更新。

还应加入速度/加速度门限：

```math
\left|\frac{z_t-z_{t-1}}{\Delta t}\right| < v_{max}
```

阈值必须来自自然手持标定，不能凭空固定。

### 5.3 指数滑动平均与 One Euro Filter

#### 指数滑动平均

```math
\hat d_t = \alpha z_t + (1-\alpha)\hat d_{t-1}
```

优点是实现简单，适合作为最低 baseline；缺点是固定 `\alpha` 无法同时兼顾静止时的平滑和快速动作时的低延迟。

#### One Euro Filter

One Euro Filter 根据估计速度动态调整截止频率：静止时强平滑，快速运动时降低平滑以减少延迟。它很适合交互式人体跟踪，可作为不建模状态协方差时的在线方案。

适用场景：

- 只需要实时平滑 `d_t`；
- 不要求输出严格概率意义上的协方差；
- 希望参数少、实现快。

它不适合作为最终的不确定度估计方法，因此论文主实验仍建议与卡尔曼滤波比较。

### 5.4 自适应卡尔曼滤波：推荐在线主算法

#### 标量距离状态

如果第一阶段只使用标量距离，可定义：

```math
\mathbf x_t =
\begin{bmatrix}
d_t\\
\dot d_t
\end{bmatrix}
```

采用近似常速度模型：

```math
\mathbf x_{t+1}
=
\begin{bmatrix}
1 & \Delta t\\
0 & 1
\end{bmatrix}
\mathbf x_t + \mathbf q_t
```

观测模型：

```math
z_t =
\begin{bmatrix}1&0\end{bmatrix}
\mathbf x_t + v_t
```

过程噪声可根据连续白噪声加速度模型设置：

```math
Q_t = \sigma_a^2
\begin{bmatrix}
\Delta t^4/4 & \Delta t^3/2\\
\Delta t^3/2 & \Delta t^2
\end{bmatrix}
```

关键不是使用普通固定 `R`，而是根据当前深度质量自适应设置：

```math
R_t = \sigma_{z,t}^2
```

当人脸跟踪稳定、ROI 有效像素多时减小 `R_t`；当跟踪质量低、深度空洞多或观测接近异常门限时增大 `R_t`。人脸完全丢失时只执行预测，不执行观测更新。

#### 三维相对位置状态

推荐最终使用：

```math
\mathbf x_t =
\begin{bmatrix}
\mathbf r_t\\
\dot{\mathbf r}_t
\end{bmatrix}
\in\mathbb R^6
```

三维常速度卡尔曼滤波可以直接输出 `\mathbf r_t` 的协方差，然后计算：

```math
\hat d_t = \|\hat{\mathbf r}_t\|_2
```

通过一阶误差传播得到距离方差：

```math
\sigma_{d,t}^2
\approx
\mathbf J_t P_{r,t}\mathbf J_t^T,
\qquad
\mathbf J_t = \frac{\hat{\mathbf r}_t^T}{\|\hat{\mathbf r}_t\|_2}
```

这样比先把三维测量压缩成标量再滤波保留了更多传播几何信息。

### 5.5 EKF 或 UKF：只在观测关系确实非线性时使用

如果输入已经是以米为单位的三维人脸/胸腔点，常速度模型和位置观测都是线性的，普通卡尔曼滤波已经足够，不需要为了“算法高级”而使用 EKF/UKF。

以下情况才考虑 EKF：

- 状态使用 `[d, 方位角, 俯仰角]`，观测为笛卡尔三维点；
- 需要联合估计人脸—胸腔标定参数；
- 测量模型显式依赖手机姿态四元数；
- 状态包含人体姿态和非线性几何约束。

以下情况可以考虑 UKF：

- 非线性较强且雅可比难以稳定推导；
- 状态维度仍较低；
- 经过仿真验证，EKF 的线性化误差确实显著。

如果没有上述证据，推荐顺序是：

```text
三维线性 KF > EKF > UKF
```

### 5.6 RTS smoother：推荐离线主算法

Rauch–Tung–Striebel smoother 在前向卡尔曼滤波后使用未来观测进行反向平滑。它适合生成实验分析用的高质量 `d_t` 序列：

```text
前向：Kalman filter
反向：RTS smoothing
输出：整段轨迹上的平滑 r_t、d_t 和协方差
```

优点：

- 实现成本低于完整因子图；
- 能利用未来帧修复短时抖动和掉帧；
- 与在线 KF 使用相同的运动和观测模型，便于公平比较。

缺点是非因果，不能直接用于实时输出。

### 5.7 因子图或滑窗优化：高精度扩展方案

如果后期需要同时处理：

- 人脸/胸腔三维观测；
- 手机 SLAM 位姿；
- IMU；
- 人脸—胸腔标定参数；
- 时间偏移；
- CSI 约束；

可以建立因子图：

```math
\min_{\mathbf r_{1:T},\,\psi}
\sum_t
\|\mathbf z_t^{depth}-h(\mathbf r_t,\psi)\|_{R_t^{-1}}^2
+
\sum_t
\|\mathbf r_{t+1}-f(\mathbf r_t)\|_{Q_t^{-1}}^2
+ R(\psi)
```

其中 `\psi` 可以包含外参、个体人体参数和时间偏移。

因子图适合作为后期研究增强，不建议作为第一个实现，因为它会同时引入较多待调参数，不利于先判断前置深度方案本身是否有效。

### 5.8 学习方法：有足够标定数据后再考虑

当固定偏移或线性模型不能从人脸稳定推算胸腔点时，可以训练轻量回归模型：

```math
\hat{\mathbf r}_t^{body}
= g_\eta(
\mathbf r_t^{face},
R_t^{face},
\text{face mesh},
\text{shoulder keypoints},
\text{device orientation})
```

候选模型包括：

- 岭回归或多项式回归；
- 随机森林/梯度提升树；
- 小型 MLP；
- 用于时序的 TCN 或小型 GRU。

不建议一开始使用深度神经网络，原因是当前最缺少的是带胸腔真值的标定数据，而不是模型容量。应先证明简单模型不足，再引入学习方法，并使用“按实验人员划分”的交叉验证，避免同一人的数据同时进入训练和测试。

---

## 6. 推荐的完整数据处理管线

### 6.1 在线管线

```text
1. 获取 ARFaceAnchor 或胸腔深度 ROI
2. 检查人脸 ID、跟踪状态、深度有效比例和时间戳
3. 转换到前摄像头坐标系
4. 应用相机—天线外参
5. 应用人脸—胸腔标定模型
6. 物理范围检查
7. Hampel/MAD + 创新门限检查
8. 自适应三维 Kalman Filter
9. 输出 r_t、d_t、速度、协方差和质量标志
10. 按统一时钟插值到 CSI 时间戳
11. 将 r_t 输入人体模型，将 d_t 仅作为派生记录
```

卡尔曼创新门限可以使用：

```math
\nu_t = \mathbf z_t-H\hat{\mathbf x}_{t|t-1}
```

```math
\operatorname{NIS}_t
= \nu_t^T S_t^{-1}\nu_t
```

若 NIS 超过卡方分布对应阈值，则增大 `R_t` 或跳过更新。这比只看相邻两帧差值更符合滤波器的统计模型。

### 6.2 离线管线

```text
原始观测与质量字段
  -> 重新检查时间同步
  -> 重新标定或估计个体参数
  -> 自适应 KF 前向处理
  -> RTS 后向平滑
  -> 输出离线 r_t / d_t / sigma_d
  -> 与外部侧拍或深度相机真值比较
  -> 生成可微射线追踪输入文件
```

### 6.3 推荐数据格式

建议新增：

```text
dataset/session_xxx/human_geometry.csv
```

字段至少包含：

| 字段                    | 含义                                        |
| ----------------------- | ------------------------------------------- |
| `timestamp_phone`     | 手机会话时间戳                              |
| `timestamp_unix`      | 如能可靠映射，保存统一系统时间              |
| `face_x/y/z`          | 原始人脸点，相机坐标系，m                   |
| `body_x/y/z_raw`      | 标定换算后的原始胸腔点，m                   |
| `body_x/y/z_filtered` | 在线滤波结果，m                             |
| `d_raw`               | 原始距离，m                                 |
| `d_filtered`          | 在线滤波距离，m                             |
| `sigma_d`             | 距离标准差，m                               |
| `vx/vy/vz`            | 相对速度，m/s                               |
| `face_tracking_state` | 正常、受限、丢失                            |
| `depth_valid_ratio`   | 深度有效像素比例，如可用                    |
| `is_outlier`          | 是否被判为异常                              |
| `source`              | `arkit_face_anchor`、`truedepth_roi` 等 |
| `person_id`           | 匿名实验人员编号                            |
| `calibration_id`      | 使用的标定参数版本                          |

不要只保存滤波后的 `d_t`；原始观测和质量字段是后续更换算法、复现实验和分析失败原因的必要条件。

---

## 7. 如何把实时 `d_t` 用到可微射线追踪中

### 7.1 直接条件输入：首选 baseline

将滤波后的人体相对位置作为已观测输入：

```math
\hat s_t = F_\theta(
\operatorname{loc}_t,
\mathbf r_t^{body-phone})
```

只优化环境参数 `\theta`：

```math
\min_\theta
\sum_t
L_{CSI}\left(
s_t,
F_\theta(\operatorname{loc}_t,\hat{\mathbf r}_t)
\right)
```

该方法最适合验证“实时人体几何是否能降低 `\theta` 的错误拟合”。

### 7.2 按观测不确定度做边缘化或域随机化

如果 `\hat{\mathbf r}_t` 的不确定度不可忽略，可从：

```math
\mathbf r_t^{(k)}
\sim \mathcal N(\hat{\mathbf r}_t,P_t)
```

采样若干人体位置，并使用期望损失：

```math
L_t
\approx \frac{1}{K}
\sum_{k=1}^{K}
L_{CSI}\left(
s_t,
F_\theta(\operatorname{loc}_t,\mathbf r_t^{(k)})
\right)
```

这比把有误差的 `d_t` 当作精确真值更稳健，也能把前置深度传感器的不确定度传递到环境参数优化中。

### 7.3 视觉观测约束下的联合优化

如果射线追踪支持对人体位置求梯度，可以在视觉结果附近微调 `\mathbf r_t`：

```math
L =
\sum_t L_{CSI}(s_t,F_\theta(\operatorname{loc}_t,\mathbf r_t))
+ \lambda_v
\sum_t
\|\mathbf r_t-\hat{\mathbf r}_t^{depth}\|_{P_t^{-1}}^2
+ \lambda_s
\sum_t\|\mathbf r_t-\mathbf r_{t-1}\|^2
+ \lambda_\theta R(\theta)
```

这里视觉项必须保留，防止 CSI 把人体位置拉向一个能够降低训练残差但不符合真实几何的位置。

该联合优化应作为增强组，而不是第一 baseline。建议至少比较：

| 方法       | 人体几何处理           |
| ---------- | ---------------------- |
| BASE       | 固定 `d_0`           |
| DEPTH-RAW  | 原始前摄观测           |
| DEPTH-KF   | 自适应 KF 输出         |
| DEPTH-RTS  | 离线 RTS 输出          |
| DEPTH-MARG | 根据协方差采样边缘化   |
| JOINT      | 深度先验约束下联合优化 |

---

## 8. 推荐实施顺序

### 阶段 A：API 和数据可用性验证

- [ ] 确认手机具体型号和 TrueDepth 能力；
- [ ] 检查 `supportsUserFaceTracking`；
- [ ] 跑通后摄世界跟踪 + 前摄人脸锚点；
- [ ] 连续保存 10 分钟人脸相对手机三维位置；
- [ ] 记录帧率、丢失率、发热和电量；
- [ ] 验证是否确实需要原始前置深度图。

### 阶段 B：静态距离标定

- [ ] 设置 25、35、45、55、65 cm 等已知距离；
- [ ] 比较人脸距离、换算后的胸腔距离和外部参考真值；
- [ ] 标定相机—天线外参；
- [ ] 拟合固定偏移和个体线性模型；
- [ ] 计算 bias、MAE、RMSE 和 95% 误差。

### 阶段 C：动态算法比较

- [ ] 静止手持；
- [ ] 原地自然摆动；
- [ ] 直线慢走；
- [ ] 转弯和改变手持高度；
- [ ] 低头、转头和短时遮挡；
- [ ] 比较 raw、EMA、One Euro、KF、RTS；
- [ ] 记录延迟、抖动、掉帧恢复和动态误差。

### 阶段 D：CSI 与射线追踪闭环

- [ ] 将 `\mathbf r_t` 对齐到 CSI 时间戳；
- [ ] 比较固定 `d_0` 与实时人体几何；
- [ ] 比较是否降低 CSI 测量—仿真残差；
- [ ] 比较是否降低环境参数 `\theta` 偏差；
- [ ] 在未参与优化的轨迹上验证泛化；
- [ ] 再决定是否实现联合优化或 CSI 辅助人体状态估计。

---

## 9. 建议的验收指标

以下数值是项目初期建议目标，不是传感器性能的既定结论，应在预实验后修订。

### 静态性能

- 平均绝对误差 MAE：目标小于 5 cm；
- 95% 距离误差：目标小于 10 cm；
- 静止 30 秒标准差：目标小于 2–3 cm；
- 不同已知距离下无明显系统性尺度漂移。

### 动态性能

- 自然行走时有效输出率：目标大于 95%；
- 短时丢失后能在 0.5–1 s 内恢复；
- 在线滤波不把自然的 10–20 cm 手持变化过度抹平；
- 时间对齐造成的等效距离误差小于视觉测距误差。

### 对无线优化的有效性

- 相比固定 `d_0`，测试轨迹 CSI 残差显著下降；
- 在仿真真值实验中，`E_\theta` 显著下降；
- 不同实验人员或采集轮次估计出的 `\theta` 更一致；
- DEPTH-KF/RTS 的改进不是只发生在训练轨迹上；
- 加入错误或打乱的 `d_t` 后性能退化，证明收益确实来自正确人体几何。

最后一项是重要的消融实验：可以将 `d_t` 时间序列随机错位或使用其他人的序列，检查优化结果是否恶化。

---

## 10. 推荐的最小算法组合

如果希望尽快得到可验证结果，建议不要一开始实现所有候选算法，而采用：

```text
采集：ARKit world tracking + user face tracking
几何：个体线性标定或固定三维偏移
异常检测：物理门限 + Hampel/MAD + NIS 门限
在线：三维常速度自适应 Kalman Filter
离线：RTS smoother
射线追踪：先直接条件输入，再做协方差采样边缘化
对照：raw、EMA、固定 d_0
```

该组合能够回答四个核心问题：

1. 前置深度/人脸三维跟踪能否稳定提供人体—手机几何；
2. 简单标定是否足以从人脸推算胸腔参考点；
3. 在线滤波是否能降低抖动而不损伤真实动作；
4. 实时人体几何是否能减少可微射线追踪对环境参数的错误更新。

只有当三维 KF 明显不足时，再推进 EKF/UKF；只有当简单人体标定模型明显不足且已有足够真值数据时，再推进学习模型；只有当独立深度路线通过后，再推进视觉—CSI—环境参数联合因子图。

---

## 11. 当前 WiTwin 验证边界

当前工作区已验证 WiTwin 确定性信道、LOS 路径、CIR 和 CFR。反射路径 `max_bounces > 0` 尚未在当前 WiTwin Channel 0.1.0、RayD 0.4.0 和 DrJit 1.3.1 组合下通过验证。

因此，前置深度 `d_t` 采集与滤波可以先独立实现和验证，但在论文中声称它改善了完整多径/人体反射可微射线追踪之前，仍需先打通并验证反射路径或采用经过验证的其他传播模型。

---

## 12. 官方接口参考

- Apple：在世界跟踪过程中组合用户人脸跟踪：[https://developer.apple.com/documentation/arkit/combining-user-face-tracking-and-world-tracking](https://developer.apple.com/documentation/arkit/combining-user-face-tracking-and-world-tracking)
- Apple：`ARFaceAnchor` 三维变换与人脸坐标系：[https://developer.apple.com/documentation/arkit/arfaceanchor](https://developer.apple.com/documentation/arkit/arfaceanchor)
- Apple：`ARWorldTrackingConfiguration`：[https://developer.apple.com/documentation/arkit/arworldtrackingconfiguration](https://developer.apple.com/documentation/arkit/arworldtrackingconfiguration)
- Apple：`ARFrame.capturedDepthData` 的适用范围：[https://developer.apple.com/documentation/arkit/arframe/captureddepthdata](https://developer.apple.com/documentation/arkit/arframe/captureddepthdata)
- Apple：`AVCaptureDepthDataOutput` 流式深度输出：[https://developer.apple.com/documentation/avfoundation/avcapturedepthdataoutput](https://developer.apple.com/documentation/avfoundation/avcapturedepthdataoutput)
- Apple：`AVCaptureMultiCamSession` 多摄像头并发：[https://developer.apple.com/documentation/avfoundation/avcapturemulticamsession](https://developer.apple.com/documentation/avfoundation/avcapturemulticamsession)
- Apple：同步视频与深度输出：[https://developer.apple.com/documentation/avfoundation/avcapturedataoutputsynchronizer](https://developer.apple.com/documentation/avfoundation/avcapturedataoutputsynchronizer)
- Android：CameraX `ConcurrentCamera`：[https://developer.android.com/reference/androidx/camera/core/ConcurrentCamera](https://developer.android.com/reference/androidx/camera/core/ConcurrentCamera)

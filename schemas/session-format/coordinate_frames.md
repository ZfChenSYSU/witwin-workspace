# 坐标系与变换约定

## 命名

统一使用：

```text
target_T_source
```

表示把 `source` 坐标中的齐次点变换到 `target` 坐标：

```text
p_target = target_T_source @ p_source
```

矩阵为 4 × 4、右手坐标系、平移单位为米。文件存储采用行主序展开，并在每个
具体格式中再次声明，防止语言库默认约定不同。

iOS 0.4.0 的 `ar_frames.csv` 为兼容既有数据继续使用列前缀
`world_T_rear_camera_00`…`world_T_rear_camera_33`。其规范含义就是
`arkit_world_T_rear_camera`；`metadata.capture.arkit.pose_field_prefix` 明确记录
实际列前缀。服务器 normalized manifest 可以改用规范名称，但不得改写原始 CSV。

## 基本坐标系

| 名称 | 含义 |
|---|---|
| `arkit_world` | 单次 ARKit session 的世界坐标 |
| `rear_camera` | 后置相机坐标 |
| `phone_body` | 固定在手机机身上的工程坐标 |
| `wifi_tx` | 手机有效 Wi-Fi 发射天线参考坐标 |
| `face_anchor` | ARKit 人脸锚点坐标 |
| `human_ref` | 胸腔或简化人体模型参考坐标 |
| `room` | 重建房间的米制坐标 |
| `csi_rx` | CSI 采集网卡有效接收天线参考坐标 |

## 必须标定或估计的关系

```text
arkit_world_T_rear_camera(t)
phone_body_T_rear_camera
wifi_tx_T_phone_body
arkit_world_T_face_anchor(t)
human_ref_T_face_anchor
room_T_arkit_world
room_T_csi_rx
```

组合变换前必须检查方向，不能仅根据变量名相似直接相乘。例如：

```text
room_T_wifi_tx(t)
  = room_T_arkit_world
  @ arkit_world_T_rear_camera(t)
  @ inverse(phone_body_T_rear_camera)
  @ inverse(wifi_tx_T_phone_body)
```

上式只展示命名和组合原则；最终外参定义冻结后，应由合成点和闭环误差测试验证
每个方向，不把示意公式直接当作已经标定的真值。

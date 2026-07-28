# Session Format v1

本目录是 iOS、CSI Linux 和 WSL/WiTwin 三端共享的数据契约。任何不向后兼容的
字段或二进制格式修改，都必须提升协议版本并先合入 `main`。

## 文件

- `session.schema.json`：session 元数据 JSON Schema；
- `example-session.json`：最小示例；
- `udp_probe_packet.md`：手机 UDP 探测包线格式；
- `coordinate_frames.md`：坐标系、矩阵和变换命名约定。

## 时间原则

每个数据源保存自己的原始单调时间戳，不在采集阶段伪造“统一时间”。离线阶段
通过匹配 UDP 序号或同步事件拟合：

```text
t_csi = clock_scale * t_phone + clock_offset_ns
```

映射参数、拟合残差、样本数和方法必须写入 session 元数据。壁钟 ISO 8601 时间
用于人类检索，不能替代单调时钟参与逐帧同步。

## 版本原则

- `schema_version`：元数据结构版本，例如 `1.0.0`；
- UDP `protocol_version`：线格式整数版本；
- 解析器遇到不支持的主版本必须显式失败；
- 增加可选字段可以提升次版本；
- 改变单位、字节序、字段意义或必选字段需要提升主版本。

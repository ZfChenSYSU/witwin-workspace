# 本地数据区

此目录用于三台设备交换或处理实验数据，默认不进入普通 Git。

建议布局：

```text
datasets/
├── raw/
│   └── session_YYYYMMDD_HHMMSS/
├── interim/
├── processed/
└── examples/
```

每个 session 至少保留：

- `metadata.json`；
- 设备、软件、固件和装配配置；
- 原始文件清单、字节数和 SHA-256；
- 时钟映射参数及残差；
- 坐标标定版本；
- 对应 Git 提交和子模块提交。

大文件应通过 NAS、移动硬盘或对象存储同步。只有经过脱敏、尺寸受控且用于自动
测试的小样例才放入 `examples/` 并提交 Git。

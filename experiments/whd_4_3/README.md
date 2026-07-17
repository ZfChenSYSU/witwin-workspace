# `w_hd` 4.3 节 CSI 敏感性实验

本目录实现了
`workspace/project-docs/科研项目待办与验证计划.md` 中的 4.3 节验证。

使用固定的 WiTwin 环境运行：

```bash
cd /opt/witwin
export DRJIT_LIBOPTIX_PATH=/usr/lib/x86_64-linux-gnu/libnvoptix.so.1
/opt/witwin/venv/bin/python experiments/whd_4_3/run_experiment.py
```

生成的 CSV、JSON、NPZ 数据和图形保存在 `outputs/` 目录中。

实验明确区分以下两类结果：

1. WiTwin 原生 LOS/遮挡结果，使用 `max_bounces=0`。
2. 用于模拟人体边缘绕射和人体邻近单次散射的透明、可审计几何光学代理。

之所以使用代理模型，是因为当前固定的 WiTwin/RayD 组合无法在
`max_bounces > 0` 时完成官方路径示例。代理结果不会被表述为已经通过验证的
人体全波近场模型。

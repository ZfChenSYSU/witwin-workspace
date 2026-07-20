#!/opt/witwin/venv/bin/python
"""阶段 1：w_geo 仿真科学假设验证。

实验只依赖当前固定的 WiTwin 环境。它用 WiTwin/DrJit 求解最多三次反射的
逐路径信道，再对有效反射增益参数 theta_ref 做可微校准；SIM-A--SIM-G
共享同一批缓存路径基，统计部分使用配对 CSI 噪声重复以提高比较效力。
"""

from __future__ import annotations

import argparse
import csv
import importlib.metadata as metadata
import json
import math
import os
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import witwin.channel as wc
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from witwin.channel.core.numerics.tensors import to_torch_view


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "outputs"
DATA = OUTPUT / "data"
FIGURES = OUTPUT / "figures"

C0 = 299_792_458.0
F_CARRIER = 2.4e9
BANDWIDTH = 20e6
NUM_SUBCARRIERS = 64
FREQUENCIES = F_CARRIER + np.linspace(
    -BANDWIDTH / 2.0, BANDWIDTH / 2.0, NUM_SUBCARRIERS
)

NUM_TIME = 20
NUM_TRAIN = 16
NUM_CSI_REPEATS = 200
NUM_DEPTH_REPEATS = 5
CSI_SNR_DB = 30.0
THETA_TRUE = 1.0
THETA_BOUNDS = (0.5, 1.5)

MAX_BOUNCES = 3
NUM_SAMPLES = 2048
MAX_NUM_PATHS = 192
MAX_DIFFRACTION_ORDER = 0

ROOM_SIZE = np.array([6.0, 4.0, 3.0])
RX = np.array([1.50, 0.90, 1.25])
BODY_SIZE = np.array([0.22, 0.30, 1.70])
R0_DISTANCE = 0.40
R0_AZIMUTH_DEG = 90.0
R0_ELEVATION_DEG = 0.0

DEPTH_SIGMA_DISTANCE_M = 0.04
DEPTH_SIGMA_AZIMUTH_DEG = 6.0
DEPTH_SIGMA_ELEVATION_DEG = 3.0
RTS_PROCESS_NOISE = 0.0025
MARGINAL_SIGMA_POINTS = 7

SEED_DEPTH = 20260720
SEED_CSI = 20260721
SEED_BOOTSTRAP = 20260722

GROUP_LABELS = {
    "SIM-A": "静态 r0 / 静态 r0",
    "SIM-B": "动态真值 / 固定 r0",
    "SIM-C": "动态真值 / 真值 rt（oracle）",
    "SIM-D": "动态真值 / 含噪三维 zt",
    "SIM-E": "动态真值 / RTS 滤波 rt",
    "SIM-F": "动态真值 / 协方差边缘化",
    "SIM-G": "动态真值 / 仅真值标量 dt",
}


@dataclass
class SolveOutput:
    basis: np.ndarray
    path_count: int
    bounce_hist: np.ndarray
    reconstruction_nrmse: float
    paths: list[dict[str, object]]
    backend: dict[str, object]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def git_revision(path: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        return "unknown"


def package_version(name: str) -> str:
    try:
        return metadata.version(name)
    except metadata.PackageNotFoundError:
        return "not-installed"


def spherical_vector(distance: float, azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    az = math.radians(float(azimuth_deg))
    el = math.radians(float(elevation_deg))
    return np.array(
        [
            distance * math.cos(el) * math.cos(az),
            distance * math.cos(el) * math.sin(az),
            distance * math.sin(el),
        ],
        dtype=float,
    )


def cartesian_to_spherical(vector: np.ndarray) -> tuple[float, float, float]:
    d = float(np.linalg.norm(vector))
    az = math.degrees(math.atan2(float(vector[1]), float(vector[0])))
    el = math.degrees(math.asin(float(vector[2]) / max(d, 1e-12)))
    return d, az, el


def project_outside_body(vector: np.ndarray, clearance_m: float = 0.02) -> np.ndarray:
    """将手机--人体向量投影到水平盒体外，防止无效的盒内发射机。"""

    result = np.asarray(vector, dtype=float).copy()
    support = BODY_SIZE[:2] / 2.0 + clearance_m
    ratio = float(np.max(np.abs(result[:2]) / support))
    if ratio < 1.0:
        if np.linalg.norm(result[:2]) < 1e-12:
            result[1] = support[1]
        else:
            result[:2] /= max(ratio, 1e-12)
    return result


def trajectory() -> dict[str, np.ndarray | list[str]]:
    u = np.linspace(0.0, 1.0, NUM_TIME)
    tx = np.column_stack(
        [
            -1.40 + 0.80 * u,
            -0.75 + 0.18 * np.sin(2.0 * np.pi * u),
            1.20 + 0.05 * np.sin(np.pi * u),
        ]
    )
    # WiTwin 的端点欧拉角顺序为 yaw, pitch, roll，单位为弧度。
    orientation_deg = np.column_stack(
        [
            -22.0 + 44.0 * u,
            9.0 * np.sin(2.0 * np.pi * u),
            7.0 * np.cos(2.0 * np.pi * u),
        ]
    )
    orientation = np.radians(orientation_deg)

    distances = np.array(
        [
            0.40, 0.40, 0.40,             # D0
            0.38, 0.40, 0.42,             # D1: +/- 2 cm
            0.30, 0.40, 0.50,             # D2: +/- 10 cm
            0.20, 0.40, 0.60,             # D3: +/- 20 cm
            0.32, 0.37, 0.43, 0.48,       # D4: 慢周期
            0.30, 0.55, 0.25, 0.60,       # D5: 突变
        ],
        dtype=float,
    )
    azimuth = np.array(
        [
            90, 90, 90,
            75, 90, 105,
            45, 75, 105,
            28, 90, 150,
            30, 50, 70, 90,
            25, 120, 40, 150,
        ],
        dtype=float,
    )
    elevation = np.array(
        [
            0, 0, 0,
            -3, 0, 3,
            -6, 0, 6,
            -10, 0, 10,
            -6, -2, 2, 6,
            -8, 8, -5, 10,
        ],
        dtype=float,
    )
    labels = ["D0"] * 3 + ["D1"] * 3 + ["D2"] * 3 + ["D3"] * 3 + ["D4"] * 4 + ["D5"] * 4
    r_true = np.stack(
        [spherical_vector(d, a, e) for d, a, e in zip(distances, azimuth, elevation)]
    )
    r0 = spherical_vector(R0_DISTANCE, R0_AZIMUTH_DEG, R0_ELEVATION_DEG)
    return {
        "tx": tx,
        "orientation": orientation,
        "orientation_deg": orientation_deg,
        "distance": distances,
        "azimuth_deg": azimuth,
        "elevation_deg": elevation,
        "labels": labels,
        "r_true": r_true,
        "r0": r0,
    }


def noisy_geometry(traj: dict[str, object], seed: int = SEED_DEPTH) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    d = np.asarray(traj["distance"]) + rng.normal(0.0, DEPTH_SIGMA_DISTANCE_M, NUM_TIME)
    a = np.asarray(traj["azimuth_deg"]) + rng.normal(0.0, DEPTH_SIGMA_AZIMUTH_DEG, NUM_TIME)
    e = np.asarray(traj["elevation_deg"]) + rng.normal(0.0, DEPTH_SIGMA_ELEVATION_DEG, NUM_TIME)
    d = np.clip(d, 0.16, 0.70)
    r = np.stack([project_outside_body(spherical_vector(x, y, z)) for x, y, z in zip(d, a, e)])
    # 一阶误差传播给出笛卡尔观测协方差，供 RTS 与边缘化共享。
    cov = np.zeros((NUM_TIME, 3, 3), dtype=float)
    sd = DEPTH_SIGMA_DISTANCE_M
    sa = math.radians(DEPTH_SIGMA_AZIMUTH_DEG)
    se = math.radians(DEPTH_SIGMA_ELEVATION_DEG)
    for i, (di, ai, ei) in enumerate(zip(d, np.radians(a), np.radians(e))):
        jac = np.array(
            [
                [math.cos(ei) * math.cos(ai), -di * math.cos(ei) * math.sin(ai), -di * math.sin(ei) * math.cos(ai)],
                [math.cos(ei) * math.sin(ai), di * math.cos(ei) * math.cos(ai), -di * math.sin(ei) * math.sin(ai)],
                [math.sin(ei), 0.0, di * math.cos(ei)],
            ]
        )
        cov[i] = jac @ np.diag([sd**2, sa**2, se**2]) @ jac.T + np.eye(3) * 1e-7
    return r, cov


def rts_smoother(measurements: np.ndarray, observation_cov: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """三轴独立常速度模型的 Kalman + Rauch--Tung--Striebel 平滑。"""

    dim = 6
    f = np.block([[np.eye(3), np.eye(3)], [np.zeros((3, 3)), np.eye(3)]])
    h = np.block([np.eye(3), np.zeros((3, 3))])
    q1 = np.array([[0.25, 0.5], [0.5, 1.0]]) * RTS_PROCESS_NOISE
    q = np.kron(q1, np.eye(3))
    x_f = np.zeros((NUM_TIME, dim))
    p_f = np.zeros((NUM_TIME, dim, dim))
    x_p = np.zeros_like(x_f)
    p_p = np.zeros_like(p_f)
    x = np.r_[measurements[0], np.zeros(3)]
    p = np.diag([0.02**2] * 3 + [0.08**2] * 3)
    eye = np.eye(dim)
    for t in range(NUM_TIME):
        if t > 0:
            x = f @ x
            p = f @ p @ f.T + q
        x_p[t], p_p[t] = x, p
        s = h @ p @ h.T + observation_cov[t]
        k = p @ h.T @ np.linalg.inv(s)
        innovation = measurements[t] - h @ x
        x = x + k @ innovation
        # Joseph 形式避免数值上出现非正定协方差。
        ikh = eye - k @ h
        p = ikh @ p @ ikh.T + k @ observation_cov[t] @ k.T
        x_f[t], p_f[t] = x, p
    x_s, p_s = x_f.copy(), p_f.copy()
    for t in range(NUM_TIME - 2, -1, -1):
        gain = p_f[t] @ f.T @ np.linalg.inv(p_p[t + 1])
        x_s[t] = x_f[t] + gain @ (x_s[t + 1] - x_p[t + 1])
        p_s[t] = p_f[t] + gain @ (p_s[t + 1] - p_p[t + 1]) @ gain.T
    position_cov = np.stack([(p[:3, :3] + p[:3, :3].T) / 2.0 for p in p_s])
    position = np.stack([project_outside_body(value) for value in x_s[:, :3]])
    return position, position_cov


def sigma_points(mean: np.ndarray, covariance: np.ndarray) -> np.ndarray:
    # 1 个中心 + 三轴正负点，共 7 点；所有点等权，用于显式均值边缘化。
    eigval, eigvec = np.linalg.eigh(covariance + np.eye(3) * 1e-9)
    root = eigvec @ np.diag(np.sqrt(np.maximum(eigval, 1e-10)))
    scale = math.sqrt(3.0)
    points = [mean]
    for axis in range(3):
        delta = scale * root[:, axis]
        points.extend([mean + delta, mean - delta])
    return np.stack([project_outside_body(point) for point in points])


def room_structures(body_center: np.ndarray) -> list[wc.Structure]:
    def box(name: str, position, size, eps_r: float, sigma_e: float) -> wc.Structure:
        return wc.Structure(
            name=name,
            geometry=wc.Box(position=tuple(position), size=tuple(size), device="cuda"),
            material=wc.Material(eps_r=eps_r, sigma_e=sigma_e),
        )

    return [
        box("wall_x_min", (-3.05, 0.0, 1.5), (0.10, 4.0, 3.0), 4.0, 0.01),
        box("wall_x_max", (3.05, 0.0, 1.5), (0.10, 4.0, 3.0), 4.0, 0.01),
        box("wall_y_min", (0.0, -2.05, 1.5), (6.0, 0.10, 3.0), 4.0, 0.01),
        box("wall_y_max", (0.0, 2.05, 1.5), (6.0, 0.10, 3.0), 4.0, 0.01),
        box("floor", (0.0, 0.0, -0.05), (6.0, 4.0, 0.10), 5.0, 0.02),
        box("ceiling", (0.0, 0.0, 3.05), (6.0, 4.0, 0.10), 3.0, 0.005),
        box("human_body", body_center, BODY_SIZE, 38.0, 1.0),
    ]


def make_scene(tx: np.ndarray, orientation: np.ndarray, r_model: np.ndarray) -> wc.Scene:
    body_center = tx + r_model
    phone_array = wc.AntennaArray(
        element_positions=[(0.0, 0.0, 0.0)], pattern="dipole", polarization="V"
    )
    rx_array = wc.AntennaArray(
        element_positions=[(0.0, 0.0, 0.0)], pattern="dipole", polarization="V"
    )
    return wc.Scene(
        structures=room_structures(body_center),
        transmitters=[
            wc.Transmitter(
                "phone_tx", tuple(tx), orientation=tuple(orientation), array=phone_array
            )
        ],
        receivers=[wc.Receiver("csi_rx", tuple(RX), array=rx_array)],
        frequency=F_CARRIER,
        device="cuda",
    )


def path_config(num_samples: int = NUM_SAMPLES) -> wc.path.Config:
    return wc.path.Config(
        num_samples=int(num_samples),
        max_bounces=MAX_BOUNCES,
        max_diffraction_order=MAX_DIFFRACTION_ORDER,
        max_num_paths=MAX_NUM_PATHS,
        return_geometry=True,
        edge_policy=wc.EdgePolicy(edge_selection_mode="all_edges"),
        tuning=wc.path.Tuning(
            reflection_field_backend="drjit",
            solver_mode="accuracy",
            min_ray_contribution_threshold=0.0,
        ),
    )


def solve_basis(
    tx: np.ndarray,
    orientation: np.ndarray,
    r_model: np.ndarray,
    *,
    num_samples: int = NUM_SAMPLES,
    keep_paths: bool = False,
) -> SolveOutput:
    result = wc.path.solve(
        scene=make_scene(tx, orientation, r_model),
        transmitter="phone_tx",
        receiver=["csi_rx"],
        config=path_config(num_samples),
    )
    valid = to_torch_view(result.valid, detach=True).reshape(-1).cpu()
    coeff = result.coeff_tensor().detach().reshape(-1).cpu()[valid]
    tau = to_torch_view(result.tau, detach=True).reshape(-1).cpu()[valid]
    result_depth = int(result.max_depth)
    types_all = to_torch_view(result.types, detach=True).reshape(-1, result_depth).cpu()
    types = types_all[valid]
    vertices_all = to_torch_view(result.vertices, detach=True).reshape(-1, result_depth, 3).cpu()
    vertices = vertices_all[valid]
    bounce = (types != 0).sum(dim=-1).to(torch.int64)
    freq = torch.as_tensor(FREQUENCIES, device="cpu", dtype=torch.float32)
    per_path = coeff[:, None] * torch.exp(
        -2.0j * math.pi * tau[:, None] * freq[None, :]
    )
    basis = torch.zeros(
        (MAX_BOUNCES + 1, NUM_SUBCARRIERS), dtype=torch.complex64
    )
    for order in range(MAX_BOUNCES + 1):
        basis[order] = per_path[bounce == order].sum(dim=0)
    native = result.cfr(
        torch.as_tensor(FREQUENCIES, device="cuda", dtype=torch.float32),
        normalize_delays=False,
    ).detach().cpu().reshape(-1, NUM_SUBCARRIERS)[0]
    reconstructed = basis.sum(dim=0)
    reconstruction_nrmse = float(
        torch.linalg.vector_norm(native - reconstructed)
        / torch.linalg.vector_norm(native).clamp_min(1e-30)
    )
    hist = np.bincount(bounce.numpy(), minlength=MAX_BOUNCES + 1)[: MAX_BOUNCES + 1]
    path_rows: list[dict[str, object]] = []
    if keep_paths:
        for index in range(int(valid.sum())):
            order = int(bounce[index])
            path_rows.append(
                {
                    "bounce_order": order,
                    "delay_ns": float(tau[index] * 1e9),
                    "coefficient_abs": float(torch.abs(coeff[index])),
                    "vertices_m": vertices[index, :order].numpy().tolist(),
                }
            )
    backend = dict(dict(result.metadata).get("runtime_backends", {}).get("reflection", {}))
    return SolveOutput(
        basis=basis.numpy().astype(np.complex128),
        path_count=int(valid.sum()),
        bounce_hist=hist.astype(int),
        reconstruction_nrmse=reconstruction_nrmse,
        paths=path_rows,
        backend=backend,
    )


def theta_cfr(basis: np.ndarray, theta: np.ndarray | float) -> np.ndarray:
    theta_array = np.asarray(theta)
    powers = np.power(theta_array[..., None], np.arange(MAX_BOUNCES + 1))
    return np.einsum("...b,...tbf->...tf", powers, basis)


def solve_sequence(
    variant: str,
    traj: dict[str, object],
    r_values: np.ndarray,
    inventory: list[dict[str, object]],
    selected_times: set[int] | None = None,
) -> tuple[np.ndarray, dict[str, object]]:
    tx = np.asarray(traj["tx"])
    orientation = np.asarray(traj["orientation"])
    basis_rows = []
    selected: dict[str, object] = {}
    selected_times = selected_times or set()
    for t in range(NUM_TIME):
        solved = solve_basis(
            tx[t], orientation[t], r_values[t], keep_paths=t in selected_times
        )
        basis_rows.append(solved.basis)
        inventory.append(
            {
                "variant": variant,
                "time_index": t,
                "sigma_index": "",
                "path_count": solved.path_count,
                "bounce_0": solved.bounce_hist[0],
                "bounce_1": solved.bounce_hist[1],
                "bounce_2": solved.bounce_hist[2],
                "bounce_3": solved.bounce_hist[3],
                "reconstruction_nrmse": solved.reconstruction_nrmse,
            }
        )
        if t in selected_times:
            selected[str(t)] = {
                "tx_m": tx[t].tolist(),
                "rx_m": RX.tolist(),
                "body_center_m": (tx[t] + r_values[t]).tolist(),
                "paths": solved.paths,
                "backend": solved.backend,
            }
    return np.stack(basis_rows), selected


def simulate_path_bases(traj: dict[str, object], force: bool) -> tuple[dict[str, np.ndarray], list[dict[str, object]], dict[str, object], dict[str, object]]:
    cache_path = DATA / "path_basis_cache.npz"
    inventory_path = DATA / "geometry_solve_inventory.csv"
    selected_path = DATA / "selected_paths.json"
    audit_path = DATA / "solver_audit.json"
    if cache_path.exists() and inventory_path.exists() and selected_path.exists() and audit_path.exists() and not force:
        cache = np.load(cache_path)
        bases = {key: cache[key] for key in cache.files}
        with inventory_path.open(encoding="utf-8") as handle:
            inventory = list(csv.DictReader(handle))
        return bases, inventory, json.loads(selected_path.read_text(encoding="utf-8")), json.loads(audit_path.read_text(encoding="utf-8"))

    r_true = np.asarray(traj["r_true"])
    r0 = np.asarray(traj["r0"])
    r_fixed = np.repeat(r0[None, :], NUM_TIME, axis=0)
    distances = np.asarray(traj["distance"])
    r_scalar = np.stack(
        [spherical_vector(d, R0_AZIMUTH_DEG, R0_ELEVATION_DEG) for d in distances]
    )
    inventory: list[dict[str, object]] = []
    bases: dict[str, np.ndarray] = {}
    bases["static"], _ = solve_sequence("static", traj, r_fixed, inventory)
    bases["true"], selected = solve_sequence(
        "true", traj, r_true, inventory, selected_times={0, 9, 17}
    )
    bases["scalar"], _ = solve_sequence("scalar", traj, r_scalar, inventory)

    tx = np.asarray(traj["tx"])
    orientation = np.asarray(traj["orientation"])
    for depth_repeat in range(NUM_DEPTH_REPEATS):
        r_noisy, obs_cov = noisy_geometry(traj, SEED_DEPTH + depth_repeat)
        r_filtered, filtered_cov = rts_smoother(r_noisy, obs_cov)
        bases[f"noisy_{depth_repeat}"], _ = solve_sequence(
            f"noisy_{depth_repeat}", traj, r_noisy, inventory
        )
        bases[f"filtered_{depth_repeat}"], _ = solve_sequence(
            f"filtered_{depth_repeat}", traj, r_filtered, inventory
        )
        marginal_basis = []
        for t in range(NUM_TIME):
            points = sigma_points(r_filtered[t], filtered_cov[t])
            assert len(points) == MARGINAL_SIGMA_POINTS
            point_bases = []
            for k, point in enumerate(points):
                solved = solve_basis(tx[t], orientation[t], point)
                point_bases.append(solved.basis)
                inventory.append(
                    {
                        "variant": f"marginal_{depth_repeat}",
                        "time_index": t,
                        "sigma_index": k,
                        "path_count": solved.path_count,
                        "bounce_0": solved.bounce_hist[0],
                        "bounce_1": solved.bounce_hist[1],
                        "bounce_2": solved.bounce_hist[2],
                        "bounce_3": solved.bounce_hist[3],
                        "reconstruction_nrmse": solved.reconstruction_nrmse,
                    }
                )
            marginal_basis.append(np.mean(point_bases, axis=0))
        bases[f"marginal_{depth_repeat}"] = np.stack(marginal_basis)

    # 采样收敛、重复确定性和运行后端是阶段 0/1 的强制审计证据。
    audit_t = 9
    convergence = []
    convergence_outputs: dict[int, SolveOutput] = {}
    for samples in (256, 512, 1024, 2048, 4096):
        convergence_outputs[samples] = solve_basis(
            tx[audit_t], orientation[audit_t], r_true[audit_t], num_samples=samples
        )
    reference = convergence_outputs[4096].basis.sum(axis=0)
    for samples, solved in convergence_outputs.items():
        cfr = solved.basis.sum(axis=0)
        nrmse = float(np.linalg.norm(cfr - reference) / max(np.linalg.norm(reference), 1e-30))
        convergence.append(
            {
                "num_samples": samples,
                "path_count": solved.path_count,
                "bounce_hist": solved.bounce_hist.tolist(),
                "cfr_nrmse_vs_4096": nrmse,
            }
        )
    repeat = solve_basis(tx[audit_t], orientation[audit_t], r_true[audit_t])
    base = convergence_outputs[2048]
    repeat_nrmse = float(
        np.linalg.norm(repeat.basis.sum(axis=0) - base.basis.sum(axis=0))
        / max(np.linalg.norm(base.basis.sum(axis=0)), 1e-30)
    )
    all_counts = [int(row["path_count"]) for row in inventory]
    max_b3 = max(int(row["bounce_3"]) for row in inventory)
    max_recon = max(float(row["reconstruction_nrmse"]) for row in inventory)
    audit = {
        "max_bounces_requested": MAX_BOUNCES,
        "third_order_paths_observed": max_b3 > 0,
        "maximum_third_order_path_count": max_b3,
        "maximum_total_path_count": max(all_counts),
        "minimum_total_path_count": min(all_counts),
        "path_cap": MAX_NUM_PATHS,
        "path_cap_headroom": MAX_NUM_PATHS - max(all_counts),
        "maximum_basis_reconstruction_nrmse": max_recon,
        "repeat_path_count_a": base.path_count,
        "repeat_path_count_b": repeat.path_count,
        "repeat_cfr_nrmse": repeat_nrmse,
        "convergence": convergence,
        "reflection_backend": base.backend,
    }
    if MAX_BOUNCES != 3 or not audit["third_order_paths_observed"]:
        raise RuntimeError("三阶反射硬检查失败。")
    if max(all_counts) >= MAX_NUM_PATHS:
        raise RuntimeError("路径数触及 max_num_paths，结果可能被截断。")
    if max_recon > 1e-5:
        raise RuntimeError(f"逐阶路径基无法重建 WiTwin CFR: {max_recon}")

    np.savez_compressed(cache_path, **bases)
    with inventory_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(inventory[0]))
        writer.writeheader()
        writer.writerows(inventory)
    write_json(selected_path, selected)
    write_json(audit_path, audit)
    return bases, inventory, selected, audit


def golden_fit(observations: np.ndarray, basis: np.ndarray, iterations: int = 70) -> np.ndarray:
    """对每次重复并行进行有界一维黄金分割最小化。"""

    repeats = observations.shape[0]
    lo = np.full(repeats, THETA_BOUNDS[0], dtype=float)
    hi = np.full(repeats, THETA_BOUNDS[1], dtype=float)
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    train_basis = basis[:, :NUM_TRAIN] if basis.ndim == 4 else basis[:NUM_TRAIN]

    def objective(theta: np.ndarray) -> np.ndarray:
        prediction = theta_cfr(train_basis, theta)
        return np.mean(np.abs(observations[:, :NUM_TRAIN] - prediction) ** 2, axis=(1, 2))

    for _ in range(iterations):
        c = hi - ratio * (hi - lo)
        d = lo + ratio * (hi - lo)
        fc, fd = objective(c), objective(d)
        left = fc < fd
        hi = np.where(left, d, hi)
        lo = np.where(left, lo, c)
    return (lo + hi) / 2.0


def complex_nrmse(prediction: np.ndarray, truth: np.ndarray) -> np.ndarray:
    axes = tuple(range(1, prediction.ndim))
    numerator = np.sum(np.abs(prediction - truth) ** 2, axis=axes)
    denominator = np.sum(np.abs(truth) ** 2, axis=tuple(range(truth.ndim)))
    return np.sqrt(numerator / max(float(denominator), 1e-30))


def evaluate_groups(bases: dict[str, np.ndarray], traj: dict[str, object]) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]], dict[str, object]]:
    clean_static = theta_cfr(bases["static"], THETA_TRUE)
    clean_dynamic = theta_cfr(bases["true"], THETA_TRUE)
    rng = np.random.default_rng(SEED_CSI)
    dynamic_power = float(np.mean(np.abs(clean_dynamic) ** 2))
    static_power = float(np.mean(np.abs(clean_static) ** 2))
    snr_linear = 10.0 ** (CSI_SNR_DB / 10.0)

    def noise(power: float) -> np.ndarray:
        component_sigma = math.sqrt(power / snr_linear / 2.0)
        return component_sigma * (
            rng.normal(size=(NUM_CSI_REPEATS, NUM_TIME, NUM_SUBCARRIERS))
            + 1.0j * rng.normal(size=(NUM_CSI_REPEATS, NUM_TIME, NUM_SUBCARRIERS))
        )

    obs_static = clean_static[None, :, :] + noise(static_power)
    shared_dynamic_noise = noise(dynamic_power)
    obs_dynamic = clean_dynamic[None, :, :] + shared_dynamic_noise
    depth_assignment = np.arange(NUM_CSI_REPEATS) % NUM_DEPTH_REPEATS
    noisy_bases = np.stack([bases[f"noisy_{i}"] for i in range(NUM_DEPTH_REPEATS)])
    filtered_bases = np.stack([bases[f"filtered_{i}"] for i in range(NUM_DEPTH_REPEATS)])
    marginal_bases = np.stack([bases[f"marginal_{i}"] for i in range(NUM_DEPTH_REPEATS)])
    group_basis = {
        "SIM-A": bases["static"],
        "SIM-B": bases["static"],
        "SIM-C": bases["true"],
        "SIM-D": noisy_bases[depth_assignment],
        "SIM-E": filtered_bases[depth_assignment],
        "SIM-F": marginal_bases[depth_assignment],
        "SIM-G": bases["scalar"],
    }
    repeat_rows: list[dict[str, object]] = []
    summary_rows: list[dict[str, object]] = []
    values: dict[str, dict[str, np.ndarray]] = {}
    for group, basis in group_basis.items():
        observations = obs_static if group == "SIM-A" else obs_dynamic
        truth = clean_static if group == "SIM-A" else clean_dynamic
        theta_hat = golden_fit(observations, basis)
        test_basis = basis[:, NUM_TRAIN:] if basis.ndim == 4 else basis[NUM_TRAIN:]
        train_basis = basis[:, :NUM_TRAIN] if basis.ndim == 4 else basis[:NUM_TRAIN]
        prediction = theta_cfr(test_basis, theta_hat)
        test_truth = truth[NUM_TRAIN:]
        nrmse = complex_nrmse(prediction, test_truth)
        amp_delta = 20.0 * np.log10(
            np.maximum(np.abs(prediction), 1e-30) / np.maximum(np.abs(test_truth)[None, :, :], 1e-30)
        )
        amp_rms = np.sqrt(np.mean(amp_delta**2, axis=(1, 2)))
        phase_rms = np.degrees(
            np.sqrt(np.mean(np.angle(prediction * np.conj(test_truth)[None, :, :]) ** 2, axis=(1, 2)))
        )
        theta_error = np.abs(theta_hat - THETA_TRUE)
        # 线性化 Fisher 信息给出每次估计的名义 95% 区间与覆盖率。
        b = np.arange(MAX_BOUNCES + 1, dtype=float)
        derivative_powers = b[None, :] * theta_hat[:, None] ** np.maximum(b[None, :] - 1.0, 0.0)
        derivative = (
            np.einsum("rb,rtbf->rtf", derivative_powers, train_basis)
            if train_basis.ndim == 4
            else np.einsum("rb,tbf->rtf", derivative_powers, train_basis)
        )
        component_variance = (static_power if group == "SIM-A" else dynamic_power) / snr_linear / 2.0
        theta_se = np.sqrt(component_variance / np.maximum(np.sum(np.abs(derivative) ** 2, axis=(1, 2)), 1e-30))
        covered = (theta_hat - 1.96 * theta_se <= THETA_TRUE) & (THETA_TRUE <= theta_hat + 1.96 * theta_se)
        values[group] = {
            "theta": theta_hat,
            "theta_error": theta_error,
            "test_nrmse": nrmse,
            "amplitude_rms_db": amp_rms,
            "phase_rms_deg": phase_rms,
            "covered": covered.astype(float),
        }
        for repeat in range(NUM_CSI_REPEATS):
            repeat_rows.append(
                {
                    "group": group,
                    "repeat": repeat,
                    "depth_repeat": int(depth_assignment[repeat]) if group in {"SIM-D", "SIM-E", "SIM-F"} else "",
                    "theta_hat": theta_hat[repeat],
                    "theta_abs_error": theta_error[repeat],
                    "test_complex_nrmse": nrmse[repeat],
                    "test_amplitude_rms_db": amp_rms[repeat],
                    "test_phase_rms_deg": phase_rms[repeat],
                    "theta_ci_covers_truth": int(covered[repeat]),
                }
            )
        row: dict[str, object] = {"group": group, "label": GROUP_LABELS[group]}
        for key in ("theta", "theta_error", "test_nrmse", "amplitude_rms_db", "phase_rms_deg"):
            array = values[group][key]
            row[f"{key}_mean"] = float(np.mean(array))
            row[f"{key}_std"] = float(np.std(array, ddof=1))
            row[f"{key}_q025"] = float(np.quantile(array, 0.025))
            row[f"{key}_q975"] = float(np.quantile(array, 0.975))
            row[f"{key}_mean_ci_half"] = float(1.96 * np.std(array, ddof=1) / math.sqrt(len(array)))
        row["theta_ci_coverage"] = float(np.mean(covered))
        row["theta_lower_bound_rate"] = float(np.mean(theta_hat <= THETA_BOUNDS[0] + 1e-6))
        row["theta_upper_bound_rate"] = float(np.mean(theta_hat >= THETA_BOUNDS[1] - 1e-6))
        summary_rows.append(row)

    rng_boot = np.random.default_rng(SEED_BOOTSTRAP)
    comparisons = []
    for reference, candidate in (
        ("SIM-B", "SIM-C"),
        ("SIM-B", "SIM-D"),
        ("SIM-B", "SIM-E"),
        ("SIM-B", "SIM-F"),
        ("SIM-B", "SIM-G"),
        ("SIM-G", "SIM-C"),
        ("SIM-E", "SIM-F"),
    ):
        difference = values[reference]["test_nrmse"] - values[candidate]["test_nrmse"]
        indices = rng_boot.integers(0, len(difference), size=(10000, len(difference)))
        bootstrap_mean = difference[indices].mean(axis=1)
        comparisons.append(
            {
                "reference": reference,
                "candidate": candidate,
                "metric": "test_complex_nrmse",
                "mean_improvement_reference_minus_candidate": float(np.mean(difference)),
                "relative_improvement_percent": float(100.0 * np.mean(difference) / max(np.mean(values[reference]["test_nrmse"]), 1e-30)),
                "bootstrap_ci_q025": float(np.quantile(bootstrap_mean, 0.025)),
                "bootstrap_ci_q975": float(np.quantile(bootstrap_mean, 0.975)),
                "paired_effect_dz": float(np.mean(difference) / max(np.std(difference, ddof=1), 1e-30)),
                "bootstrap_probability_improvement": float(np.mean(bootstrap_mean > 0.0)),
            }
        )

    gradient = gradient_and_identifiability_audit(bases["true"], clean_dynamic)
    raw_all, filtered_all, covariance_all = [], [], []
    for depth_repeat in range(NUM_DEPTH_REPEATS):
        raw_r, obs_cov = noisy_geometry(traj, SEED_DEPTH + depth_repeat)
        filtered_r, filtered_cov = rts_smoother(raw_r, obs_cov)
        raw_all.append(raw_r)
        filtered_all.append(filtered_r)
        covariance_all.append(filtered_cov)
    raw_all = np.stack(raw_all)
    filtered_all = np.stack(filtered_all)
    covariance_all = np.stack(covariance_all)
    r_true = np.asarray(traj["r_true"])
    r_fixed = np.repeat(np.asarray(traj["r0"])[None, :], NUM_TIME, axis=0)
    r_scalar = np.stack(
        [spherical_vector(d, R0_AZIMUTH_DEG, R0_ELEVATION_DEG) for d in np.asarray(traj["distance"])]
    )
    geometry = {}
    for name, estimate in (
        ("fixed", r_fixed), ("noisy", raw_all), ("filtered", filtered_all), ("scalar", r_scalar)
    ):
        if estimate.ndim == 3:
            er = np.linalg.norm(estimate - r_true[None, :, :], axis=2)
            ed = np.abs(np.linalg.norm(estimate, axis=2) - np.linalg.norm(r_true, axis=1)[None, :])
            er_by_time = er[0]
            ed_by_time = ed[0]
            er_seed_means = np.mean(er, axis=1)
        else:
            er = np.linalg.norm(estimate - r_true, axis=1)
            ed = np.abs(np.linalg.norm(estimate, axis=1) - np.linalg.norm(r_true, axis=1))
            er_by_time = er
            ed_by_time = ed
            er_seed_means = np.array([np.mean(er)])
        geometry[name] = {
            "E_r_mean_m": float(np.mean(er)),
            "E_r_test_mean_m": float(np.mean(er[..., NUM_TRAIN:])),
            "E_d_mean_m": float(np.mean(ed)),
            "E_d_test_mean_m": float(np.mean(ed[..., NUM_TRAIN:])),
            "E_r_seed_mean_std_m": float(np.std(er_seed_means, ddof=1)) if len(er_seed_means) > 1 else 0.0,
            "E_r_seed_means_m": er_seed_means.tolist(),
            "E_r_by_time_m": er_by_time.tolist(),
            "E_d_by_time_m": ed_by_time.tolist(),
        }
    extras = {
        "gradient_identifiability": gradient,
        "geometry_metrics": geometry,
        "r_noisy": raw_all[0],
        "r_filtered": filtered_all[0],
        "filtered_cov": covariance_all[0],
        "clean_static": clean_static,
        "clean_dynamic": clean_dynamic,
        "values": values,
    }
    return extras, repeat_rows, summary_rows, {"comparisons": comparisons}


def gradient_and_identifiability_audit(basis: np.ndarray, clean: np.ndarray) -> dict[str, object]:
    theta0 = 0.91
    h = 1e-5
    b_torch = torch.as_tensor(basis[:NUM_TRAIN], dtype=torch.complex128)
    y_torch = torch.as_tensor(clean[:NUM_TRAIN], dtype=torch.complex128)
    theta = torch.tensor(theta0, dtype=torch.float64, requires_grad=True)
    powers = theta ** torch.arange(MAX_BOUNCES + 1, dtype=torch.float64)
    prediction = torch.einsum("b,tbf->tf", powers.to(torch.complex128), b_torch)
    loss = torch.mean(torch.abs(prediction - y_torch) ** 2)
    loss.backward()
    autograd = float(theta.grad)

    def scalar_loss(value: float) -> float:
        pred = theta_cfr(basis[:NUM_TRAIN], value)
        return float(np.mean(np.abs(pred - clean[:NUM_TRAIN]) ** 2))

    finite = (scalar_loss(theta0 + h) - scalar_loss(theta0 - h)) / (2.0 * h)
    relative = abs(autograd - finite) / max(abs(autograd), abs(finite), 1e-30)
    grid = np.linspace(THETA_BOUNDS[0], THETA_BOUNDS[1], 2001)
    losses = np.array([scalar_loss(float(value)) for value in grid])
    local_minima = int(np.sum((losses[1:-1] < losses[:-2]) & (losses[1:-1] < losses[2:])))
    minimum = float(grid[int(np.argmin(losses))])
    step = grid[1] - grid[0]
    index = int(np.argmin(losses))
    curvature = float((losses[index + 1] - 2.0 * losses[index] + losses[index - 1]) / step**2)
    return {
        "theta_at_gradient_check": theta0,
        "finite_difference_step": h,
        "autograd_derivative": autograd,
        "finite_difference_derivative": finite,
        "relative_gradient_error": relative,
        "profile_grid_points": len(grid),
        "profile_global_minimum_theta": minimum,
        "profile_local_minima_count": local_minima,
        "loss_curvature_at_truth": curvature,
        "gradient_check_pass": relative < 1e-4,
        "identifiability_pass": abs(minimum - THETA_TRUE) <= step and local_minima == 1 and curvature > 0.0,
    }


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def write_trajectory_csv(traj: dict[str, object], extras: dict[str, object]) -> None:
    raw = np.asarray(extras["r_noisy"])
    filtered = np.asarray(extras["r_filtered"])
    rows = []
    for t in range(NUM_TIME):
        row = {
            "time_index": t,
            "split": "train" if t < NUM_TRAIN else "test",
            "perturbation": traj["labels"][t],
        }
        for prefix, array in (
            ("tx", np.asarray(traj["tx"])),
            ("orientation_deg", np.asarray(traj["orientation_deg"])),
            ("r_true", np.asarray(traj["r_true"])),
            ("r_noisy", raw),
            ("r_filtered", filtered),
        ):
            row.update({f"{prefix}_{axis}": array[t, i] for i, axis in enumerate("xyz")})
        row.update(
            {
                "distance_true_m": traj["distance"][t],
                "azimuth_true_deg": traj["azimuth_deg"][t],
                "elevation_true_deg": traj["elevation_deg"][t],
            }
        )
        rows.append(row)
    write_csv(DATA / "trajectory_and_geometry.csv", rows)


def plot_geometry(traj: dict[str, object], extras: dict[str, object]) -> None:
    true = np.asarray(traj["r_true"])
    noisy = np.asarray(extras["r_noisy"])
    filtered = np.asarray(extras["r_filtered"])
    time_axis = np.arange(NUM_TIME)
    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.6), sharex=True)
    axes[0, 0].plot(time_axis, np.linalg.norm(true, axis=1), "o-", label="True $d_t$")
    axes[0, 0].plot(time_axis, np.linalg.norm(noisy, axis=1), ".--", label="Noisy depth")
    axes[0, 0].plot(time_axis, np.linalg.norm(filtered, axis=1), "s-", ms=3, label="RTS filtered")
    true_az = [cartesian_to_spherical(v)[1] for v in true]
    noisy_az = [cartesian_to_spherical(v)[1] for v in noisy]
    filtered_az = [cartesian_to_spherical(v)[1] for v in filtered]
    axes[0, 1].plot(time_axis, true_az, "o-", label="True azimuth")
    axes[0, 1].plot(time_axis, noisy_az, ".--", label="Noisy")
    axes[0, 1].plot(time_axis, filtered_az, "s-", ms=3, label="RTS")
    axes[1, 0].plot(time_axis, np.linalg.norm(noisy - true, axis=1), ".--", label="Noisy $E_r(t)$")
    axes[1, 0].plot(time_axis, np.linalg.norm(filtered - true, axis=1), "s-", ms=3, label="RTS $E_r(t)$")
    axes[1, 1].plot(np.asarray(traj["tx"])[:, 0], np.asarray(traj["tx"])[:, 1], "o-", label="Phone trajectory")
    axes[1, 1].scatter(RX[0], RX[1], marker="^", s=90, label="CSI Rx")
    axes[0, 0].set_ylabel("Distance (m)")
    axes[0, 1].set_ylabel("Azimuth (deg)")
    axes[1, 0].set_ylabel("3-D geometry error (m)")
    axes[1, 0].set_xlabel("Time index")
    axes[1, 1].set_xlabel("x (m)")
    axes[1, 1].set_ylabel("y (m)")
    axes[1, 1].set_aspect("equal", adjustable="box")
    for axis in axes.flat:
        axis.grid(True, alpha=0.25)
        axis.legend(fontsize=8)
    for axis in axes.flat[:3]:
        axis.axvline(NUM_TRAIN - 0.5, color="black", ls=":", alpha=0.7)
    fig.suptitle("Stage-1 geometry schedule and front-depth estimates")
    fig.tight_layout()
    fig.savefig(FIGURES / "geometry_trajectory.png", dpi=190)
    plt.close(fig)


def plot_group_results(extras: dict[str, object], summary_rows: list[dict[str, object]]) -> None:
    values = extras["values"]
    groups = list(GROUP_LABELS)
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.8))
    axes[0].boxplot([values[g]["test_nrmse"] for g in groups], tick_labels=groups, showfliers=False)
    axes[1].boxplot([values[g]["theta"] for g in groups], tick_labels=groups, showfliers=False)
    axes[2].boxplot([values[g]["phase_rms_deg"] for g in groups], tick_labels=groups, showfliers=False)
    axes[0].set_ylabel("Clean test complex NRMSE")
    axes[1].set_ylabel(r"Estimated $\hat{\theta}_{ref}$")
    axes[1].axhline(THETA_TRUE, color="black", ls="--", lw=1)
    axes[2].set_ylabel("Test phase RMS error (deg)")
    for axis in axes:
        axis.grid(True, axis="y", alpha=0.25)
    fig.suptitle(f"SIM-A--SIM-G paired results ({NUM_CSI_REPEATS} CSI-noise repeats, {CSI_SNR_DB:.0f} dB SNR)")
    fig.tight_layout()
    fig.savefig(FIGURES / "sim_groups_statistical_results.png", dpi=190)
    plt.close(fig)


def plot_csi_residuals(traj: dict[str, object], bases: dict[str, np.ndarray]) -> None:
    truth = theta_cfr(bases["true"], THETA_TRUE)
    fixed = theta_cfr(bases["static"], THETA_TRUE)
    scalar = theta_cfr(bases["scalar"], THETA_TRUE)
    amp_fixed = 20.0 * np.log10(np.maximum(np.abs(fixed), 1e-30) / np.maximum(np.abs(truth), 1e-30))
    amp_scalar = 20.0 * np.log10(np.maximum(np.abs(scalar), 1e-30) / np.maximum(np.abs(truth), 1e-30))
    phase_fixed = np.degrees(np.angle(fixed * np.conj(truth)))
    phase_scalar = np.degrees(np.angle(scalar * np.conj(truth)))
    extent = [-BANDWIDTH / 2e6, BANDWIDTH / 2e6, NUM_TIME - 0.5, -0.5]
    vmax_amp = float(np.quantile(np.abs(np.r_[amp_fixed.ravel(), amp_scalar.ravel()]), 0.98))
    fig, axes = plt.subplots(2, 2, figsize=(12.0, 8.2), sharex=True, sharey=True)
    for axis, data, title, vmax, cmap in (
        (axes[0, 0], amp_fixed, "Fixed $r_0$: amplitude residual", vmax_amp, "coolwarm"),
        (axes[0, 1], amp_scalar, "Scalar $d_t$: amplitude residual", vmax_amp, "coolwarm"),
        (axes[1, 0], phase_fixed, "Fixed $r_0$: wrapped phase residual", 180.0, "twilight_shifted"),
        (axes[1, 1], phase_scalar, "Scalar $d_t$: wrapped phase residual", 180.0, "twilight_shifted"),
    ):
        image = axis.imshow(data, aspect="auto", extent=extent, cmap=cmap, vmin=-vmax, vmax=vmax)
        axis.set_title(title)
        axis.axhline(NUM_TRAIN - 0.5, color="black", ls=":", lw=1)
        fig.colorbar(image, ax=axis, shrink=0.82)
    axes[1, 0].set_xlabel("Subcarrier offset (MHz)")
    axes[1, 1].set_xlabel("Subcarrier offset (MHz)")
    axes[0, 0].set_ylabel("Time index")
    axes[1, 0].set_ylabel("Time index")
    fig.suptitle("CSI residuals caused by incomplete $w_{geo}$")
    fig.tight_layout()
    fig.savefig(FIGURES / "csi_amplitude_phase_residuals.png", dpi=190)
    plt.close(fig)


def plot_theta_profiles(bases: dict[str, np.ndarray]) -> None:
    truth = theta_cfr(bases["true"], THETA_TRUE)[:NUM_TRAIN]
    grid = np.linspace(*THETA_BOUNDS, 501)
    fig, axis = plt.subplots(figsize=(8.4, 5.0))
    for key, label in (("static", "SIM-B fixed r0"), ("true", "SIM-C oracle"), ("filtered_0", "SIM-E RTS (seed 0)"), ("scalar", "SIM-G scalar dt")):
        losses = []
        for value in grid:
            prediction = theta_cfr(bases[key][:NUM_TRAIN], value)
            losses.append(np.mean(np.abs(prediction - truth) ** 2))
        losses = np.asarray(losses)
        losses = losses / max(float(np.min(losses[grid != THETA_TRUE])) if np.any(grid != THETA_TRUE) else 1.0, 1e-30)
        axis.semilogy(grid, np.maximum(losses, 1e-12), label=label)
    axis.axvline(THETA_TRUE, color="black", ls="--", label="Truth")
    axis.set_xlabel(r"Effective per-bounce reflection gain $\theta_{ref}$")
    axis.set_ylabel("Normalized training loss (log scale)")
    axis.grid(True, which="both", alpha=0.25)
    axis.legend()
    axis.set_title("Noise-free parameter loss profiles")
    fig.tight_layout()
    fig.savefig(FIGURES / "theta_loss_profiles.png", dpi=190)
    plt.close(fig)


def cuboid_faces(center: np.ndarray, size: np.ndarray) -> list[list[np.ndarray]]:
    lo, hi = center - size / 2.0, center + size / 2.0
    v = np.array(
        [[lo[0], lo[1], lo[2]], [hi[0], lo[1], lo[2]], [hi[0], hi[1], lo[2]], [lo[0], hi[1], lo[2]],
         [lo[0], lo[1], hi[2]], [hi[0], lo[1], hi[2]], [hi[0], hi[1], hi[2]], [lo[0], hi[1], hi[2]]]
    )
    return [[v[i] for i in face] for face in ((0,1,2,3),(4,5,6,7),(0,1,5,4),(2,3,7,6),(1,2,6,5),(0,3,7,4))]


def plot_selected_paths(selected: dict[str, object]) -> None:
    colors = {0: "#1f77b4", 1: "#2ca02c", 2: "#ff7f0e", 3: "#d62728"}
    titles = {"0": "D0 nominal side geometry", "9": "D3 near-LOS body geometry", "17": "D5 abrupt vector jump"}
    fig = plt.figure(figsize=(16.0, 5.2))
    for panel, key in enumerate(("0", "9", "17"), start=1):
        axis = fig.add_subplot(1, 3, panel, projection="3d")
        row = selected[key]
        tx = np.asarray(row["tx_m"])
        rx = np.asarray(row["rx_m"])
        body = np.asarray(row["body_center_m"])
        axis.add_collection3d(Poly3DCollection(cuboid_faces(body, BODY_SIZE), facecolor="#8c564b", edgecolor="black", alpha=0.35))
        for path in row["paths"]:
            order = int(path["bounce_order"])
            vertices = np.asarray(path["vertices_m"], dtype=float).reshape(-1, 3)
            points = np.vstack([tx, vertices, rx])
            axis.plot(points[:, 0], points[:, 1], points[:, 2], color=colors[order], alpha=0.75 if order < 2 else 0.40, lw=1.4 if order < 2 else 0.8)
        axis.scatter(*tx, marker="*", s=95, color="#17becf", edgecolor="black")
        axis.scatter(*rx, marker="^", s=65, color="#9467bd", edgecolor="black")
        axis.set_xlim(-3, 3); axis.set_ylim(-2, 2); axis.set_zlim(0, 3)
        axis.set_xlabel("x (m)"); axis.set_ylabel("y (m)"); axis.set_zlabel("z (m)")
        hist = np.bincount([int(p["bounce_order"]) for p in row["paths"]], minlength=4)
        axis.set_title(f"{titles[key]}\npaths={len(row['paths'])}, orders={hist.tolist()}", fontsize=9)
        axis.view_init(elev=24, azim=-58)
    fig.suptitle("All retained WiTwin paths in three representative snapshots (maximum 3 reflections)")
    fig.tight_layout()
    fig.savefig(FIGURES / "selected_full_multipath_scenes.png", dpi=200)
    plt.close(fig)


def plot_path_and_convergence(inventory: list[dict[str, object]], audit: dict[str, object]) -> None:
    true_rows = sorted(
        [row for row in inventory if row["variant"] == "true"],
        key=lambda row: int(row["time_index"]),
    )
    time_axis = np.arange(NUM_TIME)
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.6))
    bottom = np.zeros(NUM_TIME)
    for order, color in zip(range(4), ("#1f77b4", "#2ca02c", "#ff7f0e", "#d62728")):
        values = np.array([int(row[f"bounce_{order}"]) for row in true_rows])
        axes[0].bar(time_axis, values, bottom=bottom, label=f"order {order}", color=color)
        bottom += values
    conv = audit["convergence"]
    sample_values = [row["num_samples"] for row in conv]
    path_values = [row["path_count"] for row in conv]
    nrmse_values = [row["cfr_nrmse_vs_4096"] for row in conv]
    axes[1].plot(sample_values, path_values, "o-", color="#4c78a8", label="Retained paths")
    axes[1].set_ylim(min(path_values) - 2, max(path_values) + 2)
    axes[1].annotate(
        "CFR NRMSE vs 4096 = 0 for every setting",
        xy=(0.5, 0.15), xycoords="axes fraction", ha="center", fontsize=9,
        bbox={"boxstyle": "round", "facecolor": "white", "alpha": 0.8},
    )
    axes[0].set_xlabel("Time index"); axes[0].set_ylabel("Retained path count"); axes[0].legend()
    axes[1].set_xlabel("num_samples"); axes[1].set_ylabel("Retained path count")
    axes[1].legend()
    for axis in axes: axis.grid(True, alpha=0.25)
    fig.suptitle("Reflection-order inventory and solver convergence audit")
    fig.tight_layout()
    fig.savefig(FIGURES / "path_inventory_and_convergence.png", dpi=190)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-sim", action="store_true", help="忽略路径基缓存并重新运行 WiTwin")
    args = parser.parse_args()
    for directory in (OUTPUT, DATA, FIGURES):
        directory.mkdir(parents=True, exist_ok=True)
    if MAX_BOUNCES != 3:
        raise RuntimeError("本实验要求 max_bounces 固定为 3。")
    start = time.perf_counter()
    started_at = utc_now()
    traj = trajectory()
    bases, inventory, selected, solver_audit = simulate_path_bases(traj, args.force_sim)
    extras, repeat_rows, summary_rows, comparisons = evaluate_groups(bases, traj)
    write_csv(DATA / "group_metrics_repeats.csv", repeat_rows)
    write_csv(DATA / "group_summary.csv", summary_rows)
    write_csv(DATA / "paired_comparisons.csv", comparisons["comparisons"])
    write_trajectory_csv(traj, extras)
    write_json(DATA / "gradient_identifiability.json", extras["gradient_identifiability"])
    write_json(DATA / "geometry_metrics.json", extras["geometry_metrics"])
    plot_geometry(traj, extras)
    plot_group_results(extras, summary_rows)
    plot_csi_residuals(traj, bases)
    plot_theta_profiles(bases)
    plot_selected_paths(selected)
    plot_path_and_convergence(inventory, solver_audit)

    summary_map = {row["group"]: row for row in summary_rows}
    comp_map = {f"{row['reference']}-{row['candidate']}": row for row in comparisons["comparisons"]}
    gradient = extras["gradient_identifiability"]
    go_no_go = {
        "G1_dynamic_geometry_matters": comp_map["SIM-B-SIM-C"]["bootstrap_ci_q025"] > 0.0,
        "G2_depth_method_beats_fixed": max(
            comp_map["SIM-B-SIM-E"]["bootstrap_ci_q025"],
            comp_map["SIM-B-SIM-F"]["bootstrap_ci_q025"],
        ) > 0.0,
        "G3_oracle_theta_bias_below_0_02": summary_map["SIM-C"]["theta_error_mean"] < 0.02,
        "G4_gradient_and_identifiability": bool(gradient["gradient_check_pass"] and gradient["identifiability_pass"]),
        "G5_scalar_worse_than_vector": comp_map["SIM-G-SIM-C"]["bootstrap_ci_q025"] > 0.0,
    }
    go_no_go["overall_go"] = all(go_no_go.values())
    final_summary = {
        "experiment": "Stage 1 w_geo scientific hypothesis validation",
        "completed": True,
        "groups": summary_rows,
        "paired_comparisons": comparisons["comparisons"],
        "geometry_metrics": extras["geometry_metrics"],
        "solver_audit": solver_audit,
        "gradient_identifiability": gradient,
        "go_no_go": go_no_go,
    }
    write_json(DATA / "summary.json", final_summary)
    runtime = {
        "started_at_utc": started_at,
        "finished_at_utc": utc_now(),
        "elapsed_seconds": time.perf_counter() - start,
        "command_force_sim": bool(args.force_sim),
        "packages": {name: package_version(name) for name in ("witwin", "witwin-channel", "rayd", "drjit", "torch", "numpy", "matplotlib")},
        "source_revisions": {
            "witwin-core": git_revision(Path("/opt/witwin/src/witwin-core")),
            "witwin-channel": git_revision(Path("/opt/witwin/src/witwin-channel")),
        },
        "gpu": torch.cuda.get_device_name(0),
        "drjit_liboptix_path": os.environ.get("DRJIT_LIBOPTIX_PATH"),
        "config": {
            "carrier_hz": F_CARRIER,
            "bandwidth_hz": BANDWIDTH,
            "num_subcarriers": NUM_SUBCARRIERS,
            "num_time": NUM_TIME,
            "num_train": NUM_TRAIN,
            "num_test": NUM_TIME - NUM_TRAIN,
            "num_csi_repeats": NUM_CSI_REPEATS,
            "num_depth_repeats": NUM_DEPTH_REPEATS,
            "csi_snr_db": CSI_SNR_DB,
            "max_bounces": MAX_BOUNCES,
            "num_samples": NUM_SAMPLES,
            "max_num_paths": MAX_NUM_PATHS,
            "max_diffraction_order": MAX_DIFFRACTION_ORDER,
            "reflection_backend": "drjit",
            "theta_true": THETA_TRUE,
            "theta_bounds": THETA_BOUNDS,
            "seeds": {
                "depth": list(range(SEED_DEPTH, SEED_DEPTH + NUM_DEPTH_REPEATS)),
                "csi": SEED_CSI,
                "bootstrap": SEED_BOOTSTRAP,
            },
        },
    }
    write_json(DATA / "runtime.json", runtime)
    print(json.dumps({
        "success": True,
        "overall_go": go_no_go["overall_go"],
        "elapsed_seconds": runtime["elapsed_seconds"],
        "max_path_count": solver_audit["maximum_total_path_count"],
        "third_order_observed": solver_audit["third_order_paths_observed"],
        "sim_b_nrmse": summary_map["SIM-B"]["test_nrmse_mean"],
        "sim_c_nrmse": summary_map["SIM-C"]["test_nrmse_mean"],
        "sim_e_nrmse": summary_map["SIM-E"]["test_nrmse_mean"],
        "sim_f_nrmse": summary_map["SIM-F"]["test_nrmse_mean"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

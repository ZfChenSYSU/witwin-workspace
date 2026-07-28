#!/opt/witwin/venv/bin/python
"""长轨迹、并行 D0--D5 的 w_geo 阶段 1 增强实验。

本脚本复用已验证的 WiTwin/DrJit 三阶路径求解实现，但重新定义轨迹、
误差条件、空间留一交叉验证、统计单元和全部图表。D0--D5 在每个时刻
并行施加，避免把误差类型与时间/空间位置混杂。
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle
from mpl_toolkits.mplot3d.art3d import Poly3DCollection


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "outputs" / "data"
FIGURES = ROOT / "outputs" / "figures"
STAGE1_ROOT = ROOT.parent / "wgeo_stage1"
_STAGE1_SPEC = importlib.util.spec_from_file_location(
    "wgeo_stage1_base_run_experiment", STAGE1_ROOT / "run_experiment.py"
)
if _STAGE1_SPEC is None or _STAGE1_SPEC.loader is None:
    raise RuntimeError("cannot load the validated stage-1 solver module")
stage1 = importlib.util.module_from_spec(_STAGE1_SPEC)
sys.modules[_STAGE1_SPEC.name] = stage1
_STAGE1_SPEC.loader.exec_module(stage1)


# 固定无线与数值配置。
CACHE_VERSION = "long-parallel-d0-d5-v1"
NUM_PER_ZONE = 16
ZONE_LABELS = ["Z0-south", "Z1-east", "Z2-north", "Z3-west", "Z4-center"]
NUM_ZONES = len(ZONE_LABELS)
NUM_TIME = NUM_PER_ZONE * NUM_ZONES
NUM_GEOMETRY_SEEDS = 5
NUM_CSI_REPEATS_PER_FOLD = 100
NUM_BOOTSTRAP = 20_000
CSI_SNR_DB = 30.0
THETA_TRUE = 1.0
THETA_BOUNDS = (0.5, 1.5)
MAX_BOUNCES = 3
NUM_SAMPLES = 2048
MAX_NUM_PATHS = 192
AP = np.array([2.45, 1.55, 1.25], dtype=float)
ROOM_SIZE = np.array([6.0, 4.0, 3.0], dtype=float)
BODY_SIZE = np.array([0.22, 0.30, 1.70], dtype=float)

SEED_GEOMETRY = 20260730
SEED_CSI = 20260810
SEED_BOOTSTRAP = 20260820

CONDITIONS = ["D0", "D1", "D2", "D3", "D4", "D5"]
CONDITION_LABELS = {
    "D0": "exact 3-D geometry",
    "D1": "radial noise 2 cm",
    "D2": "radial noise 10 cm",
    "D3": "angular noise 6°/3°",
    "D4": "joint noise 4 cm/6°/3°",
    "D5": "joint noise + burst outliers",
}
CONDITION_COLORS = {
    "D0": "#4c78a8",
    "D1": "#72b7b2",
    "D2": "#f2cf5b",
    "D3": "#54a24b",
    "D4": "#f58518",
    "D5": "#e45756",
}


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def spherical_vector(distance: float, azimuth_deg: float, elevation_deg: float) -> np.ndarray:
    azimuth = math.radians(azimuth_deg)
    elevation = math.radians(elevation_deg)
    return np.array(
        [
            distance * math.cos(elevation) * math.cos(azimuth),
            distance * math.cos(elevation) * math.sin(azimuth),
            distance * math.sin(elevation),
        ],
        dtype=float,
    )


def vector_angles(vector: np.ndarray) -> tuple[float, float, float]:
    distance = float(np.linalg.norm(vector))
    azimuth = math.degrees(math.atan2(vector[1], vector[0])) % 360.0
    elevation = math.degrees(math.asin(np.clip(vector[2] / max(distance, 1e-12), -1.0, 1.0)))
    return distance, azimuth, elevation


def wrap_angle_deg(value: np.ndarray | float) -> np.ndarray:
    return (np.asarray(value) + 180.0) % 360.0 - 180.0


def make_long_trajectory() -> dict[str, np.ndarray]:
    """五个空间区块组成的 80 时刻长轨迹。"""

    u = np.linspace(0.0, 1.0, NUM_PER_ZONE)
    positions: list[np.ndarray] = []
    headings: list[np.ndarray] = []

    positions.append(
        np.column_stack(
            [
                -2.20 + 4.40 * u,
                -1.20 + 0.06 * np.sin(2.0 * np.pi * u),
                1.22 + 0.04 * np.sin(np.pi * u),
            ]
        )
    )
    headings.append(np.zeros(NUM_PER_ZONE))
    positions.append(
        np.column_stack(
            [
                2.20 + 0.06 * np.sin(2.0 * np.pi * u),
                -1.20 + 2.40 * u,
                1.25 + 0.05 * np.sin(np.pi * u),
            ]
        )
    )
    headings.append(np.full(NUM_PER_ZONE, 90.0))
    positions.append(
        np.column_stack(
            [
                2.20 - 4.40 * u,
                1.20 + 0.06 * np.sin(2.0 * np.pi * u),
                1.28 + 0.04 * np.sin(np.pi * u),
            ]
        )
    )
    headings.append(np.full(NUM_PER_ZONE, 180.0))
    positions.append(
        np.column_stack(
            [
                -2.20 + 0.06 * np.sin(2.0 * np.pi * u),
                1.20 - 2.40 * u,
                1.24 + 0.05 * np.sin(np.pi * u),
            ]
        )
    )
    headings.append(np.full(NUM_PER_ZONE, -90.0))
    positions.append(
        np.column_stack(
            [
                -1.85 + 3.70 * u,
                -0.85 + 1.70 * u + 0.10 * np.sin(2.0 * np.pi * u),
                1.18 + 0.08 * np.sin(np.pi * u),
            ]
        )
    )
    headings.append(np.full(NUM_PER_ZONE, math.degrees(math.atan2(1.70, 3.70))))

    tx = np.vstack(positions)
    heading = np.concatenate(headings)
    phase = np.linspace(0.0, 4.0 * np.pi, NUM_TIME)
    orientation_deg = np.column_stack(
        [
            heading + 14.0 * np.sin(phase),
            6.0 * np.sin(1.5 * phase),
            5.0 * np.cos(phase),
        ]
    )
    orientation = np.radians(orientation_deg)

    distance = 0.43 + 0.065 * np.sin(phase) + 0.025 * np.cos(2.5 * phase)
    azimuth = (heading + 90.0 + 24.0 * np.sin(0.75 * phase)) % 360.0
    elevation = 4.0 * np.sin(1.25 * phase)
    r_true = np.stack(
        [spherical_vector(d, a, e) for d, a, e in zip(distance, azimuth, elevation)]
    )
    zones = np.repeat(np.arange(NUM_ZONES), NUM_PER_ZONE)

    body_center = tx + r_true
    horizontal_limit = ROOM_SIZE[:2] / 2.0 - BODY_SIZE[:2] / 2.0 - 0.02
    if np.any(np.abs(body_center[:, :2]) > horizontal_limit + 1e-12):
        raise RuntimeError("true body trajectory leaves the room interior")
    if np.any(body_center[:, 2] - BODY_SIZE[2] / 2.0 < 0.02):
        raise RuntimeError("true body trajectory intersects the floor")
    if np.any(body_center[:, 2] + BODY_SIZE[2] / 2.0 > ROOM_SIZE[2] - 0.02):
        raise RuntimeError("true body trajectory intersects the ceiling")

    return {
        "tx": tx,
        "orientation": orientation,
        "orientation_deg": orientation_deg,
        "heading_deg": heading,
        "distance": distance,
        "azimuth_deg": azimuth,
        "elevation_deg": elevation,
        "r_true": r_true,
        "zone": zones,
    }


def constrain_geometry(tx: np.ndarray, vector: np.ndarray) -> np.ndarray:
    result = stage1.project_outside_body(np.asarray(vector, dtype=float))
    body = tx + result
    lower = np.array(
        [
            -ROOM_SIZE[0] / 2.0 + BODY_SIZE[0] / 2.0 + 0.02,
            -ROOM_SIZE[1] / 2.0 + BODY_SIZE[1] / 2.0 + 0.02,
            BODY_SIZE[2] / 2.0 + 0.02,
        ]
    )
    upper = np.array(
        [
            ROOM_SIZE[0] / 2.0 - BODY_SIZE[0] / 2.0 - 0.02,
            ROOM_SIZE[1] / 2.0 - BODY_SIZE[1] / 2.0 - 0.02,
            ROOM_SIZE[2] - BODY_SIZE[2] / 2.0 - 0.02,
        ]
    )
    clipped_body = np.clip(body, lower, upper)
    return stage1.project_outside_body(clipped_body - tx)


def make_geometry_conditions(traj: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """返回每个条件的数组，形状均为 [seed,time,xyz]。"""

    tx = traj["tx"]
    d_true = traj["distance"]
    a_true = traj["azimuth_deg"]
    e_true = traj["elevation_deg"]
    values = {condition: [] for condition in CONDITIONS}

    for seed_index in range(NUM_GEOMETRY_SEEDS):
        rng = np.random.default_rng(SEED_GEOMETRY + seed_index)
        z_distance = rng.normal(size=NUM_TIME)
        z_azimuth = rng.normal(size=NUM_TIME)
        z_elevation = rng.normal(size=NUM_TIME)

        specifications: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray]] = {
            "D0": (d_true.copy(), a_true.copy(), e_true.copy()),
            "D1": (d_true + 0.02 * z_distance, a_true.copy(), e_true.copy()),
            "D2": (d_true + 0.10 * z_distance, a_true.copy(), e_true.copy()),
            "D3": (d_true.copy(), a_true + 6.0 * z_azimuth, e_true + 3.0 * z_elevation),
            "D4": (
                d_true + 0.04 * z_distance,
                a_true + 6.0 * z_azimuth,
                e_true + 3.0 * z_elevation,
            ),
        }
        d5_d, d5_a, d5_e = [array.copy() for array in specifications["D4"]]
        # 每个空间区块有一个连续 2 帧异常突发，占该区块样本的 12.5%。
        for zone in range(NUM_ZONES):
            start = zone * NUM_PER_ZONE + 10
            indices = np.arange(start, start + 2)
            sign = 1.0 if (seed_index + zone) % 2 == 0 else -1.0
            d5_d[indices] += sign * 0.18
            d5_a[indices] += sign * 30.0
            d5_e[indices] += sign * 10.0
        specifications["D5"] = (d5_d, d5_a, d5_e)

        for condition, (distance, azimuth, elevation) in specifications.items():
            distance = np.clip(distance, 0.18, 0.75)
            vectors = np.stack(
                [
                    constrain_geometry(tx[t], spherical_vector(distance[t], azimuth[t], elevation[t]))
                    for t in range(NUM_TIME)
                ]
            )
            values[condition].append(vectors)

    return {condition: np.stack(rows) for condition, rows in values.items()}


def configure_solver() -> None:
    stage1.RX = AP.copy()
    stage1.ROOM_SIZE = ROOM_SIZE.copy()
    stage1.BODY_SIZE = BODY_SIZE.copy()
    stage1.NUM_TIME = NUM_TIME
    stage1.MAX_BOUNCES = MAX_BOUNCES
    stage1.NUM_SAMPLES = NUM_SAMPLES
    stage1.MAX_NUM_PATHS = MAX_NUM_PATHS
    stage1.MAX_DIFFRACTION_ORDER = 0


def selected_row(
    result: stage1.SolveOutput,
    tx: np.ndarray,
    body_center: np.ndarray,
    condition: str,
    seed_index: int,
    time_index: int,
) -> dict[str, object]:
    return {
        "condition": condition,
        "seed_index": seed_index,
        "time_index": time_index,
        "zone": ZONE_LABELS[time_index // NUM_PER_ZONE],
        "tx_m": tx.tolist(),
        "rx_m": AP.tolist(),
        "body_center_m": body_center.tolist(),
        "paths": result.paths,
    }


def run_simulation(
    traj: dict[str, np.ndarray],
    geometries: dict[str, np.ndarray],
    force: bool,
) -> tuple[dict[str, np.ndarray], list[dict[str, object]], dict[str, object], dict[str, object]]:
    cache_path = DATA / "path_basis_cache.npz"
    inventory_path = DATA / "geometry_solve_inventory.csv"
    selected_path = DATA / "selected_paths.json"
    audit_path = DATA / "solver_audit.json"

    if cache_path.exists() and not force:
        payload = np.load(cache_path, allow_pickle=False)
        version = str(payload["cache_version"].item())
        if version != CACHE_VERSION:
            raise RuntimeError(f"cache version mismatch: {version} != {CACHE_VERSION}")
        bases = {key: payload[key] for key in payload.files if key != "cache_version"}
        inventory = [dict(row) for row in read_csv(inventory_path)]
        selected = json.loads(selected_path.read_text(encoding="utf-8"))
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        return bases, inventory, selected, audit

    configure_solver()
    bases: dict[str, np.ndarray] = {}
    inventory: list[dict[str, object]] = []
    selected: dict[str, object] = {}
    total_solves = NUM_TIME * (1 + (len(CONDITIONS) - 1) * NUM_GEOMETRY_SEEDS)
    completed = 0
    started = time.perf_counter()

    true_rows = []
    selected_true_times = {8, 24, 40, 56, 72}
    for t in range(NUM_TIME):
        keep = t in selected_true_times
        result = stage1.solve_basis(
            traj["tx"][t], traj["orientation"][t], traj["r_true"][t], keep_paths=keep
        )
        true_rows.append(result.basis)
        inventory.append(
            {
                "condition": "D0",
                "seed_index": -1,
                "time_index": t,
                "zone": ZONE_LABELS[int(traj["zone"][t])],
                "path_count": result.path_count,
                **{f"bounce_{order}": int(result.bounce_hist[order]) for order in range(4)},
                "reconstruction_nrmse": result.reconstruction_nrmse,
            }
        )
        if keep:
            selected[f"D0_t{t}"] = selected_row(
                result,
                traj["tx"][t],
                traj["tx"][t] + traj["r_true"][t],
                "D0",
                -1,
                t,
            )
        completed += 1
        if completed % 40 == 0:
            print(f"[paths] {completed}/{total_solves}, elapsed={time.perf_counter()-started:.1f}s", flush=True)
    bases["D0"] = np.stack(true_rows)

    for condition in CONDITIONS[1:]:
        for seed_index in range(NUM_GEOMETRY_SEEDS):
            condition_rows = []
            for t in range(NUM_TIME):
                keep = condition == "D5" and seed_index == 0 and t == 10
                result = stage1.solve_basis(
                    traj["tx"][t],
                    traj["orientation"][t],
                    geometries[condition][seed_index, t],
                    keep_paths=keep,
                )
                condition_rows.append(result.basis)
                inventory.append(
                    {
                        "condition": condition,
                        "seed_index": seed_index,
                        "time_index": t,
                        "zone": ZONE_LABELS[int(traj["zone"][t])],
                        "path_count": result.path_count,
                        **{f"bounce_{order}": int(result.bounce_hist[order]) for order in range(4)},
                        "reconstruction_nrmse": result.reconstruction_nrmse,
                    }
                )
                if keep:
                    selected["D5_seed0_t10"] = selected_row(
                        result,
                        traj["tx"][t],
                        traj["tx"][t] + geometries[condition][seed_index, t],
                        condition,
                        seed_index,
                        t,
                    )
                completed += 1
                if completed % 40 == 0:
                    print(f"[paths] {completed}/{total_solves}, elapsed={time.perf_counter()-started:.1f}s", flush=True)
            bases[f"{condition}_seed{seed_index}"] = np.stack(condition_rows)

    # 独立的采样收敛与重复确定性审计。
    audit_t = 72
    convergence = []
    convergence_outputs: dict[int, stage1.SolveOutput] = {}
    for samples in (256, 512, 1024, 2048, 4096):
        convergence_outputs[samples] = stage1.solve_basis(
            traj["tx"][audit_t], traj["orientation"][audit_t], traj["r_true"][audit_t], num_samples=samples
        )
    reference = convergence_outputs[4096].basis.sum(axis=0)
    for samples, result in convergence_outputs.items():
        cfr = result.basis.sum(axis=0)
        convergence.append(
            {
                "num_samples": samples,
                "path_count": result.path_count,
                "bounce_hist": result.bounce_hist.tolist(),
                "cfr_nrmse_vs_4096": float(
                    np.linalg.norm(cfr - reference) / max(np.linalg.norm(reference), 1e-30)
                ),
            }
        )
    repeat = stage1.solve_basis(
        traj["tx"][audit_t], traj["orientation"][audit_t], traj["r_true"][audit_t]
    )
    base = convergence_outputs[NUM_SAMPLES]
    repeat_nrmse = float(
        np.linalg.norm(repeat.basis.sum(axis=0) - base.basis.sum(axis=0))
        / max(np.linalg.norm(base.basis.sum(axis=0)), 1e-30)
    )

    path_counts = np.array([int(row["path_count"]) for row in inventory])
    third_order = np.array([int(row["bounce_3"]) for row in inventory])
    reconstruction = np.array([float(row["reconstruction_nrmse"]) for row in inventory])
    audit = {
        "cache_version": CACHE_VERSION,
        "main_geometry_solves": total_solves,
        "extra_audit_solves": 6,
        "minimum_total_path_count": int(path_counts.min()),
        "maximum_total_path_count": int(path_counts.max()),
        "maximum_third_order_path_count": int(third_order.max()),
        "path_cap": MAX_NUM_PATHS,
        "minimum_path_cap_margin": int(MAX_NUM_PATHS - path_counts.max()),
        "maximum_basis_reconstruction_nrmse": float(reconstruction.max()),
        "repeat_path_counts": [base.path_count, repeat.path_count],
        "repeat_cfr_nrmse": repeat_nrmse,
        "convergence": convergence,
        "reflection_backend": base.backend,
        "main_and_audit_solver_elapsed_seconds": float(time.perf_counter() - started),
    }

    np.savez_compressed(cache_path, cache_version=np.array(CACHE_VERSION), **bases)
    write_csv(inventory_path, inventory)
    write_json(selected_path, selected)
    write_json(audit_path, audit)
    return bases, inventory, selected, audit


def theta_cfr(basis: np.ndarray, theta: np.ndarray | float) -> np.ndarray:
    theta_array = np.asarray(theta)
    powers = np.power(theta_array[..., None], np.arange(MAX_BOUNCES + 1))
    return np.einsum("...b,...tbf->...tf", powers, basis)


def golden_fit(observations: np.ndarray, basis: np.ndarray, train_mask: np.ndarray) -> np.ndarray:
    repeats = observations.shape[0]
    lo = np.full(repeats, THETA_BOUNDS[0], dtype=float)
    hi = np.full(repeats, THETA_BOUNDS[1], dtype=float)
    ratio = (math.sqrt(5.0) - 1.0) / 2.0
    train_basis = basis[:, train_mask]
    train_observations = observations[:, train_mask]

    def objective(theta: np.ndarray) -> np.ndarray:
        prediction = theta_cfr(train_basis, theta)
        return np.mean(np.abs(train_observations - prediction) ** 2, axis=(1, 2))

    for _ in range(70):
        c = hi - ratio * (hi - lo)
        d = lo + ratio * (hi - lo)
        fc = objective(c)
        fd = objective(d)
        choose_left = fc < fd
        hi = np.where(choose_left, d, hi)
        lo = np.where(choose_left, lo, c)
    return (lo + hi) / 2.0


def signal_metrics(prediction: np.ndarray, truth: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    numerator = np.sum(np.abs(prediction - truth[None]) ** 2, axis=(1, 2))
    denominator = float(np.sum(np.abs(truth) ** 2))
    nrmse = np.sqrt(numerator / max(denominator, 1e-30))
    amplitude_delta = 20.0 * np.log10(
        np.maximum(np.abs(prediction), 1e-30) / np.maximum(np.abs(truth)[None], 1e-30)
    )
    amplitude_rms = np.sqrt(np.mean(amplitude_delta**2, axis=(1, 2)))
    phase_delta = np.angle(prediction * np.conj(truth)[None])
    phase_rms = np.degrees(np.sqrt(np.mean(phase_delta**2, axis=(1, 2))))
    return nrmse, amplitude_rms, phase_rms


def condition_basis(bases: dict[str, np.ndarray], condition: str) -> np.ndarray:
    if condition == "D0":
        return np.repeat(bases["D0"][None], NUM_GEOMETRY_SEEDS, axis=0)
    return np.stack([bases[f"{condition}_seed{seed}"] for seed in range(NUM_GEOMETRY_SEEDS)])


def percentile_summary(values: np.ndarray, prefix: str) -> dict[str, float]:
    return {
        f"{prefix}_mean": float(np.mean(values)),
        f"{prefix}_std": float(np.std(values, ddof=1)) if values.size > 1 else 0.0,
        f"{prefix}_q025": float(np.quantile(values, 0.025)),
        f"{prefix}_q975": float(np.quantile(values, 0.975)),
    }


def bootstrap_mean_ci(values: np.ndarray, rng: np.random.Generator) -> tuple[float, float]:
    indices = rng.integers(0, len(values), size=(NUM_BOOTSTRAP, len(values)))
    means = values[indices].mean(axis=1)
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def bootstrap_pooled_nrmse_ci(
    numerators: np.ndarray,
    denominators: np.ndarray,
    rng: np.random.Generator,
) -> tuple[float, float]:
    indices = rng.integers(0, len(numerators), size=(NUM_BOOTSTRAP, len(numerators)))
    sampled_numerator = numerators[indices].sum(axis=1)
    sampled_denominator = denominators[indices].sum(axis=1)
    values = np.sqrt(sampled_numerator / np.maximum(sampled_denominator, 1e-30))
    return float(np.quantile(values, 0.025)), float(np.quantile(values, 0.975))


def evaluate(
    traj: dict[str, np.ndarray],
    geometries: dict[str, np.ndarray],
    bases: dict[str, np.ndarray],
    inventory: list[dict[str, object]],
) -> dict[str, object]:
    clean_truth = theta_cfr(bases["D0"], THETA_TRUE)
    direct_rows: list[dict[str, object]] = []
    direct_time_rows: list[dict[str, object]] = []
    geometry_rows: list[dict[str, object]] = []

    inventory_lookup = {
        (str(row["condition"]), int(row["seed_index"]), int(row["time_index"])): int(row["path_count"])
        for row in inventory
    }
    true_path_count = np.array(
        [inventory_lookup[("D0", -1, t)] for t in range(NUM_TIME)], dtype=int
    )
    true_los_count = np.array(
        [
            int(
                next(
                    row
                    for row in inventory
                    if str(row["condition"]) == "D0"
                    and int(row["seed_index"]) == -1
                    and int(row["time_index"]) == t
                )["bounce_0"]
            )
            for t in range(NUM_TIME)
        ],
        dtype=int,
    )
    zone_link_rows: list[dict[str, object]] = []
    for zone in range(NUM_ZONES):
        mask = traj["zone"] == zone
        phone_ap_distance = np.linalg.norm(traj["tx"][mask] - AP[None], axis=1)
        zone_cfr = clean_truth[mask]
        zone_link_rows.append(
            {
                "zone": ZONE_LABELS[zone],
                "num_snapshots": int(mask.sum()),
                "true_cfr_total_energy": float(np.sum(np.abs(zone_cfr) ** 2)),
                "true_cfr_mean_power": float(np.mean(np.abs(zone_cfr) ** 2)),
                "phone_ap_distance_min_m": float(phone_ap_distance.min()),
                "phone_ap_distance_max_m": float(phone_ap_distance.max()),
                "true_path_count_min": int(true_path_count[mask].min()),
                "true_path_count_max": int(true_path_count[mask].max()),
                "los_snapshot_rate": float(np.mean(true_los_count[mask] > 0)),
            }
        )

    for condition in CONDITIONS:
        condition_bases = condition_basis(bases, condition)
        for seed_index in range(NUM_GEOMETRY_SEEDS):
            prediction = theta_cfr(condition_bases[seed_index], THETA_TRUE)
            nrmse, amp, phase = signal_metrics(prediction[None], clean_truth)
            r_est = geometries[condition][seed_index]
            e_r_time = np.linalg.norm(r_est - traj["r_true"], axis=1)
            e_d_time = np.abs(np.linalg.norm(r_est, axis=1) - traj["distance"])
            az_est = np.array([vector_angles(value)[1] for value in r_est])
            el_est = np.array([vector_angles(value)[2] for value in r_est])
            az_error = np.abs(wrap_angle_deg(az_est - traj["azimuth_deg"]))
            el_error = np.abs(el_est - traj["elevation_deg"])
            if condition == "D0":
                modeled_path_count = true_path_count.copy()
            else:
                modeled_path_count = np.array(
                    [inventory_lookup[(condition, seed_index, t)] for t in range(NUM_TIME)], dtype=int
                )
            direct_rows.append(
                {
                    "condition": condition,
                    "seed_index": seed_index,
                    "direct_nrmse": float(nrmse[0]),
                    "amplitude_rms_db": float(amp[0]),
                    "phase_rms_deg": float(phase[0]),
                    "E_r_mean_m": float(np.mean(e_r_time)),
                    "E_d_mean_m": float(np.mean(e_d_time)),
                    "azimuth_abs_error_mean_deg": float(np.mean(az_error)),
                    "elevation_abs_error_mean_deg": float(np.mean(el_error)),
                    "path_count_change_rate": float(np.mean(modeled_path_count != true_path_count)),
                    "path_count_abs_difference_mean": float(np.mean(np.abs(modeled_path_count - true_path_count))),
                }
            )
            for t in range(NUM_TIME):
                time_truth = clean_truth[t]
                time_prediction = prediction[t]
                direct_time_rows.append(
                    {
                        "condition": condition,
                        "seed_index": seed_index,
                        "time_index": t,
                        "zone": ZONE_LABELS[int(traj["zone"][t])],
                        "E_r_m": float(e_r_time[t]),
                        "E_d_m": float(e_d_time[t]),
                        "azimuth_abs_error_deg": float(az_error[t]),
                        "elevation_abs_error_deg": float(el_error[t]),
                        "direct_snapshot_nrmse": float(
                            np.linalg.norm(time_prediction - time_truth)
                            / max(np.linalg.norm(time_truth), 1e-30)
                        ),
                        "true_path_count": int(true_path_count[t]),
                        "model_path_count": int(modeled_path_count[t]),
                    }
                )
            geometry_rows.extend(
                {
                    "condition": condition,
                    "seed_index": seed_index,
                    "time_index": t,
                    "zone": ZONE_LABELS[int(traj["zone"][t])],
                    "r_x": float(r_est[t, 0]),
                    "r_y": float(r_est[t, 1]),
                    "r_z": float(r_est[t, 2]),
                }
                for t in range(NUM_TIME)
            )

    direct_summary = []
    for condition in CONDITIONS:
        rows = [row for row in direct_rows if row["condition"] == condition]
        result: dict[str, object] = {"condition": condition, "label": CONDITION_LABELS[condition]}
        for metric in (
            "direct_nrmse",
            "amplitude_rms_db",
            "phase_rms_deg",
            "E_r_mean_m",
            "E_d_mean_m",
            "azimuth_abs_error_mean_deg",
            "elevation_abs_error_mean_deg",
            "path_count_change_rate",
            "path_count_abs_difference_mean",
        ):
            result.update(percentile_summary(np.array([float(row[metric]) for row in rows]), metric))
        direct_summary.append(result)

    # 五折空间区块留一交叉验证；每折 100 个 CSI 重复，五个几何种子各 20 次。
    repeat_rows: list[dict[str, object]] = []
    power = float(np.mean(np.abs(clean_truth) ** 2))
    component_sigma = math.sqrt(power / (10.0 ** (CSI_SNR_DB / 10.0)) / 2.0)
    for fold in range(NUM_ZONES):
        test_mask = traj["zone"] == fold
        train_mask = ~test_mask
        rng = np.random.default_rng(SEED_CSI + fold)
        noise = component_sigma * (
            rng.normal(size=(NUM_CSI_REPEATS_PER_FOLD, NUM_TIME, stage1.NUM_SUBCARRIERS))
            + 1.0j * rng.normal(size=(NUM_CSI_REPEATS_PER_FOLD, NUM_TIME, stage1.NUM_SUBCARRIERS))
        )
        observations = clean_truth[None] + noise
        seed_assignment = np.arange(NUM_CSI_REPEATS_PER_FOLD) % NUM_GEOMETRY_SEEDS
        test_truth = clean_truth[test_mask]
        for condition in CONDITIONS:
            all_seed_basis = condition_basis(bases, condition)
            repeated_basis = all_seed_basis[seed_assignment]
            theta_hat = golden_fit(observations, repeated_basis, train_mask)
            prediction = theta_cfr(repeated_basis[:, test_mask], theta_hat)
            nrmse, amp, phase = signal_metrics(prediction, test_truth)
            squared_error = np.sum(np.abs(prediction - test_truth[None]) ** 2, axis=(1, 2))
            truth_energy = float(np.sum(np.abs(test_truth) ** 2))
            for repeat in range(NUM_CSI_REPEATS_PER_FOLD):
                repeat_rows.append(
                    {
                        "condition": condition,
                        "fold": fold,
                        "test_zone": ZONE_LABELS[fold],
                        "repeat_in_fold": repeat,
                        "geometry_seed": int(seed_assignment[repeat]),
                        "theta_hat": float(theta_hat[repeat]),
                        "theta_abs_error": float(abs(theta_hat[repeat] - THETA_TRUE)),
                        "test_nrmse": float(nrmse[repeat]),
                        "amplitude_rms_db": float(amp[repeat]),
                        "phase_rms_deg": float(phase[repeat]),
                        "test_squared_error": float(squared_error[repeat]),
                        "test_truth_energy": truth_energy,
                        "theta_lower_bound": int(theta_hat[repeat] <= THETA_BOUNDS[0] + 1e-6),
                        "theta_upper_bound": int(theta_hat[repeat] >= THETA_BOUNDS[1] - 1e-6),
                    }
                )

    cluster_rows: list[dict[str, object]] = []
    for condition in CONDITIONS:
        for fold in range(NUM_ZONES):
            for seed_index in range(NUM_GEOMETRY_SEEDS):
                rows = [
                    row
                    for row in repeat_rows
                    if row["condition"] == condition
                    and int(row["fold"]) == fold
                    and int(row["geometry_seed"]) == seed_index
                ]
                cluster_rows.append(
                    {
                        "condition": condition,
                        "fold": fold,
                        "test_zone": ZONE_LABELS[fold],
                        "geometry_seed": seed_index,
                        "n_csi_repeats": len(rows),
                        "test_nrmse_mean": float(np.mean([float(row["test_nrmse"]) for row in rows])),
                        "theta_hat_mean": float(np.mean([float(row["theta_hat"]) for row in rows])),
                        "theta_abs_error_mean": float(np.mean([float(row["theta_abs_error"]) for row in rows])),
                        "test_squared_error_mean": float(np.mean([float(row["test_squared_error"]) for row in rows])),
                        "test_truth_energy": float(rows[0]["test_truth_energy"]),
                    }
                )

    rng_bootstrap = np.random.default_rng(SEED_BOOTSTRAP)
    group_summary = []
    for condition in CONDITIONS:
        rows = [row for row in repeat_rows if row["condition"] == condition]
        clusters = [row for row in cluster_rows if row["condition"] == condition]
        result: dict[str, object] = {"condition": condition, "label": CONDITION_LABELS[condition]}
        for metric in (
            "theta_hat",
            "theta_abs_error",
            "test_nrmse",
            "amplitude_rms_db",
            "phase_rms_deg",
            "theta_lower_bound",
            "theta_upper_bound",
        ):
            result.update(percentile_summary(np.array([float(row[metric]) for row in rows]), metric))
        cluster_values = np.array([float(row["test_nrmse_mean"]) for row in clusters])
        ci_lo, ci_hi = bootstrap_mean_ci(cluster_values, rng_bootstrap)
        result["test_nrmse_cluster_bootstrap_ci_lo"] = ci_lo
        result["test_nrmse_cluster_bootstrap_ci_hi"] = ci_hi
        pooled_numerator = np.array([float(row["test_squared_error_mean"]) for row in clusters])
        pooled_denominator = np.array([float(row["test_truth_energy"]) for row in clusters])
        pooled_ci_lo, pooled_ci_hi = bootstrap_pooled_nrmse_ci(
            pooled_numerator, pooled_denominator, rng_bootstrap
        )
        result["energy_pooled_test_nrmse"] = float(
            np.sqrt(pooled_numerator.sum() / max(pooled_denominator.sum(), 1e-30))
        )
        result["energy_pooled_cluster_bootstrap_ci_lo"] = pooled_ci_lo
        result["energy_pooled_cluster_bootstrap_ci_hi"] = pooled_ci_hi
        group_summary.append(result)

    comparisons = []
    comparison_pairs = [("D1", "D0"), ("D2", "D1"), ("D3", "D0"), ("D4", "D0"), ("D5", "D4")]
    for candidate, reference in comparison_pairs:
        candidate_clusters = {
            (int(row["fold"]), int(row["geometry_seed"])): float(row["test_nrmse_mean"])
            for row in cluster_rows
            if row["condition"] == candidate
        }
        reference_clusters = {
            (int(row["fold"]), int(row["geometry_seed"])): float(row["test_nrmse_mean"])
            for row in cluster_rows
            if row["condition"] == reference
        }
        keys = sorted(candidate_clusters)
        differences = np.array([candidate_clusters[key] - reference_clusters[key] for key in keys])
        ci_lo, ci_hi = bootstrap_mean_ci(differences, rng_bootstrap)
        candidate_pooled = {
            (int(row["fold"]), int(row["geometry_seed"])): (
                float(row["test_squared_error_mean"]), float(row["test_truth_energy"])
            )
            for row in cluster_rows
            if row["condition"] == candidate
        }
        reference_pooled = {
            (int(row["fold"]), int(row["geometry_seed"])): (
                float(row["test_squared_error_mean"]), float(row["test_truth_energy"])
            )
            for row in cluster_rows
            if row["condition"] == reference
        }
        candidate_num = np.array([candidate_pooled[key][0] for key in keys])
        reference_num = np.array([reference_pooled[key][0] for key in keys])
        denominators = np.array([candidate_pooled[key][1] for key in keys])
        pooled_candidate = float(np.sqrt(candidate_num.sum() / max(denominators.sum(), 1e-30)))
        pooled_reference = float(np.sqrt(reference_num.sum() / max(denominators.sum(), 1e-30)))
        bootstrap_indices = rng_bootstrap.integers(0, len(keys), size=(NUM_BOOTSTRAP, len(keys)))
        sampled_denominator = denominators[bootstrap_indices].sum(axis=1)
        pooled_difference_samples = (
            np.sqrt(candidate_num[bootstrap_indices].sum(axis=1) / np.maximum(sampled_denominator, 1e-30))
            - np.sqrt(reference_num[bootstrap_indices].sum(axis=1) / np.maximum(sampled_denominator, 1e-30))
        )
        comparisons.append(
            {
                "candidate": candidate,
                "reference": reference,
                "metric": "test_nrmse",
                "mean_degradation_candidate_minus_reference": float(np.mean(differences)),
                "cluster_bootstrap_ci_lo": ci_lo,
                "cluster_bootstrap_ci_hi": ci_hi,
                "positive_cluster_rate": float(np.mean(differences > 0.0)),
                "paired_cluster_effect_dz": float(
                    np.mean(differences) / max(np.std(differences, ddof=1), 1e-30)
                ),
                "energy_pooled_degradation": pooled_candidate - pooled_reference,
                "energy_pooled_bootstrap_ci_lo": float(np.quantile(pooled_difference_samples, 0.025)),
                "energy_pooled_bootstrap_ci_hi": float(np.quantile(pooled_difference_samples, 0.975)),
            }
        )

    # 等权合并 D1--D5；这是透明的条件宏平均，不解释为真实传感器发生概率。
    cluster_lookup = {
        (str(row["condition"]), int(row["fold"]), int(row["geometry_seed"])): float(row["test_nrmse_mean"])
        for row in cluster_rows
    }
    macro_values = []
    d0_values = []
    macro_numerators = []
    d0_numerators = []
    macro_denominators = []
    for fold in range(NUM_ZONES):
        for seed_index in range(NUM_GEOMETRY_SEEDS):
            macro_values.append(
                np.mean(
                    [cluster_lookup[(condition, fold, seed_index)] for condition in CONDITIONS[1:]]
                )
            )
            d0_values.append(cluster_lookup[("D0", fold, seed_index)])
            condition_cluster_rows = {
                str(row["condition"]): row
                for row in cluster_rows
                if int(row["fold"]) == fold and int(row["geometry_seed"]) == seed_index
            }
            macro_numerators.append(
                np.mean(
                    [
                        float(condition_cluster_rows[condition]["test_squared_error_mean"])
                        for condition in CONDITIONS[1:]
                    ]
                )
            )
            d0_numerators.append(float(condition_cluster_rows["D0"]["test_squared_error_mean"]))
            macro_denominators.append(float(condition_cluster_rows["D0"]["test_truth_energy"]))
    macro_values = np.asarray(macro_values)
    d0_values = np.asarray(d0_values)
    macro_numerators = np.asarray(macro_numerators)
    d0_numerators = np.asarray(d0_numerators)
    macro_denominators = np.asarray(macro_denominators)
    macro_ci = bootstrap_mean_ci(macro_values, rng_bootstrap)
    macro_diff_ci = bootstrap_mean_ci(macro_values - d0_values, rng_bootstrap)
    pooled_macro = float(
        np.sqrt(macro_numerators.sum() / max(macro_denominators.sum(), 1e-30))
    )
    pooled_d0 = float(
        np.sqrt(d0_numerators.sum() / max(macro_denominators.sum(), 1e-30))
    )
    bootstrap_indices = rng_bootstrap.integers(
        0, len(macro_numerators), size=(NUM_BOOTSTRAP, len(macro_numerators))
    )
    sampled_denominator = macro_denominators[bootstrap_indices].sum(axis=1)
    pooled_macro_samples = np.sqrt(
        macro_numerators[bootstrap_indices].sum(axis=1)
        / np.maximum(sampled_denominator, 1e-30)
    )
    pooled_d0_samples = np.sqrt(
        d0_numerators[bootstrap_indices].sum(axis=1)
        / np.maximum(sampled_denominator, 1e-30)
    )
    macro_summary = {
        "conditions": CONDITIONS[1:],
        "weighting": "equal across D1--D5",
        "cluster_count": len(macro_values),
        "macro_test_nrmse_mean": float(np.mean(macro_values)),
        "macro_test_nrmse_cluster_bootstrap_ci": list(macro_ci),
        "macro_minus_D0_mean": float(np.mean(macro_values - d0_values)),
        "macro_minus_D0_cluster_bootstrap_ci": list(macro_diff_ci),
        "energy_pooled_macro_test_nrmse": pooled_macro,
        "energy_pooled_D0_test_nrmse": pooled_d0,
        "energy_pooled_macro_cluster_bootstrap_ci": [
            float(np.quantile(pooled_macro_samples, 0.025)),
            float(np.quantile(pooled_macro_samples, 0.975)),
        ],
        "energy_pooled_macro_minus_D0": pooled_macro - pooled_d0,
        "energy_pooled_macro_minus_D0_cluster_bootstrap_ci": [
            float(np.quantile(pooled_macro_samples - pooled_d0_samples, 0.025)),
            float(np.quantile(pooled_macro_samples - pooled_d0_samples, 0.975)),
        ],
    }

    # 逐区块结果，审稿人可检查结论是否由单一区域驱动。
    zone_summary = []
    for condition in CONDITIONS:
        for fold in range(NUM_ZONES):
            rows = [
                row for row in repeat_rows if row["condition"] == condition and int(row["fold"]) == fold
            ]
            zone_summary.append(
                {
                    "condition": condition,
                    "test_zone": ZONE_LABELS[fold],
                    "test_nrmse_mean": float(np.mean([float(row["test_nrmse"]) for row in rows])),
                    "theta_hat_mean": float(np.mean([float(row["theta_hat"]) for row in rows])),
                    "amplitude_rms_db_mean": float(np.mean([float(row["amplitude_rms_db"]) for row in rows])),
                    "phase_rms_deg_mean": float(np.mean([float(row["phase_rms_deg"]) for row in rows])),
                }
            )

    write_csv(DATA / "direct_sensitivity_by_seed.csv", direct_rows)
    write_csv(DATA / "direct_sensitivity_by_time.csv", direct_time_rows)
    write_csv(DATA / "direct_sensitivity_summary.csv", direct_summary)
    write_csv(DATA / "geometry_conditions.csv", geometry_rows)
    write_csv(DATA / "cv_metrics_repeats.csv", repeat_rows)
    write_csv(DATA / "cv_cluster_metrics.csv", cluster_rows)
    write_csv(DATA / "cv_group_summary.csv", group_summary)
    write_csv(DATA / "cv_zone_summary.csv", zone_summary)
    write_csv(DATA / "paired_cluster_comparisons.csv", comparisons)
    write_csv(DATA / "zone_link_summary.csv", zone_link_rows)
    write_json(DATA / "macro_summary.json", macro_summary)

    return {
        "clean_truth": clean_truth,
        "direct_rows": direct_rows,
        "direct_time_rows": direct_time_rows,
        "direct_summary": direct_summary,
        "repeat_rows": repeat_rows,
        "cluster_rows": cluster_rows,
        "group_summary": group_summary,
        "zone_summary": zone_summary,
        "comparisons": comparisons,
        "macro_summary": macro_summary,
        "zone_link_summary": zone_link_rows,
    }


def write_trajectory(traj: dict[str, np.ndarray]) -> None:
    rows = []
    for t in range(NUM_TIME):
        body = traj["tx"][t] + traj["r_true"][t]
        rows.append(
            {
                "time_index": t,
                "zone_index": int(traj["zone"][t]),
                "zone": ZONE_LABELS[int(traj["zone"][t])],
                **{f"tx_{axis}": float(traj["tx"][t, i]) for i, axis in enumerate("xyz")},
                **{f"orientation_deg_{axis}": float(traj["orientation_deg"][t, i]) for i, axis in enumerate("xyz")},
                **{f"r_true_{axis}": float(traj["r_true"][t, i]) for i, axis in enumerate("xyz")},
                **{f"body_center_{axis}": float(body[i]) for i, axis in enumerate("xyz")},
                "distance_true_m": float(traj["distance"][t]),
                "azimuth_true_deg": float(traj["azimuth_deg"][t]),
                "elevation_true_deg": float(traj["elevation_deg"][t]),
            }
        )
    write_csv(DATA / "long_trajectory.csv", rows)


def plot_trajectory(traj: dict[str, np.ndarray], geometries: dict[str, np.ndarray]) -> None:
    phone = traj["tx"]
    body_true = phone + traj["r_true"]
    body_d4 = phone[None] + geometries["D4"]
    zone_colors = ["#4c78a8", "#72b7b2", "#54a24b", "#f58518", "#e45756"]
    room_x = (-ROOM_SIZE[0] / 2.0, ROOM_SIZE[0] / 2.0)
    room_y = (-ROOM_SIZE[1] / 2.0, ROOM_SIZE[1] / 2.0)

    fig = plt.figure(figsize=(14.5, 6.2))
    ax3d = fig.add_subplot(1, 2, 1, projection="3d")
    ax2d = fig.add_subplot(1, 2, 2)
    floor_x = [room_x[0], room_x[1], room_x[1], room_x[0], room_x[0]]
    floor_y = [room_y[0], room_y[0], room_y[1], room_y[1], room_y[0]]
    for z in (0.0, ROOM_SIZE[2]):
        ax3d.plot(floor_x, floor_y, np.full(5, z), color="0.75", lw=0.8)
    for x in room_x:
        for y in room_y:
            ax3d.plot([x, x], [y, y], [0.0, ROOM_SIZE[2]], color="0.82", lw=0.7)

    for seed in range(NUM_GEOMETRY_SEEDS):
        label = "D4 observed body centers (5 seeds)" if seed == 0 else None
        for axis in (ax3d, ax2d):
            if axis is ax3d:
                axis.plot(*body_d4[seed].T, color="#9ecae1", alpha=0.28, lw=0.9, label=label)
            else:
                axis.plot(body_d4[seed, :, 0], body_d4[seed, :, 1], color="#9ecae1", alpha=0.28, lw=0.9, label=label)

    ax3d.plot(*phone.T, "k-", lw=1.8, label="Phone trajectory")
    ax2d.plot(phone[:, 0], phone[:, 1], "k-", lw=1.8, label="Phone trajectory")
    ax3d.plot(*body_true.T, color="#d95f02", lw=2.0, label="True body-center trajectory")
    ax2d.plot(body_true[:, 0], body_true[:, 1], color="#d95f02", lw=2.0, label="True body-center trajectory")
    for zone, color in enumerate(zone_colors):
        mask = traj["zone"] == zone
        ax3d.scatter(*phone[mask].T, color=color, s=15, depthshade=False)
        ax2d.scatter(phone[mask, 0], phone[mask, 1], color=color, s=18, zorder=5)
        middle = np.flatnonzero(mask)[NUM_PER_ZONE // 2]
        ax2d.annotate(ZONE_LABELS[zone], phone[middle, :2], xytext=(4, 5), textcoords="offset points", fontsize=8, color=color, weight="bold")
    ax3d.scatter(*AP, marker="*", s=230, color="#d62728", edgecolor="black", label="Fixed AP")
    ax2d.scatter(AP[0], AP[1], marker="*", s=230, color="#d62728", edgecolor="black", zorder=8, label="Fixed AP")
    ax2d.annotate("AP", AP[:2], xytext=(7, 7), textcoords="offset points", color="#b2182b", weight="bold")
    for t in (8, 24, 40, 56, 72):
        pair = np.vstack([phone[t], body_true[t]])
        ax3d.plot(*pair.T, color="0.25", ls=":", lw=1.0)
        ax2d.plot(pair[:, 0], pair[:, 1], color="0.25", ls=":", lw=1.0)

    ax2d.add_patch(Rectangle((room_x[0], room_y[0]), ROOM_SIZE[0], ROOM_SIZE[1], fill=False, color="0.5", lw=1.3))
    ax2d.set_aspect("equal", adjustable="box")
    ax2d.set_xlim(room_x[0] - 0.1, room_x[1] + 0.1)
    ax2d.set_ylim(room_y[0] - 0.1, room_y[1] + 0.1)
    ax3d.set_xlim(*room_x); ax3d.set_ylim(*room_y); ax3d.set_zlim(0.0, ROOM_SIZE[2])
    ax3d.view_init(elev=25, azim=-58)
    ax3d.set_title("3-D room view")
    ax2d.set_title("Top view and spatial hold-out zones")
    for axis in (ax3d, ax2d):
        axis.set_xlabel("x (m)"); axis.set_ylabel("y (m)"); axis.grid(True, alpha=0.2)
    ax3d.set_zlabel("z (m)")
    handles, labels = ax2d.get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=4, frameon=False)
    fig.suptitle("Long trajectory coverage, true human trajectory, D4 observations, and fixed AP")
    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.94))
    fig.savefig(FIGURES / "long_trajectory_scene.png", dpi=210, bbox_inches="tight")
    plt.close(fig)


def plot_geometry_conditions(evaluation: dict[str, object]) -> None:
    rows = evaluation["direct_time_rows"]
    fig, axes = plt.subplots(1, 2, figsize=(13.5, 4.9))
    values = [np.array([float(row["E_r_m"]) for row in rows if row["condition"] == condition]) for condition in CONDITIONS]
    axes[0].boxplot(values, tick_labels=CONDITIONS, showfliers=False)
    for index, condition in enumerate(CONDITIONS, start=1):
        seed_means = [
            np.mean([float(row["E_r_m"]) for row in rows if row["condition"] == condition and int(row["seed_index"]) == seed])
            for seed in range(NUM_GEOMETRY_SEEDS)
        ]
        axes[0].scatter(np.full(NUM_GEOMETRY_SEEDS, index), seed_means, color="black", s=16, zorder=4)
    axes[0].set_ylabel(r"3-D geometry error $E_r(t)$ (m)")
    axes[0].set_title("Error distribution across all times and seeds")

    heatmap = np.zeros((len(CONDITIONS), NUM_ZONES))
    for c, condition in enumerate(CONDITIONS):
        for zone in range(NUM_ZONES):
            heatmap[c, zone] = np.mean(
                [
                    float(row["E_r_m"])
                    for row in rows
                    if row["condition"] == condition and row["zone"] == ZONE_LABELS[zone]
                ]
            )
    image = axes[1].imshow(heatmap, aspect="auto", cmap="YlOrRd", vmin=0.0)
    axes[1].set_xticks(np.arange(NUM_ZONES), [f"Z{i}" for i in range(NUM_ZONES)])
    axes[1].set_yticks(np.arange(len(CONDITIONS)), CONDITIONS)
    axes[1].set_title("Mean geometry error by spatial zone")
    for row in range(len(CONDITIONS)):
        for column in range(NUM_ZONES):
            axes[1].text(column, row, f"{heatmap[row,column]:.3f}", ha="center", va="center", fontsize=8)
    fig.colorbar(image, ax=axes[1], label=r"Mean $E_r$ (m)")
    for axis in axes:
        axis.grid(True, alpha=0.18)
    fig.suptitle("Parallel D0--D5 geometry conditions")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    fig.savefig(FIGURES / "geometry_condition_errors.png", dpi=210, bbox_inches="tight")
    plt.close(fig)


def plot_direct_sensitivity(evaluation: dict[str, object]) -> None:
    rows = evaluation["direct_rows"]
    time_rows = evaluation["direct_time_rows"]
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8))
    x = np.arange(len(CONDITIONS))
    nrmse_seed = [np.array([float(row["direct_nrmse"]) for row in rows if row["condition"] == condition]) for condition in CONDITIONS]
    means = np.array([values.mean() for values in nrmse_seed])
    axes[0].bar(x, np.maximum(means, 1e-12), color=[CONDITION_COLORS[c] for c in CONDITIONS], edgecolor="black", lw=0.5)
    for index, values in enumerate(nrmse_seed):
        axes[0].scatter(np.full(len(values), index), np.maximum(values, 1e-12), color="black", s=15, zorder=4)
    axes[0].set_yscale("log")
    axes[0].set_ylabel(r"Direct NRMSE at $\theta_{ref}=1$")
    axes[0].set_title("Noise-free forward sensitivity")

    zone_heatmap = np.zeros((len(CONDITIONS), NUM_ZONES))
    path_change = np.zeros(len(CONDITIONS))
    for c, condition in enumerate(CONDITIONS):
        for zone in range(NUM_ZONES):
            zone_heatmap[c, zone] = np.mean(
                [
                    float(row["direct_snapshot_nrmse"])
                    for row in time_rows
                    if row["condition"] == condition and row["zone"] == ZONE_LABELS[zone]
                ]
            )
        path_change[c] = np.mean(
            [
                int(row["true_path_count"]) != int(row["model_path_count"])
                for row in time_rows
                if row["condition"] == condition
            ]
        )
    image = axes[1].imshow(zone_heatmap, aspect="auto", cmap="magma", vmin=0.0)
    axes[1].set_xticks(np.arange(NUM_ZONES), [f"Z{i}" for i in range(NUM_ZONES)])
    axes[1].set_yticks(np.arange(len(CONDITIONS)), CONDITIONS)
    axes[1].set_title("Snapshot NRMSE by held-out zone")
    for row in range(len(CONDITIONS)):
        for column in range(NUM_ZONES):
            axes[1].text(column, row, f"{zone_heatmap[row,column]:.2f}", ha="center", va="center", fontsize=8, color="white" if zone_heatmap[row,column] < zone_heatmap.max()*0.60 else "black")
    fig.colorbar(image, ax=axes[1], label="Mean snapshot NRMSE")

    axes[2].bar(x, 100.0 * path_change, color=[CONDITION_COLORS[c] for c in CONDITIONS], edgecolor="black", lw=0.5)
    axes[2].set_ylabel("Snapshots with changed path count (%)")
    axes[2].set_title("Path-set sensitivity")
    axes[2].set_ylim(0.0, max(5.0, 110.0 * path_change.max()))
    for index, value in enumerate(path_change):
        axes[2].text(index, 100.0 * value + 1.0, f"{100*value:.1f}%", ha="center", fontsize=8)

    for axis in (axes[0], axes[2]):
        axis.set_xticks(x, CONDITIONS)
        axis.grid(True, axis="y", alpha=0.2)
    fig.suptitle("Direct geometry-to-channel effect before parameter calibration")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    fig.savefig(FIGURES / "direct_geometry_sensitivity.png", dpi=210, bbox_inches="tight")
    plt.close(fig)


def plot_cv_results(evaluation: dict[str, object]) -> None:
    summaries = {row["condition"]: row for row in evaluation["group_summary"]}
    zones = evaluation["zone_summary"]
    fig, axes = plt.subplots(1, 3, figsize=(15.5, 4.8))
    x = np.arange(len(CONDITIONS))
    nrmse = np.array([float(summaries[c]["test_nrmse_mean"]) for c in CONDITIONS])
    ci_lo = np.array([float(summaries[c]["test_nrmse_cluster_bootstrap_ci_lo"]) for c in CONDITIONS])
    ci_hi = np.array([float(summaries[c]["test_nrmse_cluster_bootstrap_ci_hi"]) for c in CONDITIONS])
    pooled = np.array([float(summaries[c]["energy_pooled_test_nrmse"]) for c in CONDITIONS])
    pooled_lo = np.array([float(summaries[c]["energy_pooled_cluster_bootstrap_ci_lo"]) for c in CONDITIONS])
    pooled_hi = np.array([float(summaries[c]["energy_pooled_cluster_bootstrap_ci_hi"]) for c in CONDITIONS])
    theta = np.array([float(summaries[c]["theta_hat_mean"]) for c in CONDITIONS])
    theta_lo = np.array([float(summaries[c]["theta_hat_q025"]) for c in CONDITIONS])
    theta_hi = np.array([float(summaries[c]["theta_hat_q975"]) for c in CONDITIONS])

    width = 0.38
    axes[0].bar(x - width / 2.0, nrmse, width=width, color=[CONDITION_COLORS[c] for c in CONDITIONS], edgecolor="black", lw=0.5, label="Zone-macro")
    axes[0].bar(x + width / 2.0, pooled, width=width, color="white", edgecolor=[CONDITION_COLORS[c] for c in CONDITIONS], lw=1.5, hatch="//", label="Energy-pooled")
    axes[0].errorbar(x - width / 2.0, nrmse, yerr=np.vstack([nrmse-ci_lo, ci_hi-nrmse]), fmt="none", ecolor="black", capsize=3)
    axes[0].errorbar(x + width / 2.0, pooled, yerr=np.vstack([pooled-pooled_lo, pooled_hi-pooled]), fmt="none", ecolor="black", capsize=3)
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Held-out-zone complex NRMSE")
    axes[0].set_title("5-fold spatial cross-validation")
    axes[0].legend(fontsize=8)

    axes[1].bar(x, theta, color=[CONDITION_COLORS[c] for c in CONDITIONS], edgecolor="black", lw=0.5)
    axes[1].errorbar(x, theta, yerr=np.vstack([theta-theta_lo, theta_hi-theta]), fmt="none", ecolor="black", capsize=3)
    axes[1].axhline(1.0, color="black", ls="--", label="Truth = 1")
    axes[1].axhline(0.5, color="#b2182b", ls=":", label="Lower bound")
    axes[1].set_ylim(0.42, 1.18)
    axes[1].set_ylabel(r"Calibrated $\hat{\theta}_{ref}$")
    axes[1].set_title("Parameter contamination")
    axes[1].legend(fontsize=8)

    zone_heatmap = np.zeros((len(CONDITIONS), NUM_ZONES))
    for c, condition in enumerate(CONDITIONS):
        for zone in range(NUM_ZONES):
            row = next(r for r in zones if r["condition"] == condition and r["test_zone"] == ZONE_LABELS[zone])
            zone_heatmap[c, zone] = float(row["test_nrmse_mean"])
    image = axes[2].imshow(zone_heatmap, aspect="auto", cmap="viridis", vmin=0.0)
    axes[2].set_xticks(np.arange(NUM_ZONES), [f"Z{i}" for i in range(NUM_ZONES)])
    axes[2].set_yticks(np.arange(len(CONDITIONS)), CONDITIONS)
    axes[2].set_title("NRMSE by held-out spatial zone")
    for row in range(len(CONDITIONS)):
        for column in range(NUM_ZONES):
            axes[2].text(column, row, f"{zone_heatmap[row,column]:.2f}", ha="center", va="center", fontsize=8, color="white" if zone_heatmap[row,column] < zone_heatmap.max()*0.60 else "black")
    fig.colorbar(image, ax=axes[2], label="Test NRMSE")

    for axis in axes[:2]:
        axis.set_xticks(x, CONDITIONS)
        axis.grid(True, axis="y", alpha=0.2)
    fig.suptitle("Calibration and prediction under parallel D0--D5 errors")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    fig.savefig(FIGURES / "spatial_cv_results.png", dpi=210, bbox_inches="tight")
    plt.close(fig)


def plot_error_timeline(evaluation: dict[str, object]) -> None:
    rows = evaluation["direct_time_rows"]
    heatmap = np.zeros((len(CONDITIONS), NUM_TIME))
    geometry = np.zeros_like(heatmap)
    for c, condition in enumerate(CONDITIONS):
        for t in range(NUM_TIME):
            selected = [row for row in rows if row["condition"] == condition and int(row["time_index"]) == t]
            heatmap[c, t] = np.mean([float(row["direct_snapshot_nrmse"]) for row in selected])
            geometry[c, t] = np.mean([float(row["E_r_m"]) for row in selected])
    fig, axes = plt.subplots(2, 1, figsize=(14.0, 6.5), sharex=True)
    image0 = axes[0].imshow(geometry, aspect="auto", cmap="YlOrRd", vmin=0.0)
    image1 = axes[1].imshow(heatmap, aspect="auto", cmap="magma", vmin=0.0)
    axes[0].set_yticks(np.arange(len(CONDITIONS)), CONDITIONS)
    axes[1].set_yticks(np.arange(len(CONDITIONS)), CONDITIONS)
    axes[0].set_ylabel("Condition")
    axes[1].set_ylabel("Condition")
    axes[1].set_xlabel("Time index along long trajectory")
    axes[0].set_title("Mean 3-D geometry error across 5 seeds (m)", pad=30)
    axes[1].set_title(r"Mean direct snapshot NRMSE at $\theta_{ref}=1$")
    for boundary in range(1, NUM_ZONES):
        for axis in axes:
            axis.axvline(boundary * NUM_PER_ZONE - 0.5, color="white", ls="--", lw=1.0)
    zone_axis = axes[0].secondary_xaxis("top")
    zone_axis.set_xticks(
        [zone * NUM_PER_ZONE + (NUM_PER_ZONE - 1) / 2.0 for zone in range(NUM_ZONES)],
        [f"Z{zone}" for zone in range(NUM_ZONES)],
    )
    zone_axis.tick_params(length=0, pad=2, labelsize=10)
    fig.colorbar(image0, ax=axes[0], label=r"$E_r$ (m)")
    fig.colorbar(image1, ax=axes[1], label="Snapshot NRMSE")
    fig.suptitle("Where geometry errors occur and how strongly they perturb the channel")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.92))
    fig.savefig(FIGURES / "error_and_channel_timeline.png", dpi=210, bbox_inches="tight")
    plt.close(fig)


def cuboid_faces(center: np.ndarray, size: np.ndarray) -> list[list[np.ndarray]]:
    low = center - size / 2.0
    high = center + size / 2.0
    vertices = np.array(
        [
            [low[0], low[1], low[2]], [high[0], low[1], low[2]],
            [high[0], high[1], low[2]], [low[0], high[1], low[2]],
            [low[0], low[1], high[2]], [high[0], low[1], high[2]],
            [high[0], high[1], high[2]], [low[0], high[1], high[2]],
        ]
    )
    return [[vertices[i] for i in face] for face in ((0,1,2,3),(4,5,6,7),(0,1,5,4),(2,3,7,6),(1,2,6,5),(0,3,7,4))]


def plot_selected_paths(selected: dict[str, object]) -> None:
    order_colors = {0: "#1f77b4", 1: "#2ca02c", 2: "#ff7f0e", 3: "#d62728"}
    keys = ["D0_t8", "D0_t24", "D0_t40", "D0_t56", "D0_t72", "D5_seed0_t10"]
    fig = plt.figure(figsize=(16.0, 9.2))
    for panel, key in enumerate(keys, start=1):
        axis = fig.add_subplot(2, 3, panel, projection="3d")
        row = selected[key]
        tx = np.asarray(row["tx_m"])
        rx = np.asarray(row["rx_m"])
        body = np.asarray(row["body_center_m"])
        axis.add_collection3d(
            Poly3DCollection(cuboid_faces(body, BODY_SIZE), facecolor="#8c564b", edgecolor="black", alpha=0.35)
        )
        for path in row["paths"]:
            order = int(path["bounce_order"])
            vertices = np.asarray(path["vertices_m"], dtype=float).reshape(-1, 3)
            points = np.vstack([tx, vertices, rx])
            axis.plot(
                points[:, 0], points[:, 1], points[:, 2],
                color=order_colors[order], alpha=0.75 if order < 2 else 0.35,
                lw=1.3 if order < 2 else 0.7,
            )
        axis.scatter(*tx, marker="*", s=90, color="#17becf", edgecolor="black")
        axis.scatter(*rx, marker="^", s=65, color="#9467bd", edgecolor="black")
        axis.set_xlim(-3, 3); axis.set_ylim(-2, 2); axis.set_zlim(0, 3)
        axis.set_xlabel("x (m)"); axis.set_ylabel("y (m)"); axis.set_zlabel("z (m)")
        histogram = np.bincount([int(path["bounce_order"]) for path in row["paths"]], minlength=4)
        title = f"{row['condition']} | {row['zone']} | t={row['time_index']}"
        axis.set_title(f"{title}\npaths={len(row['paths'])}, orders={histogram.tolist()}", fontsize=9)
        axis.view_init(elev=24, azim=-58)
    fig.suptitle("All retained WiTwin paths in representative spatial zones (maximum 3 reflections)")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.96))
    fig.savefig(FIGURES / "representative_full_multipath_scenes.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def build_summary(
    traj: dict[str, np.ndarray],
    evaluation: dict[str, object],
    audit: dict[str, object],
    elapsed_seconds: float,
) -> dict[str, object]:
    direct = {row["condition"]: row for row in evaluation["direct_summary"]}
    cv = {row["condition"]: row for row in evaluation["group_summary"]}
    comparisons = {f"{row['candidate']}-{row['reference']}": row for row in evaluation["comparisons"]}
    phone_span = np.ptp(traj["tx"], axis=0)
    body_span = np.ptp(traj["tx"] + traj["r_true"], axis=0)
    phone_xy_bbox_fraction = float(np.prod(phone_span[:2]) / np.prod(ROOM_SIZE[:2]))
    body_xy_bbox_fraction = float(np.prod(body_span[:2]) / np.prod(ROOM_SIZE[:2]))
    go = {
        "G1_small_radial_error_detectable_in_both_aggregations": (
            comparisons["D1-D0"]["cluster_bootstrap_ci_lo"] > 0.0
            and comparisons["D1-D0"]["energy_pooled_bootstrap_ci_lo"] > 0.0
        ),
        "G2_angular_error_detectable_in_both_aggregations": (
            comparisons["D3-D0"]["cluster_bootstrap_ci_lo"] > 0.0
            and comparisons["D3-D0"]["energy_pooled_bootstrap_ci_lo"] > 0.0
        ),
        "G3_joint_error_detectable_in_both_aggregations": (
            comparisons["D4-D0"]["cluster_bootstrap_ci_lo"] > 0.0
            and comparisons["D4-D0"]["energy_pooled_bootstrap_ci_lo"] > 0.0
        ),
        "G4_burst_outliers_worse_than_joint_in_both_aggregations": (
            comparisons["D5-D4"]["cluster_bootstrap_ci_lo"] > 0.0
            and comparisons["D5-D4"]["energy_pooled_bootstrap_ci_lo"] > 0.0
        ),
        "G5_D0_theta_error_below_0_02": cv["D0"]["theta_abs_error_mean"] < 0.02,
        "G6_third_order_paths_observed": audit["maximum_third_order_path_count"] > 0,
        "G7_no_path_cap_hit": audit["maximum_total_path_count"] < audit["path_cap"],
    }
    secondary = {
        "S1_large_radial_worse_than_small_zone_macro": comparisons["D2-D1"]["cluster_bootstrap_ci_lo"] > 0.0,
        "S2_large_radial_worse_than_small_energy_pooled": comparisons["D2-D1"]["energy_pooled_bootstrap_ci_lo"] > 0.0,
    }
    return {
        "success": True,
        "overall_go": bool(all(go.values())),
        "go_criteria": go,
        "secondary_checks": secondary,
        "trajectory": {
            "num_time": NUM_TIME,
            "num_zones": NUM_ZONES,
            "phone_span_m": phone_span.tolist(),
            "body_center_span_m": body_span.tolist(),
            "phone_xy_bbox_room_fraction": phone_xy_bbox_fraction,
            "body_xy_bbox_room_fraction": body_xy_bbox_fraction,
            "ap_m": AP.tolist(),
        },
        "direct_summary": direct,
        "cv_summary": cv,
        "comparisons": comparisons,
        "macro_summary": evaluation["macro_summary"],
        "solver_audit": audit,
        "current_analysis_runtime_seconds": elapsed_seconds,
        "configuration": {
            "max_bounces": MAX_BOUNCES,
            "num_samples": NUM_SAMPLES,
            "max_num_paths": MAX_NUM_PATHS,
            "num_geometry_seeds": NUM_GEOMETRY_SEEDS,
            "num_csi_repeats_per_fold": NUM_CSI_REPEATS_PER_FOLD,
            "num_spatial_folds": NUM_ZONES,
            "total_cv_repeats_per_condition": NUM_CSI_REPEATS_PER_FOLD * NUM_ZONES,
            "cluster_count": NUM_ZONES * NUM_GEOMETRY_SEEDS,
            "csi_snr_db": CSI_SNR_DB,
            "theta_bounds": list(THETA_BOUNDS),
            "seeds": {
                "geometry_start": SEED_GEOMETRY,
                "csi_start": SEED_CSI,
                "bootstrap": SEED_BOOTSTRAP,
            },
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-sim", action="store_true", help="忽略路径基缓存并重跑全部 WiTwin 场景")
    args = parser.parse_args()
    for directory in (DATA, FIGURES):
        directory.mkdir(parents=True, exist_ok=True)
    configure_solver()
    previous_full_runtime = None
    summary_path = DATA / "summary.json"
    if summary_path.exists():
        try:
            previous_full_runtime = json.loads(summary_path.read_text(encoding="utf-8")).get(
                "full_force_run_runtime_seconds"
            )
        except (json.JSONDecodeError, OSError):
            previous_full_runtime = None
    started = time.perf_counter()
    traj = make_long_trajectory()
    geometries = make_geometry_conditions(traj)
    write_trajectory(traj)
    np.savez_compressed(DATA / "geometry_conditions.npz", **geometries)
    bases, inventory, selected, audit = run_simulation(traj, geometries, args.force_sim)
    print("[analysis] evaluating direct sensitivity and spatial cross-validation", flush=True)
    evaluation = evaluate(traj, geometries, bases, inventory)
    plot_trajectory(traj, geometries)
    plot_geometry_conditions(evaluation)
    plot_direct_sensitivity(evaluation)
    plot_cv_results(evaluation)
    plot_error_timeline(evaluation)
    plot_selected_paths(selected)
    elapsed = time.perf_counter() - started
    summary = build_summary(traj, evaluation, audit, elapsed)
    summary["full_force_run_runtime_seconds"] = (
        float(elapsed) if args.force_sim else previous_full_runtime
    )
    summary["current_invocation_runtime_seconds"] = float(elapsed)
    write_json(summary_path, summary)
    print(
        json.dumps(
            {
                "success": True,
                "overall_go": summary["overall_go"],
                "runtime_seconds": elapsed,
                "main_geometry_solves": audit["main_geometry_solves"],
                "path_count_range": [audit["minimum_total_path_count"], audit["maximum_total_path_count"]],
                "D0_test_nrmse": summary["cv_summary"]["D0"]["test_nrmse_mean"],
                "D4_test_nrmse": summary["cv_summary"]["D4"]["test_nrmse_mean"],
                "D5_test_nrmse": summary["cv_summary"]["D5"]["test_nrmse_mean"],
            },
            ensure_ascii=False,
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

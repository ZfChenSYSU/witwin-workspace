#!/opt/witwin/venv/bin/python
"""Reproducible experiment for section 4.3 of the WiTwin research plan."""

from __future__ import annotations

import argparse
import csv
import importlib.metadata as metadata
import json
import math
import os
import subprocess
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


C0 = 299_792_458.0
F_CARRIER = 2.4e9
FREQUENCIES = F_CARRIER + np.linspace(-10e6, 10e6, 64)
D_VALUES = np.round(np.arange(0.25, 0.7001, 0.025), 3)
D0 = 0.40
TX = np.array([0.0, 0.0, 1.2], dtype=float)
RX = np.array([4.0, 0.0, 1.2], dtype=float)
BODY_SIZE = np.array([0.20, 0.45, 1.70], dtype=float)
BODY_EPS_R = 40.0
BODY_SIGMA = 1.0
BLOCKED_ANGLE_DEG = 38.0
SCATTER_SCALES = (0.10, 0.25, 0.50)
NOMINAL_SCATTER_SCALE = 0.25
DIFFRACTION_SCALE = 0.15
BLOCKED_DIRECT_ATTENUATION_DB = 35.0
AMP_THRESHOLD_DB = 1.0
PHASE_THRESHOLD_DEG = 10.0


@dataclass(frozen=True)
class MetricSeries:
    amplitude_rms_db: np.ndarray
    phase_rms_deg: np.ndarray
    complex_nrmse: np.ndarray


def git_revision(path: Path) -> str:
    return subprocess.check_output(
        ["git", "-C", str(path), "rev-parse", "HEAD"], text=True
    ).strip()


def body_position(distance: float, angle_deg: float) -> np.ndarray:
    angle = math.radians(angle_deg)
    return TX + np.array(
        [distance * math.cos(angle), distance * math.sin(angle), 0.0]
    )


def free_space_field(length_m: float, frequencies: np.ndarray = FREQUENCIES) -> np.ndarray:
    length_m = max(float(length_m), 1e-6)
    wavelength = C0 / frequencies
    return wavelength / (4.0 * np.pi * length_m) * np.exp(
        -2.0j * np.pi * frequencies * length_m / C0
    )


def segment_intersects_body(tx: np.ndarray, rx: np.ndarray, center: np.ndarray) -> bool:
    """Slab intersection between a 3-D segment and the axis-aligned body box."""

    lower = center - BODY_SIZE / 2.0
    upper = center + BODY_SIZE / 2.0
    direction = rx - tx
    t_min, t_max = 0.0, 1.0
    for axis in range(3):
        if abs(direction[axis]) < 1e-12:
            if tx[axis] < lower[axis] or tx[axis] > upper[axis]:
                return False
            continue
        t1 = (lower[axis] - tx[axis]) / direction[axis]
        t2 = (upper[axis] - tx[axis]) / direction[axis]
        t_near, t_far = min(t1, t2), max(t1, t2)
        t_min = max(t_min, t_near)
        t_max = min(t_max, t_far)
        if t_min > t_max:
            return False
    return t_max >= 0.0 and t_min <= 1.0


def unblocked_csi(rx: np.ndarray = RX) -> np.ndarray:
    return free_space_field(np.linalg.norm(rx - TX))


def blocked_diffraction_proxy(distance: float, rx: np.ndarray = RX) -> tuple[np.ndarray, bool]:
    center = body_position(distance, BLOCKED_ANGLE_DEG)
    direct = unblocked_csi(rx)
    blocked = segment_intersects_body(TX, rx, center)
    if not blocked:
        return direct, False

    attenuated = direct * 10.0 ** (-BLOCKED_DIRECT_ATTENUATION_DB / 20.0)
    # Two horizontal torso edges provide a transparent geometric diffraction proxy.
    edge_a = center + np.array([0.0, BODY_SIZE[1] / 2.0, 0.0])
    edge_b = center - np.array([0.0, BODY_SIZE[1] / 2.0, 0.0])
    edge_terms = []
    for edge in (edge_a, edge_b):
        length = np.linalg.norm(edge - TX) + np.linalg.norm(rx - edge)
        edge_terms.append(DIFFRACTION_SCALE * free_space_field(length))
    return attenuated + edge_terms[0] + edge_terms[1], True


def complex_permittivity(frequency: float = F_CARRIER) -> complex:
    epsilon_0 = 8.854_187_8128e-12
    return BODY_EPS_R - 1.0j * BODY_SIGMA / (2.0 * np.pi * frequency * epsilon_0)


def normal_incidence_reflection_coefficient() -> complex:
    refractive_index = np.sqrt(complex_permittivity())
    return (1.0 - refractive_index) / (1.0 + refractive_index)


def body_scattering_proxy(
    distance: float, rx: np.ndarray = RX, scatter_scale: float = NOMINAL_SCATTER_SCALE
) -> np.ndarray:
    center = body_position(distance, 90.0)
    direct = unblocked_csi(rx)
    path_length = np.linalg.norm(center - TX) + np.linalg.norm(rx - center)
    scattered = (
        scatter_scale
        * normal_incidence_reflection_coefficient()
        * free_space_field(path_length)
    )
    return direct + scattered


def wrapped_phase_difference(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    return np.angle(a * np.conj(b))


def calculate_metrics(csi: np.ndarray, reference_index: int) -> MetricSeries:
    reference = csi[reference_index]
    eps = np.finfo(float).tiny
    amp_db = 20.0 * np.log10(np.maximum(np.abs(csi), eps))
    ref_amp_db = 20.0 * np.log10(np.maximum(np.abs(reference), eps))
    amplitude_rms_db = np.sqrt(np.mean((amp_db - ref_amp_db) ** 2, axis=-1))
    phase = wrapped_phase_difference(csi, reference[None, :])
    phase_rms_deg = np.degrees(np.sqrt(np.mean(phase**2, axis=-1)))
    denom = max(float(np.linalg.norm(reference)), eps)
    complex_nrmse = np.linalg.norm(csi - reference[None, :], axis=-1) / denom
    return MetricSeries(amplitude_rms_db, phase_rms_deg, complex_nrmse)


def calculate_metrics_with_invalid_zeros(
    csi: np.ndarray, reference_index: int
) -> MetricSeries:
    result = calculate_metrics(csi, reference_index)
    reference_power = float(np.mean(np.abs(csi[reference_index]) ** 2))
    valid = np.mean(np.abs(csi) ** 2, axis=-1) > max(reference_power * 1e-12, 1e-30)
    phase = result.phase_rms_deg.copy()
    phase[~valid] = np.nan
    return MetricSeries(result.amplitude_rms_db, phase, result.complex_nrmse)


def run_proxy_models() -> dict[str, object]:
    unblocked = np.stack([unblocked_csi() for _ in D_VALUES])
    blocked_pairs = [blocked_diffraction_proxy(float(d)) for d in D_VALUES]
    blocked = np.stack([pair[0] for pair in blocked_pairs])
    blocked_flags = np.array([pair[1] for pair in blocked_pairs], dtype=bool)
    scattering_by_scale = {
        str(scale): np.stack(
            [body_scattering_proxy(float(d), scatter_scale=scale) for d in D_VALUES]
        )
        for scale in SCATTER_SCALES
    }
    return {
        "unblocked": unblocked,
        "blocked": blocked,
        "blocked_flags": blocked_flags,
        "scattering_by_scale": scattering_by_scale,
    }


def make_witwin_scene(distance: float, scenario: str) -> wc.Scene:
    angle = 90.0 if scenario == "unblocked" else BLOCKED_ANGLE_DEG
    center = body_position(distance, angle)
    return wc.Scene(
        structures=[
            wc.Structure(
                name="human_body",
                geometry=wc.Box(
                    position=tuple(center), size=tuple(BODY_SIZE), device="cuda"
                ),
                material=wc.Material(eps_r=BODY_EPS_R, sigma_e=BODY_SIGMA),
            )
        ],
        transmitters=[wc.Transmitter("phone_tx", tuple(TX))],
        receivers=[wc.Receiver("rx0", tuple(RX))],
        frequency=F_CARRIER,
        device="cuda",
    )


def run_witwin_los() -> dict[str, object]:
    frequency_tensor = torch.as_tensor(FREQUENCIES, device="cuda", dtype=torch.float32)
    output: dict[str, object] = {}
    config = wc.path.Config(
        num_samples=64,
        max_bounces=0,
        max_diffraction_order=0,
        max_num_paths=4,
        return_geometry=True,
        edge_policy=wc.EdgePolicy(edge_selection_mode="all_edges"),
    )
    for scenario in ("unblocked", "blocked_transition"):
        cfr_values: list[np.ndarray] = []
        path_counts: list[int] = []
        for distance in D_VALUES:
            result = wc.path.solve(
                scene=make_witwin_scene(float(distance), scenario),
                transmitter="phone_tx",
                receiver=["rx0"],
                config=config,
            )
            cfr = result.cfr(frequency_tensor, normalize_delays=False)
            cfr_values.append(cfr.detach().cpu().numpy().reshape(-1, len(FREQUENCIES))[0])
            path_counts.append(
                int(to_torch_view(result.num_paths, detach=True).reshape(-1)[0].item())
            )
        output[scenario] = {
            "cfr": np.stack(cfr_values),
            "path_counts": np.asarray(path_counts, dtype=int),
        }
    return output


def reflection_probe() -> dict[str, object]:
    scene = wc.Scene(
        structures=[
            wc.Structure(
                name="wall",
                geometry=wc.Box(
                    position=(0.0, 0.0, 1.5),
                    size=(0.25, 4.0, 3.0),
                    device="cuda",
                ),
                material=wc.Material(eps_r=4.0, sigma_e=0.0),
            )
        ],
        transmitters=[wc.Transmitter("tx", (-2.0, -1.0, 1.5))],
        receivers=[wc.Receiver("rx", (-2.0, 1.0, 1.5))],
        frequency=3.5e9,
        device="cuda",
    )
    try:
        result = wc.path.solve(
            scene=scene,
            transmitter="tx",
            receiver=["rx"],
            config=wc.path.Config(
                num_samples=64,
                max_bounces=1,
                max_diffraction_order=0,
                max_num_paths=4,
                return_geometry=True,
                edge_policy=wc.EdgePolicy(edge_selection_mode="all_edges"),
            ),
        )
        reflection_paths = result.filter_by_type(wc.path.InteractionType.REFLECTION)
        return {
            "success": True,
            "path_counts": to_torch_view(result.num_paths, detach=True)
            .cpu()
            .reshape(-1)
            .tolist(),
            "reflection_path_counts": to_torch_view(
                reflection_paths.num_paths, detach=True
            )
            .cpu()
            .reshape(-1)
            .tolist(),
            "error_type": None,
            "error": None,
        }
    except Exception as exc:  # The failure is itself a recorded capability result.
        return {
            "success": False,
            "path_counts": None,
            "reflection_path_counts": None,
            "error_type": type(exc).__name__,
            "error": str(exc),
        }


def metric_at_delta(metric: np.ndarray, delta: float) -> float:
    target = D0 + delta
    index = int(np.argmin(np.abs(D_VALUES - target)))
    return float(metric[index])


def write_metric_csv(
    path: Path,
    proxy_metrics: dict[str, MetricSeries],
    witwin_metrics: dict[str, MetricSeries],
    blocked_flags: np.ndarray,
    witwin_data: dict[str, object],
) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(
            [
                "model",
                "scenario",
                "d_t_m",
                "amplitude_rms_db",
                "phase_rms_deg",
                "complex_nrmse",
                "blocked",
                "path_count",
            ]
        )
        for scenario, metrics in proxy_metrics.items():
            for index, distance in enumerate(D_VALUES):
                writer.writerow(
                    [
                        "proxy",
                        scenario,
                        distance,
                        metrics.amplitude_rms_db[index],
                        metrics.phase_rms_deg[index],
                        metrics.complex_nrmse[index],
                        bool(blocked_flags[index]) if scenario == "blocked" else False,
                        "",
                    ]
                )
        for scenario, metrics in witwin_metrics.items():
            for index, distance in enumerate(D_VALUES):
                writer.writerow(
                    [
                        "witwin",
                        scenario,
                        distance,
                        metrics.amplitude_rms_db[index],
                        metrics.phase_rms_deg[index],
                        metrics.complex_nrmse[index],
                        "",
                        witwin_data[scenario]["path_counts"][index],
                    ]
                )


def plot_residuals(
    path: Path,
    proxy_metrics: dict[str, MetricSeries],
) -> None:
    labels = {
        "unblocked": "Unblocked LOS control",
        "blocked": "Occlusion + edge proxy",
        "scattering_nominal": "Body-scattering proxy (scale 0.25)",
    }
    colors = {"unblocked": "#4c78a8", "blocked": "#e45756", "scattering_nominal": "#59a14f"}
    fig, axes = plt.subplots(3, 1, figsize=(8.3, 10.2), sharex=True)
    for scenario, metrics in proxy_metrics.items():
        axes[0].plot(D_VALUES, metrics.amplitude_rms_db, marker="o", ms=3, label=labels[scenario], color=colors[scenario])
        axes[1].plot(D_VALUES, metrics.phase_rms_deg, marker="o", ms=3, label=labels[scenario], color=colors[scenario])
        axes[2].plot(D_VALUES, metrics.complex_nrmse, marker="o", ms=3, label=labels[scenario], color=colors[scenario])
    axes[0].axhline(AMP_THRESHOLD_DB, color="black", ls="--", alpha=0.45, label="1 dB screening threshold")
    axes[1].axhline(PHASE_THRESHOLD_DEG, color="black", ls="--", alpha=0.45, label="10° screening threshold")
    for axis in axes:
        axis.axvline(D0, color="gray", ls="-.", alpha=0.7)
        axis.grid(True, alpha=0.25)
    axes[0].set_ylabel("Amplitude RMS residual (dB)")
    axes[1].set_ylabel("Phase RMS residual (deg)")
    axes[2].set_ylabel("Complex NRMSE")
    axes[2].set_xlabel("Human-to-phone distance $d_t$ (m)")
    axes[0].legend(fontsize=8, ncol=2)
    fig.suptitle("CSI sensitivity to $d_t$ (reference $d_0=0.40$ m)")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_scattering_robustness(path: Path, proxy_data: dict[str, object]) -> None:
    reference_index = int(np.argmin(np.abs(D_VALUES - D0)))
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 7.0), sharex=True)
    for scale, csi in proxy_data["scattering_by_scale"].items():
        metrics = calculate_metrics(csi, reference_index)
        axes[0].plot(
            D_VALUES,
            metrics.amplitude_rms_db,
            marker="o",
            ms=3,
            label=f"scatter scale={float(scale):.2f}",
        )
        axes[1].plot(
            D_VALUES,
            metrics.phase_rms_deg,
            marker="o",
            ms=3,
            label=f"scatter scale={float(scale):.2f}",
        )
    axes[0].axhline(AMP_THRESHOLD_DB, color="black", ls="--", alpha=0.5)
    axes[1].axhline(PHASE_THRESHOLD_DEG, color="black", ls="--", alpha=0.5)
    for axis in axes:
        axis.axvline(D0, color="gray", ls="-.")
        axis.grid(True, alpha=0.25)
        axis.legend()
    axes[0].set_ylabel("Amplitude RMS residual (dB)")
    axes[1].set_ylabel("Phase RMS residual (deg)")
    axes[1].set_xlabel("Human-to-phone distance $d_t$ (m)")
    fig.suptitle("Sensitivity to the assumed body-scattering strength")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_selected_cfr(path: Path, proxy_data: dict[str, object]) -> None:
    selected = (0.30, 0.40, 0.50)
    offsets_mhz = (FREQUENCIES - F_CARRIER) / 1e6
    fig, axes = plt.subplots(2, 2, figsize=(11.0, 7.4), sharex=True)
    scenarios = (
        ("blocked", "Occlusion + edge proxy"),
        ("scattering", "Body-scattering proxy"),
    )
    arrays = {
        "blocked": proxy_data["blocked"],
        "scattering": proxy_data["scattering_by_scale"][str(NOMINAL_SCATTER_SCALE)],
    }
    for column, (scenario, title) in enumerate(scenarios):
        for distance in selected:
            index = int(np.argmin(np.abs(D_VALUES - distance)))
            csi = arrays[scenario][index]
            axes[0, column].plot(offsets_mhz, 20.0 * np.log10(np.maximum(np.abs(csi), 1e-30)), label=f"d={D_VALUES[index]:.2f} m")
            axes[1, column].plot(offsets_mhz, np.degrees(np.unwrap(np.angle(csi))), label=f"d={D_VALUES[index]:.2f} m")
        axes[0, column].set_title(title)
        axes[0, column].set_ylabel("|H| (dB)")
        axes[1, column].set_ylabel("Unwrapped phase (deg)")
        axes[1, column].set_xlabel("Subcarrier offset (MHz)")
        axes[0, column].grid(True, alpha=0.25)
        axes[1, column].grid(True, alpha=0.25)
        axes[0, column].legend(fontsize=8)
    fig.suptitle("Complex CSI examples at selected $d_t$")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def spatial_sensitivity() -> dict[str, np.ndarray]:
    x_values = np.linspace(2.0, 6.0, 41)
    y_values = np.linspace(-2.0, 2.0, 41)
    amp = np.zeros((len(y_values), len(x_values)))
    phase = np.zeros_like(amp)
    visibility_change = np.zeros_like(amp)
    for iy, y in enumerate(y_values):
        for ix, x in enumerate(x_values):
            rx = np.array([x, y, 1.2])
            reference = body_scattering_proxy(D0, rx=rx)
            candidates = np.stack(
                [body_scattering_proxy(D0 + delta, rx=rx) for delta in (-0.05, 0.05)]
            )
            combined = np.concatenate([reference[None, :], candidates], axis=0)
            metric = calculate_metrics(combined, 0)
            amp[iy, ix] = float(np.max(metric.amplitude_rms_db[1:]))
            phase[iy, ix] = float(np.max(metric.phase_rms_deg[1:]))
            base_center = body_position(D0, BLOCKED_ANGLE_DEG)
            base_blocked = segment_intersects_body(TX, rx, base_center)
            changed = any(
                segment_intersects_body(TX, rx, body_position(D0 + delta, BLOCKED_ANGLE_DEG)) != base_blocked
                for delta in (-0.05, 0.05)
            )
            visibility_change[iy, ix] = 1.0 if changed else 0.0
    return {
        "x": x_values,
        "y": y_values,
        "amplitude_rms_db": amp,
        "phase_rms_deg": phase,
        "visibility_change": visibility_change,
    }


def plot_spatial_maps(path: Path, spatial: dict[str, np.ndarray]) -> None:
    extent = [spatial["x"][0], spatial["x"][-1], spatial["y"][0], spatial["y"][-1]]
    fig, axes = plt.subplots(1, 3, figsize=(14.0, 4.2), constrained_layout=True)
    maps = (
        (spatial["visibility_change"], "LOS visibility changes\nfor $d_0\\pm5$ cm", "gray_r", 0.0, 1.0),
        (spatial["amplitude_rms_db"], "Scattering proxy amplitude\nmax residual for $d_0\\pm5$ cm", "viridis", 0.0, None),
        (spatial["phase_rms_deg"], "Scattering proxy phase\nmax residual for $d_0\\pm5$ cm", "magma", 0.0, None),
    )
    for axis, (values, title, cmap, vmin, vmax) in zip(axes, maps):
        image = axis.imshow(values, origin="lower", extent=extent, aspect="auto", cmap=cmap, vmin=vmin, vmax=vmax)
        axis.set_title(title)
        axis.set_xlabel("Receiver x (m)")
        axis.set_ylabel("Receiver y (m)")
        axis.set_xlim(extent[0], extent[1])
        axis.set_ylim(extent[2], extent[3])
        fig.colorbar(image, ax=axis, shrink=0.82)
    fig.savefig(path, dpi=180)
    plt.close(fig)


def plot_witwin_los(path: Path, witwin_data: dict[str, object]) -> None:
    fig, axes = plt.subplots(2, 1, figsize=(8.2, 6.8), sharex=True)
    reference_index = int(np.argmin(np.abs(D_VALUES - D0)))
    for scenario, label in (("unblocked", "Unblocked"), ("blocked_transition", "Occlusion transition")):
        counts = witwin_data[scenario]["path_counts"]
        cfr = witwin_data[scenario]["cfr"]
        ref = np.mean(np.abs(cfr[reference_index]))
        relative_db = 20.0 * np.log10(np.maximum(np.mean(np.abs(cfr), axis=1), 1e-30) / max(ref, 1e-30))
        relative_db = np.where(counts > 0, relative_db, np.nan)
        axes[0].step(D_VALUES, counts, where="mid", label=label)
        axes[1].plot(D_VALUES, relative_db, marker="o", ms=3, label=label)
    axes[0].set_ylabel("Native LOS path count")
    axes[1].set_ylabel("Mean |CFR| relative to d0 (dB)")
    axes[1].set_xlabel("Human-to-phone distance $d_t$ (m)")
    for axis in axes:
        axis.axvline(D0, color="gray", ls="-.")
        axis.grid(True, alpha=0.25)
        axis.legend()
    fig.suptitle("Native WiTwin LOS/occlusion cross-check (max_bounces=0)")
    fig.tight_layout()
    fig.savefig(path, dpi=180)
    plt.close(fig)


def selected_scene_definitions() -> list[dict[str, object]]:
    return [
        {
            "name": "(a) Unblocked LOS control: $d_t=0.40$ m",
            "kind": "unblocked",
            "distance": 0.40,
            "body_center": body_position(0.40, 90.0),
        },
        {
            "name": "(b) LOS occlusion + edge proxy: $d_t=0.35$ m",
            "kind": "blocked",
            "distance": 0.35,
            "body_center": body_position(0.35, BLOCKED_ANGLE_DEG),
        },
        {
            "name": "(c) Body-scattering proxy: $d_t=0.45$ m",
            "kind": "scattering",
            "distance": 0.45,
            "body_center": body_position(0.45, 90.0),
        },
    ]


def scene_path_segments(scene: dict[str, object]) -> list[tuple[np.ndarray, np.ndarray, str, str]]:
    center = np.asarray(scene["body_center"], dtype=float)
    kind = str(scene["kind"])
    if kind == "unblocked":
        return [(TX, RX, "#1f77b4", "Native LOS")]
    if kind == "blocked":
        edge_a = center + np.array([0.0, BODY_SIZE[1] / 2.0, 0.0])
        edge_b = center - np.array([0.0, BODY_SIZE[1] / 2.0, 0.0])
        return [
            (TX, RX, "#d62728", "Blocked LOS"),
            (TX, edge_a, "#ff7f0e", "Body-edge diffraction proxy"),
            (edge_a, RX, "#ff7f0e", "Body-edge diffraction proxy"),
            (TX, edge_b, "#ff7f0e", "Body-edge diffraction proxy"),
            (edge_b, RX, "#ff7f0e", "Body-edge diffraction proxy"),
        ]
    return [
        (TX, RX, "#1f77b4", "Native LOS"),
        (TX, center, "#2ca02c", "Body-scattering proxy"),
        (center, RX, "#2ca02c", "Body-scattering proxy"),
    ]


def plot_selected_scenes_top_view(path: Path) -> None:
    scenes = selected_scene_definitions()
    fig, axes = plt.subplots(1, 3, figsize=(15.0, 4.8), sharex=True, sharey=True)
    for axis, scene in zip(axes, scenes):
        center = np.asarray(scene["body_center"], dtype=float)
        axis.add_patch(
            Rectangle(
                (-0.5, -1.0),
                5.0,
                2.0,
                fill=False,
                lw=1.5,
                color="0.35",
                label="Simplified room boundary",
            )
        )
        axis.add_patch(
            Rectangle(
                (center[0] - BODY_SIZE[0] / 2.0, center[1] - BODY_SIZE[1] / 2.0),
                BODY_SIZE[0],
                BODY_SIZE[1],
                facecolor="#8c564b",
                edgecolor="black",
                alpha=0.65,
                label="Body box proxy",
            )
        )
        used_labels: set[str] = set()
        for start, end, color, label in scene_path_segments(scene):
            line_style = "--" if label == "Blocked LOS" else "-"
            axis.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                color=color,
                lw=2.2,
                ls=line_style,
                label=label if label not in used_labels else None,
            )
            used_labels.add(label)
        axis.scatter(TX[0], TX[1], marker="*", s=150, color="#17becf", edgecolor="black", zorder=5, label="Phone Tx")
        axis.scatter(RX[0], RX[1], marker="^", s=95, color="#9467bd", edgecolor="black", zorder=5, label="Receiver Rx")
        axis.annotate("Tx", TX[:2] + np.array([0.05, -0.18]), fontsize=9)
        axis.annotate("Rx", RX[:2] + np.array([-0.18, -0.20]), fontsize=9)
        axis.annotate("Body", center[:2] + np.array([0.08, 0.08]), fontsize=9)
        axis.set_title(str(scene["name"]), fontsize=11)
        axis.set_xlim(-0.55, 4.45)
        axis.set_ylim(-1.05, 1.05)
        axis.set_aspect("equal")
        axis.set_xlabel("x (m)")
        axis.grid(True, alpha=0.2)
    axes[0].set_ylabel("y (m)")
    handles, labels = [], []
    for axis in axes:
        axis_handles, axis_labels = axis.get_legend_handles_labels()
        handles.extend(axis_handles)
        labels.extend(axis_labels)
    deduplicated = dict(zip(labels, handles))
    fig.legend(deduplicated.values(), deduplicated.keys(), loc="lower center", ncol=5, fontsize=9)
    fig.suptitle("Selected scene models and propagation-path geometry (top view)", fontsize=15)
    fig.tight_layout(rect=(0, 0.11, 1, 0.94))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def cuboid_faces(center: np.ndarray, size: np.ndarray) -> list[list[tuple[float, float, float]]]:
    lower = center - size / 2.0
    upper = center + size / 2.0
    x0, y0, z0 = lower
    x1, y1, z1 = upper
    vertices = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    return [
        [vertices[i] for i in (0, 1, 2, 3)],
        [vertices[i] for i in (4, 5, 6, 7)],
        [vertices[i] for i in (0, 1, 5, 4)],
        [vertices[i] for i in (1, 2, 6, 5)],
        [vertices[i] for i in (2, 3, 7, 6)],
        [vertices[i] for i in (3, 0, 4, 7)],
    ]


def draw_room_wireframe(axis) -> None:
    x0, x1 = -0.5, 4.5
    y0, y1 = -1.0, 1.0
    z0, z1 = 0.0, 2.8
    corners = np.array(
        [
            [x0, y0, z0], [x1, y0, z0], [x1, y1, z0], [x0, y1, z0],
            [x0, y0, z1], [x1, y0, z1], [x1, y1, z1], [x0, y1, z1],
        ]
    )
    for i, j in (
        (0, 1), (1, 2), (2, 3), (3, 0),
        (4, 5), (5, 6), (6, 7), (7, 4),
        (0, 4), (1, 5), (2, 6), (3, 7),
    ):
        axis.plot(*zip(corners[i], corners[j]), color="0.65", lw=0.8, alpha=0.8)


def plot_selected_scenes_3d(path: Path) -> None:
    scenes = selected_scene_definitions()
    fig = plt.figure(figsize=(15.2, 5.2))
    for index, scene in enumerate(scenes, start=1):
        axis = fig.add_subplot(1, 3, index, projection="3d")
        center = np.asarray(scene["body_center"], dtype=float)
        draw_room_wireframe(axis)
        body = Poly3DCollection(
            cuboid_faces(center, BODY_SIZE),
            facecolors="#8c564b",
            edgecolors="black",
            linewidths=0.7,
            alpha=0.55,
        )
        axis.add_collection3d(body)
        used_labels: set[str] = set()
        for start, end, color, label in scene_path_segments(scene):
            line_style = "--" if label == "Blocked LOS" else "-"
            axis.plot(
                [start[0], end[0]],
                [start[1], end[1]],
                [start[2], end[2]],
                color=color,
                lw=2.1,
                ls=line_style,
                label=label if label not in used_labels else None,
            )
            used_labels.add(label)
        axis.scatter(*TX, marker="*", s=100, color="#17becf", edgecolor="black", label="Phone Tx")
        axis.scatter(*RX, marker="^", s=70, color="#9467bd", edgecolor="black", label="Receiver Rx")
        axis.set_xlim(-0.5, 4.5)
        axis.set_ylim(-1.0, 1.0)
        axis.set_zlim(0.0, 2.8)
        axis.set_xlabel("x (m)")
        axis.set_ylabel("y (m)")
        axis.set_zlabel("z (m)")
        axis.set_xticks([0.0, 2.0, 4.0])
        axis.set_yticks([-1.0, 0.0, 1.0])
        axis.set_zticks([0.0, 1.0, 2.0])
        axis.set_title(str(scene["name"]), fontsize=10)
        axis.view_init(elev=23, azim=-63)
        axis.set_box_aspect((5.0, 2.0, 2.8))
    handles, labels = [], []
    for axis in fig.axes:
        axis_handles, axis_labels = axis.get_legend_handles_labels()
        handles.extend(axis_handles)
        labels.extend(axis_labels)
    deduplicated = dict(zip(labels, handles))
    fig.legend(deduplicated.values(), deduplicated.keys(), loc="lower center", ncol=5, fontsize=9)
    fig.suptitle("Selected 3-D scene models and propagation paths", fontsize=15)
    fig.tight_layout(rect=(0, 0.10, 1, 0.94))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def build_summary(
    proxy_metrics: dict[str, MetricSeries],
    witwin_data: dict[str, object],
    probe: dict[str, object],
    spatial: dict[str, np.ndarray],
    proxy_data: dict[str, object],
) -> dict[str, object]:
    scenario_summary: dict[str, object] = {}
    for scenario, metrics in proxy_metrics.items():
        scenario_summary[scenario] = {
            "at_minus_5cm": {
                "amplitude_rms_db": metric_at_delta(metrics.amplitude_rms_db, -0.05),
                "phase_rms_deg": metric_at_delta(metrics.phase_rms_deg, -0.05),
                "complex_nrmse": metric_at_delta(metrics.complex_nrmse, -0.05),
            },
            "at_plus_5cm": {
                "amplitude_rms_db": metric_at_delta(metrics.amplitude_rms_db, 0.05),
                "phase_rms_deg": metric_at_delta(metrics.phase_rms_deg, 0.05),
                "complex_nrmse": metric_at_delta(metrics.complex_nrmse, 0.05),
            },
            "at_minus_10cm": {
                "amplitude_rms_db": metric_at_delta(metrics.amplitude_rms_db, -0.10),
                "phase_rms_deg": metric_at_delta(metrics.phase_rms_deg, -0.10),
                "complex_nrmse": metric_at_delta(metrics.complex_nrmse, -0.10),
            },
            "at_plus_10cm": {
                "amplitude_rms_db": metric_at_delta(metrics.amplitude_rms_db, 0.10),
                "phase_rms_deg": metric_at_delta(metrics.phase_rms_deg, 0.10),
                "complex_nrmse": metric_at_delta(metrics.complex_nrmse, 0.10),
            },
            "max_over_scan": {
                "amplitude_rms_db": float(np.nanmax(metrics.amplitude_rms_db)),
                "phase_rms_deg": float(np.nanmax(metrics.phase_rms_deg)),
                "complex_nrmse": float(np.nanmax(metrics.complex_nrmse)),
            },
        }

    robustness: dict[str, object] = {}
    reference_index = int(np.argmin(np.abs(D_VALUES - D0)))
    for scale, csi in proxy_data["scattering_by_scale"].items():
        metrics = calculate_metrics(csi, reference_index)
        robustness[scale] = {
            "max_amp_for_plus_minus_5cm_db": max(
                metric_at_delta(metrics.amplitude_rms_db, -0.05),
                metric_at_delta(metrics.amplitude_rms_db, 0.05),
            ),
            "max_phase_for_plus_minus_5cm_deg": max(
                metric_at_delta(metrics.phase_rms_deg, -0.05),
                metric_at_delta(metrics.phase_rms_deg, 0.05),
            ),
            "observable_at_plus_minus_5cm": bool(
                max(
                    metric_at_delta(metrics.amplitude_rms_db, -0.05),
                    metric_at_delta(metrics.amplitude_rms_db, 0.05),
                )
                >= AMP_THRESHOLD_DB
                or max(
                    metric_at_delta(metrics.phase_rms_deg, -0.05),
                    metric_at_delta(metrics.phase_rms_deg, 0.05),
                )
                >= PHASE_THRESHOLD_DEG
            ),
        }

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "screening_thresholds": {
            "amplitude_rms_db": AMP_THRESHOLD_DB,
            "phase_rms_deg": PHASE_THRESHOLD_DEG,
        },
        "scenario_metrics": scenario_summary,
        "scattering_scale_robustness": robustness,
        "spatial_grid": {
            "receiver_count": int(spatial["amplitude_rms_db"].size),
            "fraction_amp_observable_for_plus_minus_5cm": float(
                np.mean(spatial["amplitude_rms_db"] >= AMP_THRESHOLD_DB)
            ),
            "fraction_phase_observable_for_plus_minus_5cm": float(
                np.mean(spatial["phase_rms_deg"] >= PHASE_THRESHOLD_DEG)
            ),
            "fraction_los_visibility_changed_for_plus_minus_5cm": float(
                np.mean(spatial["visibility_change"] > 0.5)
            ),
            "max_amplitude_rms_db": float(np.max(spatial["amplitude_rms_db"])),
            "max_phase_rms_deg": float(np.max(spatial["phase_rms_deg"])),
        },
        "witwin_los": {
            scenario: {
                "path_counts": data["path_counts"].tolist(),
                "distances_with_no_path_m": D_VALUES[data["path_counts"] == 0].tolist(),
            }
            for scenario, data in witwin_data.items()
        },
        "witwin_reflection_probe": probe,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs",
    )
    args = parser.parse_args()
    output_dir = args.output_dir
    data_dir = output_dir / "data"
    figure_dir = output_dir / "figures"
    data_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    if not os.environ.get("DRJIT_LIBOPTIX_PATH"):
        raise RuntimeError("DRJIT_LIBOPTIX_PATH must be set for this environment")

    reference_index = int(np.argmin(np.abs(D_VALUES - D0)))
    proxy_data = run_proxy_models()
    proxy_metrics = {
        "unblocked": calculate_metrics(proxy_data["unblocked"], reference_index),
        "blocked": calculate_metrics(proxy_data["blocked"], reference_index),
        "scattering_nominal": calculate_metrics(
            proxy_data["scattering_by_scale"][str(NOMINAL_SCATTER_SCALE)],
            reference_index,
        ),
    }

    witwin_data = run_witwin_los()
    witwin_metrics = {
        scenario: calculate_metrics_with_invalid_zeros(data["cfr"], reference_index)
        for scenario, data in witwin_data.items()
    }
    probe = reflection_probe()
    spatial = spatial_sensitivity()

    np.savez_compressed(
        data_dir / "raw_csi_and_spatial.npz",
        distances_m=D_VALUES,
        frequencies_hz=FREQUENCIES,
        proxy_unblocked=proxy_data["unblocked"],
        proxy_blocked=proxy_data["blocked"],
        proxy_scattering_scale_010=proxy_data["scattering_by_scale"]["0.1"],
        proxy_scattering_scale_025=proxy_data["scattering_by_scale"]["0.25"],
        proxy_scattering_scale_050=proxy_data["scattering_by_scale"]["0.5"],
        witwin_unblocked=witwin_data["unblocked"]["cfr"],
        witwin_blocked_transition=witwin_data["blocked_transition"]["cfr"],
        spatial_x=spatial["x"],
        spatial_y=spatial["y"],
        spatial_amplitude_rms_db=spatial["amplitude_rms_db"],
        spatial_phase_rms_deg=spatial["phase_rms_deg"],
        spatial_visibility_change=spatial["visibility_change"],
    )
    write_metric_csv(
        data_dir / "metrics_by_distance.csv",
        proxy_metrics,
        witwin_metrics,
        proxy_data["blocked_flags"],
        witwin_data,
    )
    summary = build_summary(proxy_metrics, witwin_data, probe, spatial, proxy_data)
    runtime = {
        "packages": {
            name: metadata.version(name)
            for name in ("witwin", "witwin-channel", "torch", "drjit", "rayd", "numpy", "matplotlib")
        },
        "source_revisions": {
            "witwin-core": git_revision(Path("/opt/witwin/src/witwin-core")),
            "witwin-channel": git_revision(Path("/opt/witwin/src/witwin-channel")),
        },
        "gpu": torch.cuda.get_device_name(0),
        "drjit_liboptix_path": os.environ.get("DRJIT_LIBOPTIX_PATH"),
        "config": {
            "carrier_hz": F_CARRIER,
            "bandwidth_hz": float(FREQUENCIES[-1] - FREQUENCIES[0]),
            "num_subcarriers": len(FREQUENCIES),
            "d0_m": D0,
            "distances_m": D_VALUES.tolist(),
            "tx_m": TX.tolist(),
            "rx_m": RX.tolist(),
            "body_size_m": BODY_SIZE.tolist(),
            "blocked_angle_deg": BLOCKED_ANGLE_DEG,
            "scatter_scales": list(SCATTER_SCALES),
            "reflection_coefficient_real": float(normal_incidence_reflection_coefficient().real),
            "reflection_coefficient_imag": float(normal_incidence_reflection_coefficient().imag),
        },
    }
    (data_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (data_dir / "runtime.json").write_text(
        json.dumps(runtime, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (data_dir / "reflection_probe.json").write_text(
        json.dumps(probe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    plot_residuals(figure_dir / "csi_residual_vs_distance.png", proxy_metrics)
    plot_scattering_robustness(
        figure_dir / "scattering_strength_robustness.png", proxy_data
    )
    plot_selected_cfr(figure_dir / "csi_selected_subcarriers.png", proxy_data)
    plot_spatial_maps(figure_dir / "spatial_sensitivity_maps.png", spatial)
    plot_witwin_los(figure_dir / "witwin_los_occlusion_check.png", witwin_data)
    plot_selected_scenes_top_view(
        figure_dir / "selected_scenes_top_view.png"
    )
    plot_selected_scenes_3d(figure_dir / "selected_scenes_3d.png")

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

#!/opt/witwin/venv/bin/python
"""从阶段 1 已有数据生成简报专用图，不重新运行射线追踪。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

import run_experiment as experiment


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "outputs" / "data"
FIGURES = ROOT / "outputs" / "figures"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def array_from_rows(rows: list[dict[str, str]], prefix: str) -> np.ndarray:
    return np.array(
        [[float(row[f"{prefix}_{axis}"]) for axis in "xyz"] for row in rows],
        dtype=float,
    )


def plot_simd_trajectory() -> None:
    rows = read_csv(DATA / "trajectory_and_geometry.csv")
    phone = array_from_rows(rows, "tx")
    relative_true = array_from_rows(rows, "r_true")
    body_true = phone + relative_true
    labels = np.array([row["perturbation"] for row in rows])

    trajectory = experiment.trajectory()
    noisy_relative = np.stack(
        [
            experiment.noisy_geometry(trajectory, experiment.SEED_DEPTH + seed_index)[0]
            for seed_index in range(experiment.NUM_DEPTH_REPEATS)
        ]
    )
    body_noisy = phone[None, :, :] + noisy_relative

    # 第一条噪声轨迹必须与主实验导出的 CSV 完全一致，防止绘图参数漂移。
    exported_first_noise = array_from_rows(rows, "r_noisy")
    if not np.allclose(noisy_relative[0], exported_first_noise, atol=1e-12, rtol=0.0):
        raise RuntimeError("SIM-D noise reconstruction does not match trajectory CSV")

    segment_colors = {
        "D0": "#4c78a8",
        "D1": "#72b7b2",
        "D2": "#54a24b",
        "D3": "#f2cf5b",
        "D4": "#f58518",
        "D5": "#e45756",
    }
    room_x = (-experiment.ROOM_SIZE[0] / 2.0, experiment.ROOM_SIZE[0] / 2.0)
    room_y = (-experiment.ROOM_SIZE[1] / 2.0, experiment.ROOM_SIZE[1] / 2.0)

    fig = plt.figure(figsize=(14.5, 6.4))
    ax3d = fig.add_subplot(1, 2, 1, projection="3d")
    ax2d = fig.add_subplot(1, 2, 2)

    # 房间边界与地面轮廓。
    floor_x = [room_x[0], room_x[1], room_x[1], room_x[0], room_x[0]]
    floor_y = [room_y[0], room_y[0], room_y[1], room_y[1], room_y[0]]
    ax3d.plot(floor_x, floor_y, np.zeros(5), color="0.6", lw=1.0, label="Room boundary")
    for z in (0.0, experiment.ROOM_SIZE[2]):
        ax3d.plot(floor_x, floor_y, np.full(5, z), color="0.75", lw=0.8)
    for x in room_x:
        for y in room_y:
            ax3d.plot([x, x], [y, y], [0.0, experiment.ROOM_SIZE[2]], color="0.8", lw=0.7)

    # 五个 SIM-D 深度种子：显示全部轨迹，但降低透明度避免遮挡真值。
    for seed_index, noisy_path in enumerate(body_noisy):
        label = "SIM-D noisy body centers (5 seeds)" if seed_index == 0 else None
        ax3d.plot(
            noisy_path[:, 0], noisy_path[:, 1], noisy_path[:, 2],
            color="#6baed6", lw=1.0, alpha=0.30, marker=".", ms=3, label=label,
        )
        ax2d.plot(
            noisy_path[:, 0], noisy_path[:, 1],
            color="#6baed6", lw=1.0, alpha=0.30, marker=".", ms=3, label=label,
        )

    ax3d.plot(
        phone[:, 0], phone[:, 1], phone[:, 2],
        "k-o", lw=2.0, ms=3.5, label="Phone trajectory",
    )
    ax2d.plot(
        phone[:, 0], phone[:, 1],
        "k-o", lw=2.0, ms=3.5, label="Phone trajectory",
    )
    ax3d.plot(
        body_true[:, 0], body_true[:, 1], body_true[:, 2],
        color="#e6550d", lw=2.4, label="True body-center trajectory",
    )
    ax2d.plot(
        body_true[:, 0], body_true[:, 1],
        color="#e6550d", lw=2.4, label="True body-center trajectory",
    )

    # 在真值人体轨迹上用颜色标出 D0--D5，并标注每段的中间时刻。
    for segment, color in segment_colors.items():
        indices = np.flatnonzero(labels == segment)
        ax3d.scatter(
            body_true[indices, 0], body_true[indices, 1], body_true[indices, 2],
            color=color, s=30, depthshade=False,
        )
        ax2d.scatter(
            body_true[indices, 0], body_true[indices, 1],
            color=color, s=34, zorder=5,
        )
        middle = indices[len(indices) // 2]
        ax2d.annotate(
            segment,
            body_true[middle, :2],
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=9,
            weight="bold",
            color=color,
        )

    # 三个代表时刻的手机--人体相对向量。
    for time_index in (0, 9, 17):
        xyz = np.vstack([phone[time_index], body_true[time_index]])
        ax3d.plot(xyz[:, 0], xyz[:, 1], xyz[:, 2], color="0.25", ls=":", lw=1.2)
        ax2d.plot(xyz[:, 0], xyz[:, 1], color="0.25", ls=":", lw=1.2)

    ap = np.asarray(experiment.RX)
    ax3d.scatter(*ap, marker="*", s=230, color="#d62728", edgecolor="black", label="Fixed AP / CSI receiver")
    ax2d.scatter(ap[0], ap[1], marker="*", s=230, color="#d62728", edgecolor="black", zorder=8, label="Fixed AP / CSI receiver")
    ax2d.annotate("AP", ap[:2], xytext=(8, 7), textcoords="offset points", weight="bold", color="#b2182b")

    for axis in (ax3d, ax2d):
        axis.set_xlabel("x (m)")
        axis.set_ylabel("y (m)")
        axis.grid(True, alpha=0.22)
    ax3d.set_zlabel("z (m)")
    ax3d.set_xlim(*room_x)
    ax3d.set_ylim(*room_y)
    ax3d.set_zlim(0.0, experiment.ROOM_SIZE[2])
    ax3d.set_title("3-D room view")
    ax3d.view_init(elev=25, azim=-58)

    ax2d.add_patch(
        Rectangle(
            (room_x[0], room_y[0]),
            experiment.ROOM_SIZE[0],
            experiment.ROOM_SIZE[1],
            fill=False,
            edgecolor="0.55",
            lw=1.4,
        )
    )
    ax2d.set_xlim(room_x[0] - 0.1, room_x[1] + 0.1)
    ax2d.set_ylim(room_y[0] - 0.1, room_y[1] + 0.1)
    ax2d.set_aspect("equal", adjustable="box")
    ax2d.set_title("Top view with D0--D5 labels")

    handles, legend_labels = ax2d.get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc="lower center", ncol=4, frameon=False)
    fig.suptitle("SIM-D trajectories: phone, human body center, and fixed AP")
    fig.tight_layout(rect=(0.0, 0.08, 1.0, 0.94))
    fig.savefig(FIGURES / "simd_phone_human_ap_trajectory.png", dpi=210, bbox_inches="tight")
    plt.close(fig)


def plot_brief_results() -> None:
    rows = {row["group"]: row for row in read_csv(DATA / "group_summary.csv")}
    groups = ["SIM-A", "SIM-B", "SIM-C", "SIM-D", "SIM-G"]
    colors = ["#4c78a8", "#e45756", "#54a24b", "#72b7b2", "#f58518"]
    x = np.arange(len(groups))

    nrmse = np.array([float(rows[group]["test_nrmse_mean"]) for group in groups])
    nrmse_lo = np.array([float(rows[group]["test_nrmse_q025"]) for group in groups])
    nrmse_hi = np.array([float(rows[group]["test_nrmse_q975"]) for group in groups])
    theta = np.array([float(rows[group]["theta_mean"]) for group in groups])
    theta_lo = np.array([float(rows[group]["theta_q025"]) for group in groups])
    theta_hi = np.array([float(rows[group]["theta_q975"]) for group in groups])

    with (DATA / "geometry_metrics.json").open(encoding="utf-8") as handle:
        geometry = json.load(handle)
    dynamic_groups = ["SIM-B", "SIM-C", "SIM-D", "SIM-G"]
    dynamic_er = [
        geometry["fixed"]["E_r_test_mean_m"],
        0.0,
        geometry["noisy"]["E_r_test_mean_m"],
        geometry["scalar"]["E_r_test_mean_m"],
    ]
    dynamic_colors = [colors[1], colors[2], colors[3], colors[4]]

    fig, axes = plt.subplots(1, 3, figsize=(14.5, 4.7))

    axes[0].bar(x, nrmse, color=colors, edgecolor="black", linewidth=0.5)
    axes[0].errorbar(
        x,
        nrmse,
        yerr=np.vstack([nrmse - nrmse_lo, nrmse_hi - nrmse]),
        fmt="none",
        ecolor="black",
        capsize=3,
        lw=1.0,
    )
    axes[0].set_yscale("log")
    axes[0].set_ylabel("Test complex NRMSE (log scale)")
    axes[0].set_title("Held-out test error")

    axes[1].bar(x, theta, color=colors, edgecolor="black", linewidth=0.5)
    axes[1].errorbar(
        x,
        theta,
        yerr=np.vstack([theta - theta_lo, theta_hi - theta]),
        fmt="none",
        ecolor="black",
        capsize=3,
        lw=1.0,
    )
    axes[1].axhline(1.0, color="black", ls="--", lw=1.2, label="Truth = 1")
    axes[1].axhline(0.5, color="#b2182b", ls=":", lw=1.2, label="Search lower bound")
    axes[1].set_ylim(0.42, 1.12)
    axes[1].set_ylabel(r"Calibrated $\hat{\theta}_{ref}$")
    axes[1].set_title("Calibration result (D0--D4)")
    axes[1].legend(fontsize=8)

    axes[2].bar(np.arange(len(dynamic_groups)), dynamic_er, color=dynamic_colors, edgecolor="black", linewidth=0.5)
    axes[2].set_ylabel(r"D5 geometry error $E_r$ (m)")
    axes[2].set_title("Dynamic D5 geometry accuracy")
    for index, value in enumerate(dynamic_er):
        axes[2].text(index, value + 0.012, f"{value:.3f}", ha="center", va="bottom", fontsize=8)
    axes[2].set_ylim(0.0, 0.44)
    axes[2].set_xticks(np.arange(len(dynamic_groups)), dynamic_groups)

    for axis in axes[:2]:
        axis.set_xticks(x, groups)
    for axis in axes:
        axis.grid(True, axis="y", alpha=0.22)

    fig.suptitle("Stage-1 brief results (SIM-A/B/C/D/G)")
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.93))
    fig.savefig(FIGURES / "brief_main_results.png", dpi=210, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    plot_simd_trajectory()
    plot_brief_results()
    print(FIGURES / "simd_phone_human_ap_trajectory.png")
    print(FIGURES / "brief_main_results.png")


if __name__ == "__main__":
    main()

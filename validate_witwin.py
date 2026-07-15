#!/opt/witwin/venv/bin/python
"""End-to-end validation for the generated WiTwin container."""

from __future__ import annotations

import argparse
import importlib.metadata as metadata
import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import drjit as dr
import numpy as np
import torch
import witwin.channel as wc




def git_revision(path: str) -> str:
    return subprocess.check_output(
        ["git", "-C", path, "rev-parse", "HEAD"], text=True
    ).strip()


def deterministic_validation() -> dict[str, object]:
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
        transmitters=[wc.Transmitter("tx", (-2.0, 0.0, 1.5))],
        receivers=[
            wc.ReceiverGrid(
                "rm",
                axis="z",
                position=1.5,
                bounds=((-3.0, 3.0), (-3.0, 3.0)),
                grid_shape=(4, 4),
            )
        ],
        frequency=3.5e9,
        device="cuda",
    )
    result = wc.deterministic.solve(
        scene=scene,
        transmitter="tx",
        receiver="rm",
        config=wc.deterministic.Config(
            num_samples=32,
            max_bounces=1,
            max_diffraction_order=0,
            edge_policy=wc.EdgePolicy(edge_selection_mode="all_edges"),
        ),
    )
    path_gain = np.asarray(result.path_gain, dtype=np.float32)
    return {
        "shape": list(path_gain.shape),
        "finite": bool(np.isfinite(path_gain).all()),
        "min": float(path_gain.min()),
        "max": float(path_gain.max()),
    }


def path_validation() -> dict[str, object]:
    scene = wc.Scene(
        structures=[
            wc.Structure(
                name="wall_far",
                geometry=wc.Box(
                    position=(0.0, 5.0, 1.5),
                    size=(0.25, 1.0, 3.0),
                    device="cuda",
                ),
                material=wc.Material(eps_r=4.0, sigma_e=0.0),
            )
        ],
        transmitters=[wc.Transmitter("tx", (-2.0, 0.0, 1.5))],
        receivers=[wc.Receiver("rx0", (2.0, 0.0, 1.5))],
        frequency=3.5e9,
        device="cuda",
    )
    result = wc.path.solve(
        scene=scene,
        transmitter="tx",
        receiver=["rx0"],
        config=wc.path.Config(
            num_samples=32,
            max_bounces=0,
            max_diffraction_order=0,
            max_num_paths=8,
            return_geometry=True,
            edge_policy=wc.EdgePolicy(edge_selection_mode="all_edges"),
        ),
    )
    coefficients, delays = result.cir()
    cfr = result.cfr(np.linspace(-10e6, 10e6, 8))
    return {
        "cir_coeff_shape": list(coefficients.shape),
        "cir_delay_shape": list(delays.shape),
        "cfr_shape": list(cfr.shape),
        "cfr_finite": bool(torch.isfinite(cfr).all().item()),
        "cfr_device": str(cfr.device),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output", default="/opt/witwin/logs/validation.json", type=Path
    )
    args = parser.parse_args()

    torch_probe = torch.arange(5, device="cuda", dtype=torch.float32)
    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "packages": {
            name: metadata.version(name)
            for name in (
                "witwin",
                "witwin-channel",
                "torch",
                "drjit",
                "rayd",
                "numpy",
                "matplotlib",
                "tqdm",
                "nanobind",
            )
        },
        "source_revisions": {
            "witwin-core": git_revision("/opt/witwin/src/witwin-core"),
            "witwin-channel": git_revision("/opt/witwin/src/witwin-channel"),
        },
        "runtime": {
            "drjit_liboptix_path": os.environ.get("DRJIT_LIBOPTIX_PATH"),
            "drjit_llvm_backend": bool(dr.has_backend(dr.JitBackend.LLVM)),
            "drjit_cuda_backend": bool(dr.has_backend(dr.JitBackend.CUDA)),
            "torch_cuda_available": torch.cuda.is_available(),
            "torch_cuda_build": torch.version.cuda,
            "gpu": torch.cuda.get_device_name(0),
            "gpu_compute_capability": list(torch.cuda.get_device_capability(0)),
            "torch_gpu_probe_sum": float(torch_probe.square().sum().item()),
        },
        "deterministic": deterministic_validation(),
        "path_los": path_validation(),
        "known_limitations": [
            "witwin-channel 0.1.0 does not declare its RayD dependency.",
            "RayD 0.5.0 has a Dr.Jit symbol-loading failure in this stack.",
            "RayD 0.4.0 validates deterministic solving and LOS path/CIR/CFR.",
            "Reflected path EPC with max_bounces > 0 is not validated in this pinned stack.",
        ],
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

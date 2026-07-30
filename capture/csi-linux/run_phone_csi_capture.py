#!/usr/bin/env python3
"""Run PicoScenes and the WTWN UDP receiver as one Linux capture session.

The script does not reconfigure the Wi-Fi NIC or channel.  Run
``array_prepare_for_picoscenes`` deliberately before starting this command,
because that system tool stops NetworkManager and changes interface state.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from export_picoscenes import normalize_mac


READY_TEXT = "PicoScenes Platform has been launched successfully"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture PicoScenes CSI and WTWN UDP logs together"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--phone-mac", type=normalize_mac, required=True)
    parser.add_argument("--duration", type=float, default=120.0)
    parser.add_argument("--interface-index", type=int, default=2)
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5201)
    parser.add_argument("--ready-timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def command_output(command: list[str]) -> str:
    try:
        return subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=5,
        ).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired) as error:
        return f"unavailable: {error}"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def stop_process(process: subprocess.Popen[bytes] | None) -> None:
    if process is None or process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGINT)
        process.wait(timeout=8)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)


def wait_for_picoscenes(
    process: subprocess.Popen[bytes],
    log_path: Path,
    timeout: float,
) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"PicoScenes exited before becoming ready (code={process.returncode})"
            )
        if log_path.exists() and READY_TEXT in log_path.read_text(
            encoding="utf-8", errors="replace"
        ):
            return
        time.sleep(0.25)
    raise RuntimeError(
        f"PicoScenes did not report readiness within {timeout:.1f} seconds"
    )


def main() -> int:
    args = parse_args()
    if args.duration <= 0:
        raise SystemExit("--duration must be positive")
    if not 1 <= args.port <= 65535:
        raise SystemExit("--port must be in 1..65535")

    script_dir = Path(__file__).resolve().parent
    receiver_script = script_dir / "udp_probe_receiver.py"
    exporter_script = script_dir / "export_picoscenes.py"
    output_dir = args.output_dir.resolve()
    receiver_csv = output_dir / "udp_probe.csv"
    picoscenes_log = output_dir / "picoscenes_capture.log"
    export_dir = output_dir / "export"
    receiver_command = [
        sys.executable,
        str(receiver_script),
        "--bind",
        args.bind,
        "--port",
        str(args.port),
        "--output",
        str(receiver_csv),
    ]
    picoscenes_options = (
        f"-d info -i {args.interface_index} --mode logger "
        f"--source-address-filter {args.phone_mac}"
    )
    picoscenes_command = ["PicoScenes", picoscenes_options]

    if args.dry_run:
        print(
            json.dumps(
                {
                    "output_dir": str(output_dir),
                    "receiver_command": receiver_command,
                    "picoscenes_command": picoscenes_command,
                    "duration_seconds_after_ready": args.duration,
                    "note": "NIC/channel preparation is intentionally not performed",
                },
                indent=2,
            )
        )
        return 0
    if not receiver_script.is_file() or not exporter_script.is_file():
        raise SystemExit("capture scripts are incomplete in capture/csi-linux")
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"output directory must be absent or empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    started_at = datetime.now(timezone.utc)
    network_state_before_capture = command_output(["iw", "dev"])
    receiver: subprocess.Popen[bytes] | None = None
    picoscenes: subprocess.Popen[bytes] | None = None
    capture_error: str | None = None
    try:
        receiver_log = (output_dir / "udp_receiver.log").open("wb")
        pico_log = picoscenes_log.open("wb")
        try:
            receiver = subprocess.Popen(
                receiver_command,
                stdout=receiver_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            time.sleep(0.25)
            if receiver.poll() is not None:
                raise RuntimeError(
                    f"WTWN receiver failed to start (code={receiver.returncode})"
                )
            picoscenes = subprocess.Popen(
                picoscenes_command,
                cwd=output_dir,
                stdout=pico_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            wait_for_picoscenes(picoscenes, picoscenes_log, args.ready_timeout)
            ready_at = datetime.now(timezone.utc)
            print(
                f"READY: CSI and UDP receiver active for {args.duration:.1f}s; "
                f"send iPhone traffic to port {args.port}",
                flush=True,
            )
            deadline = time.monotonic() + args.duration
            while time.monotonic() < deadline:
                if picoscenes.poll() is not None:
                    raise RuntimeError(
                        f"PicoScenes exited during capture (code={picoscenes.returncode})"
                    )
                if receiver.poll() is not None:
                    raise RuntimeError(
                        f"WTWN receiver exited during capture (code={receiver.returncode})"
                    )
                time.sleep(min(0.5, max(0.0, deadline - time.monotonic())))
        finally:
            stop_process(picoscenes)
            stop_process(receiver)
            pico_log.close()
            receiver_log.close()
    except (KeyboardInterrupt, OSError, RuntimeError) as error:
        capture_error = str(error)
        ready_at = locals().get("ready_at")

    finished_at = datetime.now(timezone.utc)
    csi_files = sorted(output_dir.glob("*.csi"))
    export_status: dict[str, object] = {"attempted": False}
    if capture_error is None and len(csi_files) == 1:
        export_command = [
            sys.executable,
            str(exporter_script),
            str(csi_files[0]),
            "--output-dir",
            str(export_dir),
            "--phone-mac",
            args.phone_mac,
            "--require-uplink",
            "--min-mpdu-bytes",
            "1000",
        ]
        completed = subprocess.run(
            export_command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        export_status = {
            "attempted": True,
            "return_code": completed.returncode,
            "output": completed.stdout.strip(),
        }
        if completed.returncode != 0:
            capture_error = (
                "raw capture completed but filtered export failed: "
                f"{completed.stdout.strip()}"
            )
    elif capture_error is None:
        capture_error = (
            f"expected exactly one PicoScenes .csi file, found {len(csi_files)}"
        )

    files = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "capture_manifest.json":
            files.append(
                {
                    "path": str(path.relative_to(output_dir)),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    manifest = {
        "schema_version": "1.0.0",
        "status": "completed" if capture_error is None else "failed",
        "error": capture_error,
        "started_at_utc": started_at.isoformat(),
        "ready_at_utc": ready_at.isoformat() if ready_at else None,
        "finished_at_utc": finished_at.isoformat(),
        "duration_seconds_after_ready": args.duration,
        "phone_mac": args.phone_mac,
        "udp_bind": args.bind,
        "udp_port": args.port,
        "picoscenes_interface_index": args.interface_index,
        "picoscenes_options": picoscenes_options,
        "network_state_before_capture": network_state_before_capture,
        "export": export_status,
        "files": files,
        "notes": [
            "array_prepare_for_picoscenes is intentionally not called automatically",
            "capture status does not claim CSI phase calibration",
        ],
    }
    manifest_path = output_dir / "capture_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"manifest={manifest_path}; status={manifest['status']}")
    if capture_error:
        print(capture_error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

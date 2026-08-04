#!/usr/bin/env python3
"""Export filtered PicoScenes frames to CSV and NumPy arrays.

This script intentionally preserves both clocks exposed by PicoScenes:

* ``device_timestamp_us`` is the CSI device clock.
* ``system_time_ns`` is the Linux CLOCK_REALTIME timestamp attached to the
  same CSI frame.

The two clocks must not be treated as interchangeable.  The companion
``fit_phone_csi_clock.py`` tool estimates their relationship explicitly.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np


MAC_PATTERN = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")


def normalize_mac(value: str) -> str:
    normalized = value.strip().lower().replace("-", ":")
    if not MAC_PATTERN.fullmatch(normalized):
        raise argparse.ArgumentTypeError(f"invalid MAC address: {value!r}")
    return normalized


def format_mac(value: Any) -> str:
    octets = list(value or [])
    if len(octets) != 6:
        return ""
    return ":".join(f"{int(octet) & 0xff:02x}" for octet in octets)


def utc_from_ns(value: int) -> str:
    seconds, nanoseconds = divmod(value, 1_000_000_000)
    base = datetime.fromtimestamp(seconds, tz=timezone.utc)
    return f"{base.strftime('%Y-%m-%dT%H:%M:%S')}.{nanoseconds:09d}Z"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reshape_csi(segment: dict[str, Any]) -> np.ndarray:
    num_tones = int(segment["numTones"])
    num_tx = int(segment["numTx"])
    num_rx = int(segment["numRx"])
    num_csi = int(segment.get("numCSI", 1))
    flat = np.asarray(segment["CSI"], dtype=np.complex128)
    expected = num_tones * num_tx * num_rx * num_csi
    if flat.size != expected:
        raise ValueError(
            "CSI element count does not match dimensions: "
            f"got {flat.size}, expected {expected}"
        )

    # PicoScenes serializes tones contiguously inside TX, RX, CSI dimensions.
    shaped = flat.reshape((num_csi, num_rx, num_tx, num_tones))
    shaped = np.transpose(shaped, (3, 2, 1, 0))
    if num_csi == 1:
        shaped = shaped[..., 0]
    return shaped


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export and filter a PicoScenes .csi capture"
    )
    parser.add_argument("source", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--phone-mac", type=normalize_mac)
    parser.add_argument(
        "--require-uplink",
        action="store_true",
        help="require Addr2=phone, ToDS=1, FromDS=0 and data frame type",
    )
    parser.add_argument(
        "--min-mpdu-bytes",
        type=int,
        default=0,
        help="discard frames whose first MPDU is shorter than this value",
    )
    parser.add_argument(
        "--max-mpdu-bytes",
        type=int,
        default=0,
        help="discard frames whose first MPDU is longer than this value; 0 disables",
    )
    parser.add_argument("--start-system-time-ns", type=int)
    parser.add_argument("--end-system-time-ns", type=int)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = args.source.resolve()
    if not source.is_file():
        raise SystemExit(f"source file does not exist: {source}")
    if args.require_uplink and not args.phone_mac:
        raise SystemExit("--require-uplink also requires --phone-mac")
    if args.min_mpdu_bytes < 0 or args.max_mpdu_bytes < 0:
        raise SystemExit("MPDU byte limits must be non-negative")
    if (
        args.max_mpdu_bytes
        and args.min_mpdu_bytes > args.max_mpdu_bytes
    ):
        raise SystemExit("--min-mpdu-bytes cannot exceed --max-mpdu-bytes")
    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"output directory must be absent or empty: {output_dir}")

    try:
        from picoscenes import Picoscenes
    except ImportError as error:
        raise SystemExit(
            "picoscenes is not installed; run with /opt/witwin/venv-picoscenes/bin/python"
        ) from error

    parsed = Picoscenes(str(source))
    counters = {
        "parsed": len(parsed.raw),
        "missing_required_segments": 0,
        "phone_mac_mismatch": 0,
        "not_infrastructure_uplink": 0,
        "outside_time_window": 0,
        "mpdu_length_mismatch": 0,
        "selected": 0,
    }
    rows: list[dict[str, Any]] = []
    group_frames: dict[
        tuple[tuple[int, ...], tuple[int, ...]], list[np.ndarray]
    ] = {}
    group_names: dict[tuple[tuple[int, ...], tuple[int, ...]], str] = {}

    for capture_index, frame in enumerate(parsed.raw):
        header = frame.get("StandardHeader")
        basic = frame.get("RxSBasic")
        csi_segment = frame.get("CSI")
        if not header or not basic or not csi_segment:
            counters["missing_required_segments"] += 1
            continue

        control = header.get("ControlField") or {}
        addr1 = format_mac(header.get("Addr1"))
        addr2 = format_mac(header.get("Addr2"))
        addr3 = format_mac(header.get("Addr3"))
        to_ds = int(control.get("ToDS", 0))
        from_ds = int(control.get("FromDS", 0))
        frame_type = int(control.get("Type", -1))
        frame_subtype = int(control.get("SubType", -1))

        if args.phone_mac and addr2 != args.phone_mac:
            counters["phone_mac_mismatch"] += 1
            continue
        if args.require_uplink and not (
            to_ds == 1 and from_ds == 0 and frame_type == 2
        ):
            counters["not_infrastructure_uplink"] += 1
            continue

        system_time_ns = int(basic["systemns"])
        if (
            args.start_system_time_ns is not None
            and system_time_ns < args.start_system_time_ns
        ) or (
            args.end_system_time_ns is not None
            and system_time_ns > args.end_system_time_ns
        ):
            counters["outside_time_window"] += 1
            continue

        mpdus = frame.get("MPDUS") or []
        primary_mpdu_bytes = len(mpdus[0]) if mpdus else 0
        if (
            primary_mpdu_bytes < args.min_mpdu_bytes
            or (
                args.max_mpdu_bytes
                and primary_mpdu_bytes > args.max_mpdu_bytes
            )
        ):
            counters["mpdu_length_mismatch"] += 1
            continue

        csi = reshape_csi(csi_segment)
        shape = tuple(int(value) for value in csi.shape)
        indices = np.asarray(csi_segment["SubcarrierIndex"], dtype=np.int16)
        group_key = (shape, tuple(int(value) for value in indices))
        if group_key not in group_frames:
            group_frames[group_key] = []
            group_names[group_key] = f"group_{len(group_names):03d}"
        csi_group = group_names[group_key]
        csi_group_index = len(group_frames[group_key])
        group_frames[group_key].append(csi)

        extra = frame.get("RxExtraInfo") or {}
        rows.append(
            {
                "packet_index": len(rows),
                "capture_index": capture_index,
                "csi_group": csi_group,
                "csi_group_index": csi_group_index,
                "system_time_ns": system_time_ns,
                "system_time_utc": utc_from_ns(system_time_ns),
                "device_timestamp_us": int(basic["timestamp"]),
                "addr1_receiver": addr1,
                "addr2_transmitter": addr2,
                "addr3": addr3,
                "to_ds": to_ds,
                "from_ds": from_ds,
                "frame_type": frame_type,
                "frame_subtype": frame_subtype,
                "retry": int(control.get("Retry", 0)),
                "protected": int(control.get("Protected", 0)),
                "sequence": int(header.get("Sequence", 0)),
                "fragment": int(header.get("Fragment", 0)),
                "mpdu_count": len(mpdus),
                "primary_mpdu_bytes": primary_mpdu_bytes,
                "total_mpdu_bytes": sum(len(mpdu) for mpdu in mpdus),
                "rssi_dbm": int(basic.get("rssi", -128)),
                "rssi1_dbm": int(basic.get("rssi1", -128)),
                "rssi2_dbm": int(basic.get("rssi2", -128)),
                "noise_floor_dbm": int(basic.get("noiseFloor", -128)),
                "center_freq_mhz": int(basic.get("centerFreq", 0)),
                "control_freq_mhz": int(basic.get("controlFreq", 0)),
                "cbw_mhz": int(basic.get("CBW", 0)),
                "packet_cbw_mhz": int(basic.get("packetCBW", 0)),
                "packet_format": int(basic.get("packetFormat", -1)),
                "mcs": int(basic.get("MCS", -1)),
                "guard_interval_ns": int(basic.get("GI", 0)),
                "num_tones": int(csi_segment["numTones"]),
                "num_tx": int(csi_segment["numTx"]),
                "num_rx": int(csi_segment["numRx"]),
                "num_csi": int(csi_segment.get("numCSI", 1)),
                "device_type": int(basic.get("deviceType", 0)),
                "firmware_version": int(csi_segment.get("FirmwareVersion", 0)),
                "acquisition_nic_mac": format_mac(
                    extra.get("macaddr_cur")
                ),
            }
        )

    counters["selected"] = len(rows)
    if not rows:
        raise SystemExit(
            "no CSI frames matched the requested filters; "
            f"counters={json.dumps(counters, sort_keys=True)}"
        )

    output_dir.mkdir(parents=True, exist_ok=True)
    packets_path = output_dir / "csi_packets.csv"
    metadata_path = output_dir / "metadata.json"

    with packets_path.open("w", newline="", encoding="utf-8") as output:
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    group_metadata = []
    for group_key, frames in group_frames.items():
        shape, subcarrier_values = group_key
        group_name = group_names[group_key]
        stacked = np.stack(frames)
        csi_filename = f"csi_{group_name}.npy"
        subcarrier_filename = f"subcarrier_index_{group_name}.npy"
        np.save(output_dir / csi_filename, stacked, allow_pickle=False)
        np.save(
            output_dir / subcarrier_filename,
            np.asarray(subcarrier_values, dtype=np.int16),
            allow_pickle=False,
        )
        group_metadata.append(
            {
                "name": group_name,
                "frames": len(frames),
                "per_frame_shape": list(shape),
                "array_shape": list(stacked.shape),
                "csi_file": csi_filename,
                "subcarrier_index_file": subcarrier_filename,
                "subcarrier_count": len(subcarrier_values),
            }
        )

    # Keep the original simple filenames only when one homogeneous group exists.
    if len(group_metadata) == 1:
        only = group_metadata[0]
        np.save(
            output_dir / "csi.npy",
            np.load(output_dir / str(only["csi_file"]), allow_pickle=False),
            allow_pickle=False,
        )
        np.save(
            output_dir / "subcarrier_index.npy",
            np.load(
                output_dir / str(only["subcarrier_index_file"]),
                allow_pickle=False,
            ),
            allow_pickle=False,
        )

    metadata = {
        "schema_version": "2.0.0",
        "source_file": str(source),
        "source_sha256": sha256_file(source),
        "exported_at_utc": datetime.now(timezone.utc).isoformat(),
        "filters": {
            "phone_mac": args.phone_mac,
            "require_infrastructure_uplink": args.require_uplink,
            "min_mpdu_bytes": args.min_mpdu_bytes,
            "max_mpdu_bytes": args.max_mpdu_bytes or None,
            "start_system_time_ns": args.start_system_time_ns,
            "end_system_time_ns": args.end_system_time_ns,
        },
        "clock_fields": {
            "device_timestamp_us": "PicoScenes RxSBasic.timestamp",
            "system_time_ns": "PicoScenes RxSBasic.systemns / Linux CLOCK_REALTIME",
        },
        "counters": counters,
        "csi_groups": group_metadata,
        "csi_dtype": "complex128",
        "notes": [
            "CSI phase is exported but is not claimed to be calibrated",
            "Addr1 is the intended 802.11 receiver, not the passive CSI acquisition NIC",
        ],
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"exported {len(rows)} of {len(parsed.raw)} frames to {output_dir}; "
        f"csi_groups={len(group_metadata)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

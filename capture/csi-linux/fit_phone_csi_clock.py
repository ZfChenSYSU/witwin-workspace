#!/usr/bin/env python3
"""Estimate a phone monotonic clock to PicoScenes device-clock mapping.

The mapping is composed through the two clock pairs recorded on the Linux host:

1. WTWN receiver rows pair phone monotonic time with Linux realtime.
2. PicoScenes rows pair CSI device time with Linux realtime.

UDP queueing is one-sided, so the phone-to-host fit uses a binned lower envelope.
The result remains an estimated one-way mapping, not hardware synchronization.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


@dataclass(frozen=True)
class ReceiverEvent:
    sequence: int
    phone_ns: int
    receiver_realtime_ns: int
    receiver_monotonic_ns: int
    session_hash: str


@dataclass(frozen=True)
class CSIEvent:
    packet_index: int
    capture_index: int
    system_time_ns: int
    device_ns: int
    sequence: int
    retry: int
    primary_mpdu_bytes: int


@dataclass(frozen=True)
class AffineFit:
    scale: float
    offset: float
    residuals: tuple[float, ...]
    fit_samples: int


def quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("quantile requires at least one value")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(ordered[lower])
    fraction = position - lower
    return float(ordered[lower] * (1 - fraction) + ordered[upper] * fraction)


def rms(values: Iterable[float]) -> float:
    materialized = list(values)
    if not materialized:
        return 0.0
    return math.sqrt(sum(value * value for value in materialized) / len(materialized))


def ordinary_affine_fit(xs: Sequence[int | float], ys: Sequence[int | float]) -> tuple[float, float]:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("affine fit requires equally sized inputs with at least two rows")
    center_x = statistics.fmean(xs)
    center_y = statistics.fmean(ys)
    denominator = sum((float(x) - center_x) ** 2 for x in xs)
    if denominator == 0:
        raise ValueError("affine fit input times have zero span")
    scale = sum(
        (float(x) - center_x) * (float(y) - center_y)
        for x, y in zip(xs, ys)
    ) / denominator
    offset = center_y - scale * center_x
    return scale, offset


def lower_envelope_fit(
    xs: Sequence[int],
    ys: Sequence[int],
    *,
    bin_count: int = 24,
    envelope_quantile: float = 0.05,
) -> AffineFit:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("lower-envelope fit requires at least two clock pairs")
    ordered = sorted(zip(xs, ys))
    bins = max(2, min(bin_count, len(ordered) // 8 or 2))
    anchors_x: list[float] = []
    anchors_y: list[float] = []
    for bin_index in range(bins):
        start = len(ordered) * bin_index // bins
        end = len(ordered) * (bin_index + 1) // bins
        chunk = ordered[start:end]
        if not chunk:
            continue
        anchor_x = statistics.median(x for x, _ in chunk)
        residual = quantile(
            [float(y - x) for x, y in chunk],
            envelope_quantile,
        )
        anchors_x.append(float(anchor_x))
        anchors_y.append(float(anchor_x) + residual)

    scale, _ = ordinary_affine_fit(anchors_x, anchors_y)
    offset = quantile(
        [float(y) - scale * float(x) for x, y in ordered],
        envelope_quantile,
    )
    residuals = tuple(
        float(y) - (scale * float(x) + offset) for x, y in ordered
    )
    return AffineFit(scale, offset, residuals, len(anchors_x))


def robust_affine_fit(xs: Sequence[int], ys: Sequence[int]) -> AffineFit:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("robust affine fit requires at least two clock pairs")
    active = list(range(len(xs)))
    scale = 1.0
    offset = 0.0
    for _ in range(6):
        scale, offset = ordinary_affine_fit(
            [xs[index] for index in active],
            [ys[index] for index in active],
        )
        all_residuals = [
            float(y) - (scale * float(x) + offset) for x, y in zip(xs, ys)
        ]
        median_residual = statistics.median(all_residuals)
        deviations = [
            abs(value - median_residual) for value in all_residuals
        ]
        mad = statistics.median(deviations)
        if mad == 0:
            break
        threshold = max(1.0, 4.5 * 1.4826 * mad)
        updated = [
            index
            for index, value in enumerate(all_residuals)
            if abs(value - median_residual) <= threshold
        ]
        if len(updated) < 2 or updated == active:
            break
        active = updated
    residuals = tuple(
        float(y) - (scale * float(x) + offset) for x, y in zip(xs, ys)
    )
    return AffineFit(scale, offset, residuals, len(active))


def fixed_unit_scale_fit(
    xs: Sequence[int],
    ys: Sequence[int],
    *,
    offset_quantile: float,
) -> AffineFit:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("fixed-scale fit requires at least two clock pairs")
    offset = quantile(
        [float(y - x) for x, y in zip(xs, ys)],
        offset_quantile,
    )
    residuals = tuple(float(y - x) - offset for x, y in zip(xs, ys))
    return AffineFit(1.0, offset, residuals, len(xs))


def normalize_hash(value: str) -> str:
    return value.strip().lower().removeprefix("0x").zfill(16)


def read_phone_log(path: Path) -> dict[int, int]:
    result: dict[int, int] = {}
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row.get("send_status") != "accepted_by_local_udp_stack":
                continue
            result[int(row["sequence"])] = int(row["phone_monotonic_ns"])
    if not result:
        raise ValueError(f"no successful UDP rows in phone log: {path}")
    return result


def read_receiver_events(
    path: Path,
    *,
    requested_session_hash: str | None,
    phone_log: dict[int, int] | None,
) -> tuple[list[ReceiverEvent], str, dict[str, int]]:
    candidate_rows: list[dict[str, str]] = []
    hashes: set[str] = set()
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            if row.get("parse_status") != "ok" or int(row.get("flags", "-1")) != 0:
                continue
            session_hash = normalize_hash(row["session_hash"])
            hashes.add(session_hash)
            candidate_rows.append(row)
    if requested_session_hash:
        selected_hash = normalize_hash(requested_session_hash)
        if selected_hash not in hashes:
            raise ValueError(
                f"session hash {selected_hash} is absent from receiver log; "
                f"available={sorted(hashes)}"
            )
    elif len(hashes) == 1:
        selected_hash = next(iter(hashes))
    else:
        raise ValueError(
            "receiver log contains multiple data sessions; pass --session-hash "
            f"from {sorted(hashes)}"
        )

    events: list[ReceiverEvent] = []
    phone_timestamp_mismatches = 0
    receiver_rows_without_phone_log = 0
    receiver_sequences: set[int] = set()
    for row in candidate_rows:
        if normalize_hash(row["session_hash"]) != selected_hash:
            continue
        sequence = int(row["sequence"])
        phone_ns = int(row["phone_monotonic_ns"])
        if phone_log is not None:
            expected = phone_log.get(sequence)
            if expected is None:
                receiver_rows_without_phone_log += 1
                continue
            if expected != phone_ns:
                phone_timestamp_mismatches += 1
                continue
        kernel_realtime = int(row.get("receiver_kernel_realtime_ns") or 0)
        events.append(
            ReceiverEvent(
                sequence=sequence,
                phone_ns=phone_ns,
                receiver_realtime_ns=(
                    kernel_realtime
                    if kernel_realtime > 0
                    else int(row["receiver_realtime_ns"])
                ),
                receiver_monotonic_ns=int(row["receiver_monotonic_ns"]),
                session_hash=selected_hash,
            )
        )
        receiver_sequences.add(sequence)
    events.sort(key=lambda event: event.phone_ns)
    if len(events) < 2:
        raise ValueError("fewer than two validated receiver events remain")
    crosscheck = {
        "phone_timestamp_mismatches": phone_timestamp_mismatches,
        "receiver_rows_without_phone_log": receiver_rows_without_phone_log,
        "phone_success_rows": len(phone_log or {}),
        "phone_success_rows_missing_at_receiver": (
            len(set(phone_log) - receiver_sequences) if phone_log else 0
        ),
        "receiver_validated_rows": len(events),
    }
    if phone_timestamp_mismatches:
        raise ValueError(
            f"{phone_timestamp_mismatches} phone timestamps disagree between logs"
        )
    return events, selected_hash, crosscheck


def read_csi_events(path: Path) -> list[CSIEvent]:
    events: list[CSIEvent] = []
    with path.open(newline="", encoding="utf-8") as source:
        for row in csv.DictReader(source):
            events.append(
                CSIEvent(
                    packet_index=int(row["packet_index"]),
                    capture_index=int(row["capture_index"]),
                    system_time_ns=int(row["system_time_ns"]),
                    device_ns=int(row["device_timestamp_us"]) * 1_000,
                    sequence=int(row.get("sequence", 0)),
                    retry=int(row.get("retry", 0)),
                    primary_mpdu_bytes=int(row.get("primary_mpdu_bytes", 0)),
                )
            )
    events.sort(key=lambda event: event.system_time_ns)
    if len(events) < 2:
        raise ValueError("fewer than two CSI events are available")
    return events


def monotonic_nearest_matches(
    receivers: Sequence[ReceiverEvent],
    csi_events: Sequence[CSIEvent],
    tolerance_ns: int,
) -> list[tuple[ReceiverEvent, CSIEvent, int]]:
    csi_times = [event.system_time_ns for event in csi_events]
    used: set[int] = set()
    matches: list[tuple[ReceiverEvent, CSIEvent, int]] = []
    last_index = -1
    for receiver in receivers:
        insertion = bisect.bisect_left(csi_times, receiver.receiver_realtime_ns)
        candidates = range(
            max(last_index + 1, insertion - 3),
            min(len(csi_events), insertion + 4),
        )
        available = [index for index in candidates if index not in used]
        if not available:
            continue
        best = min(
            available,
            key=lambda index: abs(
                receiver.receiver_realtime_ns - csi_events[index].system_time_ns
            ),
        )
        delta = receiver.receiver_realtime_ns - csi_events[best].system_time_ns
        if abs(delta) > tolerance_ns:
            continue
        used.add(best)
        last_index = best
        matches.append((receiver, csi_events[best], delta))
    return matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fit phone monotonic time to PicoScenes device time"
    )
    parser.add_argument("--receiver-log", type=Path, required=True)
    parser.add_argument("--csi-packets", type=Path, required=True)
    parser.add_argument("--phone-log", type=Path)
    parser.add_argument("--session-hash")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--match-tolerance-ms", type=float, default=50.0)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    phone_log = read_phone_log(args.phone_log) if args.phone_log else None
    receivers, session_hash, crosscheck = read_receiver_events(
        args.receiver_log,
        requested_session_hash=args.session_hash,
        phone_log=phone_log,
    )
    csi_events = read_csi_events(args.csi_packets)
    tolerance_ns = int(args.match_tolerance_ms * 1_000_000)
    overlap_receivers = [
        event
        for event in receivers
        if (
            csi_events[0].system_time_ns - tolerance_ns
            <= event.receiver_realtime_ns
            <= csi_events[-1].system_time_ns + tolerance_ns
        )
    ]
    if len(overlap_receivers) < 2:
        raise SystemExit(
            "receiver and CSI Linux realtime windows do not overlap; "
            "a clock mapping cannot be composed across different captures"
        )
    receivers = overlap_receivers
    crosscheck["receiver_rows_in_csi_window"] = len(receivers)

    matches = monotonic_nearest_matches(receivers, csi_events, tolerance_ns)
    receiver_span_ns = receivers[-1].phone_ns - receivers[0].phone_ns
    csi_span_ns = csi_events[-1].device_ns - csi_events[0].device_ns
    estimate_clock_scale = (
        receiver_span_ns >= 60_000_000_000
        and csi_span_ns >= 60_000_000_000
    )
    if estimate_clock_scale:
        phone_host = lower_envelope_fit(
            [event.phone_ns for event in receivers],
            [event.receiver_realtime_ns for event in receivers],
        )
        csi_host = robust_affine_fit(
            [event.device_ns for event in csi_events],
            [event.system_time_ns for event in csi_events],
        )
    else:
        phone_host = fixed_unit_scale_fit(
            [event.phone_ns for event in receivers],
            [event.receiver_realtime_ns for event in receivers],
            offset_quantile=0.05,
        )
        csi_host = fixed_unit_scale_fit(
            [event.device_ns for event in csi_events],
            [event.system_time_ns for event in csi_events],
            offset_quantile=0.50,
        )
    phone_to_csi_scale = phone_host.scale / csi_host.scale
    phone_to_csi_offset = (
        phone_host.offset - csi_host.offset
    ) / csi_host.scale
    mapped_residuals = [
        float(csi.device_ns)
        - (
            phone_to_csi_scale * float(receiver.phone_ns)
            + phone_to_csi_offset
        )
        for receiver, csi, _ in matches
    ]
    drift_fit_reliable = (
        estimate_clock_scale
        and receiver_span_ns >= 120_000_000_000
        and csi_span_ns >= 120_000_000_000
        and phone_host.fit_samples >= 12
        and len(matches) >= 100
        and 0.999 <= phone_to_csi_scale <= 1.001
    )
    bridge_residual_rms = math.hypot(
        rms(phone_host.residuals),
        rms(csi_host.residuals),
    )

    output_dir = args.output_dir.resolve()
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"output directory must be absent or empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    matches_path = output_dir / "udp_csi_matches.csv"
    with matches_path.open("w", newline="", encoding="utf-8") as output:
        fieldnames = [
            "session_hash",
            "sequence",
            "phone_monotonic_ns",
            "receiver_realtime_ns",
            "csi_packet_index",
            "csi_capture_index",
            "csi_system_time_ns",
            "csi_device_timestamp_ns",
            "csi_80211_sequence",
            "csi_retry",
            "csi_primary_mpdu_bytes",
            "receiver_minus_csi_system_ns",
            "mapped_csi_device_ns",
            "mapped_minus_observed_csi_ns",
        ]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for receiver, csi, delta in matches:
            mapped = (
                phone_to_csi_scale * float(receiver.phone_ns)
                + phone_to_csi_offset
            )
            writer.writerow(
                {
                    "session_hash": session_hash,
                    "sequence": receiver.sequence,
                    "phone_monotonic_ns": receiver.phone_ns,
                    "receiver_realtime_ns": receiver.receiver_realtime_ns,
                    "csi_packet_index": csi.packet_index,
                    "csi_capture_index": csi.capture_index,
                    "csi_system_time_ns": csi.system_time_ns,
                    "csi_device_timestamp_ns": csi.device_ns,
                    "csi_80211_sequence": csi.sequence,
                    "csi_retry": csi.retry,
                    "csi_primary_mpdu_bytes": csi.primary_mpdu_bytes,
                    "receiver_minus_csi_system_ns": delta,
                    "mapped_csi_device_ns": round(mapped),
                    "mapped_minus_observed_csi_ns": round(mapped - csi.device_ns),
                }
            )

    phone_residual_p50 = quantile(phone_host.residuals, 0.50)
    phone_residual_p95 = quantile(phone_host.residuals, 0.95)
    mapping = {
        "schema_version": "1.0.0",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "session_hash": session_hash,
        "method": (
            "linux_realtime_bridge_with_binned_udp_lower_envelope"
            if estimate_clock_scale
            else "linux_realtime_bridge_with_fixed_unit_scale"
        ),
        "equation": "t_csi_device_ns = clock_scale * t_phone_monotonic_ns + clock_offset_ns",
        "phone_to_csi": {
            "clock_scale": phone_to_csi_scale,
            "clock_offset_ns": phone_to_csi_offset,
            "fit_samples": phone_host.fit_samples,
            "residual_rms_ns": bridge_residual_rms,
            "drift_ppm": (
                (phone_to_csi_scale - 1.0) * 1_000_000
                if estimate_clock_scale
                else None
            ),
            "clock_scale_estimated": estimate_clock_scale,
            "drift_fit_reliable": drift_fit_reliable,
        },
        "phone_to_linux_realtime": {
            "clock_scale": phone_host.scale,
            "clock_offset_ns": phone_host.offset,
            "observations": len(receivers),
            "fit_samples": phone_host.fit_samples,
            "residual_p50_ns": phone_residual_p50,
            "residual_p95_ns": phone_residual_p95,
            "residual_min_ns": min(phone_host.residuals),
            "note": "offset includes unknown minimum one-way network delay",
        },
        "csi_device_to_linux_realtime": {
            "clock_scale": csi_host.scale,
            "clock_offset_ns": csi_host.offset,
            "observations": len(csi_events),
            "inlier_samples": csi_host.fit_samples,
            "residual_rms_ns": rms(csi_host.residuals),
            "residual_p95_abs_ns": quantile(
                [abs(value) for value in csi_host.residuals], 0.95
            ),
        },
        "matching": {
            "method": "monotonic_nearest_linux_realtime",
            "tolerance_ns": tolerance_ns,
            "matched_rows": len(matches),
            "receiver_rows": len(receivers),
            "csi_rows": len(csi_events),
            "mapped_residual_rms_ns": rms(mapped_residuals),
            "mapped_residual_p95_abs_ns": quantile(
                [abs(value) for value in mapped_residuals], 0.95
            )
            if mapped_residuals
            else None,
            "note": "nearest matches are diagnostics and are not used to fit the clock mapping",
        },
        "crosscheck": crosscheck,
        "input_spans_ns": {
            "phone": receiver_span_ns,
            "csi_device": csi_span_ns,
        },
        "limitations": [
            "the mapping is software-estimated, not hardware clock synchronization",
            "phone-to-host offset contains the minimum observed one-way network delay",
            "drift is provisional unless drift_fit_reliable is true",
            "short captures fix clock_scale to 1 and estimate offset only",
            "CSI phase calibration is outside the scope of this clock fit",
        ],
    }
    mapping_path = output_dir / "clock_mapping.json"
    mapping_path.write_text(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"mapping={mapping_path}; matches={len(matches)}/{len(receivers)}; "
        f"clock_scale={phone_to_csi_scale:.12f}; "
        f"drift_reliable={drift_fit_reliable}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

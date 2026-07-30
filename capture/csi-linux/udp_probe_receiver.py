#!/usr/bin/env python3
"""Receive and validate WiTwin WTWN UDP probe packets.

This receiver records host clocks only. PicoScenes/CSI timestamps must remain in
the CSI capture and be associated offline; they are not replaced by these times.
"""

from __future__ import annotations

import argparse
import csv
import json
import signal
import socket
import struct
import time
from dataclasses import asdict, dataclass
from pathlib import Path


HEADER = struct.Struct("!4sBBHQQQ")
MAGIC = b"WTWN"
PROTOCOL_VERSION = 1
HEADER_LENGTH = 32
FLAG_DATA = 0
FLAG_HELLO = 1
FLAG_ACKNOWLEDGEMENT = 2


@dataclass
class SessionSummary:
    packets: int = 0
    bytes: int = 0
    first_sequence: int | None = None
    last_sequence: int | None = None
    sequence_gaps: int = 0
    duplicates_or_reordered: int = 0
    first_phone_monotonic_ns: int | None = None
    last_phone_monotonic_ns: int | None = None
    first_receiver_monotonic_ns: int | None = None
    last_receiver_monotonic_ns: int | None = None

    def observe(
        self,
        sequence: int,
        phone_ns: int,
        receiver_ns: int,
        datagram_bytes: int,
    ) -> None:
        if self.last_sequence is not None:
            if sequence <= self.last_sequence:
                self.duplicates_or_reordered += 1
            elif sequence > self.last_sequence + 1:
                self.sequence_gaps += sequence - self.last_sequence - 1
        self.packets += 1
        self.bytes += datagram_bytes
        self.first_sequence = (
            sequence if self.first_sequence is None else self.first_sequence
        )
        self.last_sequence = sequence
        self.first_phone_monotonic_ns = (
            phone_ns
            if self.first_phone_monotonic_ns is None
            else self.first_phone_monotonic_ns
        )
        self.last_phone_monotonic_ns = phone_ns
        self.first_receiver_monotonic_ns = (
            receiver_ns
            if self.first_receiver_monotonic_ns is None
            else self.first_receiver_monotonic_ns
        )
        self.last_receiver_monotonic_ns = receiver_ns


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=5201)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(f"udp_probe_{time.strftime('%Y%m%d_%H%M%S')}.csv"),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    summary_path = args.output.with_suffix(".summary.json")
    stopping = False

    def request_stop(_signum: int, _frame: object) -> None:
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGTERM, request_stop)

    summaries: dict[str, SessionSummary] = {}
    invalid_packets = 0
    total_packets = 0
    started_realtime_ns = time.time_ns()

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as udp_socket:
        udp_socket.bind((args.bind, args.port))
        udp_socket.settimeout(0.5)

        with args.output.open("w", newline="", encoding="utf-8") as output_file:
            writer = csv.writer(output_file)
            writer.writerow(
                [
                    "receiver_monotonic_ns",
                    "receiver_realtime_ns",
                    "source_ip",
                    "source_port",
                    "datagram_bytes",
                    "magic",
                    "protocol_version",
                    "flags",
                    "header_length",
                    "session_hash",
                    "sequence",
                    "phone_monotonic_ns",
                    "parse_status",
                ]
            )
            output_file.flush()
            print(
                f"WTWN UDP receiver listening on {args.bind}:{args.port}; "
                f"output={args.output}",
                flush=True,
            )

            while not stopping:
                try:
                    datagram, source = udp_socket.recvfrom(65_535)
                except socket.timeout:
                    continue

                receiver_monotonic_ns = time.monotonic_ns()
                receiver_realtime_ns = time.time_ns()
                total_packets += 1
                magic = b""
                version = 0
                flags = 0
                header_length = 0
                session_hash = 0
                sequence = 0
                phone_ns = 0
                status = "ok"

                if len(datagram) < HEADER_LENGTH:
                    status = "datagram_too_short"
                else:
                    (
                        magic,
                        version,
                        flags,
                        header_length,
                        session_hash,
                        sequence,
                        phone_ns,
                    ) = HEADER.unpack_from(datagram)
                    if magic != MAGIC:
                        status = "invalid_magic"
                    elif version != PROTOCOL_VERSION:
                        status = "unsupported_version"
                    elif header_length != HEADER_LENGTH:
                        status = "invalid_header_length"
                    elif flags == FLAG_HELLO:
                        acknowledgement = HEADER.pack(
                            MAGIC,
                            PROTOCOL_VERSION,
                            FLAG_ACKNOWLEDGEMENT,
                            HEADER_LENGTH,
                            session_hash,
                            sequence,
                            phone_ns,
                        )
                        udp_socket.sendto(acknowledgement, source)
                        status = "hello_acknowledged"
                    elif flags != FLAG_DATA:
                        status = "unsupported_flags"

                session_hash_hex = f"{session_hash:016x}"
                if status in {"ok", "hello_acknowledged"}:
                    summaries.setdefault(session_hash_hex, SessionSummary()).observe(
                        sequence,
                        phone_ns,
                        receiver_monotonic_ns,
                        len(datagram),
                    )
                else:
                    invalid_packets += 1

                writer.writerow(
                    [
                        receiver_monotonic_ns,
                        receiver_realtime_ns,
                        source[0],
                        source[1],
                        len(datagram),
                        magic.decode("ascii", errors="replace"),
                        version,
                        flags,
                        header_length,
                        session_hash_hex,
                        sequence,
                        phone_ns,
                        status,
                    ]
                )
                if total_packets % 100 == 0:
                    output_file.flush()
                if total_packets % 250 == 0:
                    valid = total_packets - invalid_packets
                    print(
                        f"received={total_packets} valid={valid} "
                        f"invalid={invalid_packets}",
                        flush=True,
                    )

    finished_realtime_ns = time.time_ns()
    report = {
        "schema_version": "1.0.0",
        "bind": args.bind,
        "port": args.port,
        "started_realtime_ns": started_realtime_ns,
        "finished_realtime_ns": finished_realtime_ns,
        "total_packets": total_packets,
        "invalid_packets": invalid_packets,
        "sessions": {
            session_hash: asdict(summary)
            for session_hash, summary in sorted(summaries.items())
        },
        "notes": [
            "receiver_monotonic_ns and receiver_realtime_ns are Linux host clocks",
            "these fields do not replace PicoScenes CSI timestamps",
        ],
    }
    summary_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"stopped; summary={summary_path}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

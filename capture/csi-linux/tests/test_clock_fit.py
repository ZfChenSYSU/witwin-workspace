from __future__ import annotations

import csv
import importlib.util
import math
import socket
import struct
import sys
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).parents[1] / "fit_phone_csi_clock.py"
SPEC = importlib.util.spec_from_file_location("fit_phone_csi_clock", MODULE_PATH)
assert SPEC and SPEC.loader
clock_fit = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = clock_fit
SPEC.loader.exec_module(clock_fit)

RECEIVER_MODULE_PATH = Path(__file__).parents[1] / "udp_probe_receiver.py"
RECEIVER_SPEC = importlib.util.spec_from_file_location(
    "udp_probe_receiver",
    RECEIVER_MODULE_PATH,
)
assert RECEIVER_SPEC and RECEIVER_SPEC.loader
udp_receiver = importlib.util.module_from_spec(RECEIVER_SPEC)
sys.modules[RECEIVER_SPEC.name] = udp_receiver
RECEIVER_SPEC.loader.exec_module(udp_receiver)


class ClockFitTests(unittest.TestCase):
    def test_legacy_receiver_log_falls_back_to_user_realtime(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "udp.csv"
            with path.open("w", newline="", encoding="utf-8") as output:
                fieldnames = [
                    "parse_status",
                    "flags",
                    "session_hash",
                    "sequence",
                    "phone_monotonic_ns",
                    "receiver_realtime_ns",
                    "receiver_monotonic_ns",
                ]
                writer = csv.DictWriter(output, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(
                    [
                        {
                            "parse_status": "ok",
                            "flags": 0,
                            "session_hash": "1",
                            "sequence": 0,
                            "phone_monotonic_ns": 100,
                            "receiver_realtime_ns": 1_000,
                            "receiver_monotonic_ns": 10,
                        },
                        {
                            "parse_status": "ok",
                            "flags": 0,
                            "session_hash": "1",
                            "sequence": 2,
                            "phone_monotonic_ns": 200,
                            "receiver_realtime_ns": 2_000,
                            "receiver_monotonic_ns": 20,
                        },
                    ]
                )

            events, session_hash, crosscheck = clock_fit.read_receiver_events(
                path,
                requested_session_hash=None,
                phone_log={0: 100, 1: 150, 2: 200},
            )

        self.assertEqual(session_hash, "0000000000000001")
        self.assertEqual(
            [event.receiver_realtime_ns for event in events],
            [1_000, 2_000],
        )
        self.assertEqual(
            crosscheck["phone_success_rows_missing_at_receiver"],
            1,
        )

    def test_linux_kernel_timestamp_ancillary_is_parsed(self) -> None:
        ancillary = [
            (
                socket.SOL_SOCKET,
                udp_receiver.SO_TIMESTAMPNS,
                struct.pack("@ll", 1_785_000_000, 123_456_789),
            )
        ]

        self.assertEqual(
            udp_receiver.extract_kernel_realtime_ns(ancillary),
            1_785_000_000_123_456_789,
        )

    def test_short_capture_can_fix_scale_and_fit_offset_only(self) -> None:
        xs = [10_000_000_000 + index * 5_000_000 for index in range(2_000)]
        ys = [
            x + 1_700_000_000_000_000_000 + 2_000_000 + index % 1_000_000
            for index, x in enumerate(xs)
        ]

        fitted = clock_fit.fixed_unit_scale_fit(
            xs,
            ys,
            offset_quantile=0.05,
        )

        self.assertEqual(fitted.scale, 1.0)
        self.assertEqual(fitted.fit_samples, len(xs))
        self.assertLess(abs(clock_fit.quantile(fitted.residuals, 0.05)), 1.0)

    def test_lower_envelope_recovers_scale_with_queueing_outliers(self) -> None:
        expected_scale = 1.000012
        expected_offset = 1_700_000_000_000_000_000
        xs = [
            40_000_000_000_000 + index * 5_000_000
            for index in range(24_000)
        ]
        ys = []
        for index, x in enumerate(xs):
            base_delay = 1_800_000 + ((index * 7919) % 900_000)
            queue_delay = 0
            if index % 503 in range(0, 18):
                queue_delay = 80_000_000
            ys.append(
                round(
                    expected_scale * x
                    + expected_offset
                    + base_delay
                    + queue_delay
                )
            )

        fitted = clock_fit.lower_envelope_fit(xs, ys)

        self.assertTrue(
            math.isclose(fitted.scale, expected_scale, abs_tol=2e-7)
        )
        # The lower-envelope offset includes minimum one-way delay.
        self.assertLess(
            abs(fitted.offset - (expected_offset + 1_800_000)),
            250_000,
        )
        self.assertLess(clock_fit.quantile(fitted.residuals, 0.95), 2_000_000)

    def test_robust_affine_rejects_large_system_timestamp_outliers(self) -> None:
        expected_scale = 0.999998
        expected_offset = 1_784_000_000_000_000_000
        xs = [index * 1_000_000 for index in range(2_000)]
        ys = [
            round(
                expected_scale * x
                + expected_offset
                + ((index % 7) - 3) * 20_000
            )
            for index, x in enumerate(xs)
        ]
        for index in (100, 700, 1300):
            ys[index] += 120_000_000

        fitted = clock_fit.robust_affine_fit(xs, ys)

        self.assertTrue(
            math.isclose(fitted.scale, expected_scale, abs_tol=2e-7)
        )
        self.assertLess(abs(fitted.offset - expected_offset), 100_000)
        self.assertEqual(fitted.fit_samples, len(xs) - 3)


if __name__ == "__main__":
    unittest.main()

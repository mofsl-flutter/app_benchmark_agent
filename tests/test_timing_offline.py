"""Unit tests for the pure parts of timing.py and offline.py. Run: python3 -m unittest discover tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("RIISE_BENCH_HOME", tempfile.mkdtemp())

import benchlib as B  # noqa: E402
import offline  # noqa: E402
import timing  # noqa: E402


class TimingTests(unittest.TestCase):
    def test_parse_touches_scales_to_pixels(self):
        out = ("[   10.000100] EV_ABS       ABS_MT_POSITION_X    000007ff\n"
               "[   10.000100] EV_ABS       ABS_MT_POSITION_Y    00000fff\n"
               "[   10.000200] EV_KEY       BTN_TOUCH            DOWN\n"
               "[   10.000300] EV_SYN       SYN_REPORT           00000000\n")
        (t, x, y), = timing.parse_touches(out, (4095, 4095), (1080, 2340))
        self.assertAlmostEqual(t, 10.0002)
        self.assertAlmostEqual(x, 2047 * 1080 / 4095)
        self.assertAlmostEqual(y, 2340)

    def test_analyse_tap_then_load(self):
        import numpy as np
        n, h, w = 300, 120, 60
        frames = np.zeros((n, h, w), np.uint8)
        frames[60:, 47:57, 25:35] = 255          # tap dot (Show taps, ~10 px at analysis scale) at frame 60
        frames[90:, 20:110, :] = 200              # content arrives at frame 90 and stays
        t0, resp, settled, how = timing.analyse(frames, 1.0, [(30, 52)])
        self.assertEqual((t0, resp, settled, how), (60, 90, 90, "tap dot"))

    def test_problem_of(self):
        self.assertEqual(timing.problem_of([], 1, 5, 9), "no touch seen")
        self.assertIn("2 touches", timing.problem_of([1, 2], 1, 5, 9))
        self.assertIn("did not settle", timing.problem_of([1], 1, 5, None))
        self.assertEqual(timing.problem_of([1], 1, 10, 30), "")


class OfflineTests(unittest.TestCase):
    def test_every_seeded_item_has_a_step(self):
        for name in ("portfolio", "mf", "funds"):
            phases = [offline.phase_of(it) for it in B.load_module(name)["offline_items"]]
            self.assertEqual(sorted(phases), sorted(["cold", "cold", "lost", "lost", "lost", "reconnect", "reconnect", "detail", "end"]))


class ModuleRunsTests(unittest.TestCase):
    def test_module_run_overrides(self):
        e = B.expected(B.load_module("funds"))
        self.assertEqual(sorted(e), ["C1", "C4", "L14", "L15", "L3", "L4", "R2"])   # agreed Funds scope; no facts without L6/L7
        self.assertEqual((e["L3"], e["C1"]), (3, 3))
        self.assertEqual(B.expected(B.load_module("mf"))["L3"], 5)
        self.assertEqual(B.expected(B.load_module("portfolio"))["L3"], 5)


if __name__ == "__main__":
    unittest.main()

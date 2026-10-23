"""Unit tests for the frame scoring in bench.py, including the SurfaceFlinger fallback for apps (Flutter on
Android 16) whose frames Perfetto FrameTimeline never attributes to the app. Run: python3 -m unittest discover tests"""
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import bench  # noqa: E402

MS = 1_000_000


def presents(gaps_ms, start=10 * MS):
    """Display frames with the given present-to-present gaps; dur and jank are irrelevant for intervals."""
    out, ts = [], start
    for g in [0] + list(gaps_ms):
        ts += int(g * MS)
        out.append((ts, 5 * MS, "None"))
    return out


class IntervalStatsTests(unittest.TestCase):
    def test_steady_120hz_has_no_jank(self):
        s = bench.interval_stats(presents([8.33] * 120))
        self.assertEqual(s["jank_pct"], 0.0)
        self.assertEqual(s["p50"], 8.3)
        self.assertEqual(s["fps"], 120.0)
        self.assertTrue(s["fallback"])
        self.assertEqual(s["frames"], 121)

    def test_dropped_frames_count_as_jank_and_idle_gaps_are_ignored(self):
        gaps = [8.33] * 95 + [16.7] * 5          # 5 dropped frames in 100 intervals
        gaps += [500, 600]                        # idle pauses between flings: excluded
        s = bench.interval_stats(presents(gaps))
        self.assertEqual(s["jank_pct"], 5.0)
        self.assertEqual(s["p99"], 16.7)
        self.assertLess(s["fps"], 120.0)

    def test_too_few_frames(self):
        self.assertIsNone(bench.interval_stats([]))
        self.assertIsNone(bench.interval_stats(presents([])))
        self.assertIsNone(bench.interval_stats(presents([500])))  # one idle gap only


class ScrollStatsTests(unittest.TestCase):
    def test_app_layer_uses_frame_stats(self):
        frames = [(i * 8 * MS, 6 * MS, "None") for i in range(50)] + [(50 * 8 * MS, 20 * MS, "App Deadline Missed")]
        s = bench.scroll_stats("TX - com.x/MainActivity", frames)
        self.assertFalse(s["fallback"])
        self.assertAlmostEqual(s["jank_pct"], round(100 / 51, 2))
        self.assertEqual(s["p50"], 6.0)

    def test_sf_layer_uses_interval_stats(self):
        s = bench.scroll_stats(bench.SF_LAYER, presents([8.33] * 60))
        self.assertTrue(s["fallback"])
        self.assertEqual(s["jank_pct"], 0.0)

    def test_note_marks_fallback(self):
        self.assertIn("SurfaceFlinger", bench.SF_NOTE)
        self.assertIn("present-to-present", bench.SF_NOTE)


if __name__ == "__main__":
    unittest.main()

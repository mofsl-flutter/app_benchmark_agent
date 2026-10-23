"""Unit tests for the pure scoring in build_dashboard.py. Run: python3 -m unittest discover tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("RIISE_BENCH_HOME", tempfile.mkdtemp())

import benchlib as B  # noqa: E402
import build_dashboard as D  # noqa: E402

RUBRIC = D.load_rubric()
WEIGHTS = B.load_weights()


class DashboardTests(unittest.TestCase):
    def test_band_limits(self):
        bands = RUBRIC["speed"]["bands_ms"]
        self.assertEqual([D.band(x, bands) for x in (400, 401, 1000, 9999, 10001)], [100, 70, 70, 30, 0])

    def test_confidence(self):
        self.assertEqual(D.confidence([500]), ("One", 0.0))
        self.assertEqual(D.confidence([100, 105, 110])[0], "High")
        self.assertEqual(D.confidence([100, 140])[0], "Medium")
        self.assertEqual(D.confidence([100, 110, 400])[0], "Low")

    def test_facts_and_holdings(self):
        rows = [{"app": "RISE", "metric": "F.pull_to_refresh", "value": "No", "timestamp": "1"},
                {"app": "RISE", "metric": "F.pull_to_refresh", "value": "yes", "timestamp": "2"},
                {"app": "RISE", "metric": "L3", "value": "300", "timestamp": "1"}]
        self.assertEqual(dict(D.read_facts(rows)), {"RISE": {"pull_to_refresh": True}})
        self.assertEqual(D.parse_holdings("Riise=447, Groww: 22, Kotak Neo=0"), {"RISE": 447, "Groww": 22, "Kotak Neo": 0})

    def test_ux_scores(self):
        med = {"RISE": {"L3": 300, "L4": 800, "S5": 90, "O1": 70, "C2": 60},
               "Groww": {"L3": 1200, "S5": 55, "C2": 30}}
        runs = {"RISE": {"L3": [300, 310, 1000]}, "Groww": {"L3": [1200, 1250]}}
        facts = {"RISE": {"pin_on_resume": False, "pull_to_refresh": False}, "Groww": {"pin_on_resume": True, "pull_to_refresh": True}}
        ux = D.ux_scores(med, runs, facts, ["RISE", "Groww"], RUBRIC)
        self.assertEqual(ux["speed"], {"RISE": 85.0, "Groww": 30.0})
        self.assertEqual(ux["smooth"], {"RISE": 100, "Groww": 30})
        self.assertEqual(ux["offline"], {"RISE": 70})
        self.assertEqual(ux["friction"], {"RISE": 50, "Groww": 50})
        self.assertEqual(ux["battery"], {"RISE": 50.0, "Groww": 100.0})
        self.assertEqual(ux["reliability"], {"RISE": 70, "Groww": 100})  # 1000 > 3 x 310

    def test_actions_rescore_and_skip_bests(self):
        apps = ["RISE", "Groww", "Kite"]
        med = {"RISE": {"L3": 900, "R2": 300}, "Groww": {"L3": 400, "R2": 500}, "Kite": {"L3": 500, "R2": 600}}
        facts = {"RISE": {"pull_to_refresh": False}, "Groww": {"pull_to_refresh": True}, "Kite": {"pull_to_refresh": True}}
        acts, combined = D.actions(med, {}, facts, apps, WEIGHTS, RUBRIC)
        ids = [a["id"] for a in acts]
        self.assertIn("L3", ids)
        self.assertIn("pull_to_refresh", ids)
        self.assertNotIn("R2", ids)                    # RISE is already best
        l3 = next(a for a in acts if a["id"] == "L3")
        self.assertEqual(l3["to"], 450)                # median of the other apps
        self.assertTrue(all(a["gain"] > 0 for a in acts))
        self.assertEqual(combined["tech_rank"], 2)            # 450 ms is still slower than Groww on the 20-weight Loading category


if __name__ == "__main__":
    unittest.main()

"""Unit tests for the pure aggregation in build_report.py. Run: python3 -m unittest discover tests"""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("RIISE_BENCH_HOME", tempfile.mkdtemp())

import benchlib as B  # noqa: E402
import build_report as R  # noqa: E402


def row(app, metric, run, value, ts="2026-10-22T10:00:00", version="v1"):
    return {"app": app, "metric": metric, "run": run, "value": str(value), "num": float(value) if not isinstance(value, str) else None,
            "timestamp": ts, "module_version": version}


class AggregationTests(unittest.TestCase):
    module = {"name": "fno", "version": "v1", "rise": {"screen": "s", "list": "l", "detail": "d", "live_ticks": True, "account_sensitive": False},
              "skip": [], "offline_items": ["A", "B"], "data_items": ["C"]}

    def test_medians_runs_apps_and_items(self):
        rows = [row("RISE", "L3", 1, 100), row("RISE", "L3", 2, 300), row("RISE", "L3", 3, 200),
                row("RISE", "X4", 1, 5), row("RISE", "X4", 2, 9),
                {"app": "RISE", "metric": "O1.a", "run": 1, "value": "Yes", "num": None},
                {"app": "RISE", "metric": "O1.b", "run": 1, "value": "No", "num": None},
                {"app": "RISE", "metric": "D1.c", "run": 1, "value": "Partial", "num": None},
                row("Groww", "L3", 1, 50)]
        med = R.medians(rows, self.module, {"RISE", "Groww"})
        self.assertEqual(med["RISE"]["L3"], 200)      # median
        self.assertEqual(med["RISE"]["X4"], 7)        # X4 expects 5 runs, so it is a median like any other metric
        self.assertEqual(R.medians([row("RISE", "X1", 1, 3), row("RISE", "X1", 2, 8)], self.module, {"RISE"})["RISE"]["X1"], 8)  # single facts: latest run
        self.assertEqual(med["RISE"]["O1"], 50.0)     # (2*1 + 0) / (2*2)
        self.assertEqual(med["RISE"]["D1"], 50.0)
        self.assertEqual(med["Groww"]["L3"], 50)

    def test_item_score_excludes_na(self):
        self.assertEqual(R.item_score("O1", ["Yes", "N/A", "No"]), 50.0)
        self.assertIsNone(R.item_score("D1", ["N/A"]))

    def test_metric_scores_and_ranks(self):
        med = {"RISE": {"L3": 200, "S5": 60}, "Groww": {"L3": 100, "S5": 90}, "Kite": {"L3": 300}, "RISE UAT": {"L3": 50}}
        ms = R.metric_scores(med, ["RISE", "Groww", "Kite"])
        self.assertEqual(ms["L3"], {"RISE": 50.0, "Groww": 100.0, "Kite": 0.0})   # lower is better
        self.assertEqual(ms["S5"], {"RISE": 0.0, "Groww": 100.0})                 # higher is better
        self.assertNotIn("RISE UAT", ms["L3"])                                     # unranked apps never score
        cs = R.category_scores(ms, ["RISE", "Groww", "Kite"])
        self.assertEqual(cs["Loading Time"]["RISE"], 50.0)
        ov = R.overall(cs, B.DEFAULT_WEIGHTS, ["RISE", "Groww", "Kite"])
        self.assertEqual(R.rank_of(ov, "Groww"), 1)
        self.assertEqual(R.rank_of(ov, "RISE"), 2)
        self.assertIsNone(R.rank_of(ov, "Nobody"))

    def test_best_and_gap(self):
        med = {"RISE": {"L3": 200, "S5": 60}, "Groww": {"L3": 100, "S5": 90}}
        self.assertEqual(R.best_and_gap(med, "L3", ["RISE", "Groww"]), ("Groww", 100))
        self.assertEqual(R.best_and_gap(med, "S5", ["RISE", "Groww"]), ("Groww", 30))
        self.assertEqual(R.best_and_gap({"RISE": {"L3": 1}}, "L3", ["RISE"]), (None, None))

    def test_group_folders_latest_first(self):
        runs = [("fno", Path("/a"), [row("RISE", "L3", 1, 1, ts="2026-10-20T00:00:00")]),
                ("fno", Path("/b"), [row("RISE", "L3", 1, 1, ts="2026-10-22T00:00:00")])]
        by = R.group_folders(runs)
        self.assertEqual([f.name for f, _ in by["fno"]], ["b", "a"])

    def test_completeness_counts_version_mismatch(self):
        tmp = Path(tempfile.mkdtemp())
        rows = [row("RISE", "L3", 1, 1, version="old")]
        res = R.completeness(self.module, tmp, rows)
        self.assertEqual(res[0][0], "RISE")
        self.assertEqual(res[0][3], 1)



class ReviewFixTests(unittest.TestCase):
    """Regression tests for the findings of the 22 Oct review."""
    module = AggregationTests.module

    def test_medians_latest_row_wins_per_run(self):  # I2
        rows = [row("RISE", "U4", 1, 10, ts="2026-10-22T10:00:00"), row("RISE", "U4", 1, 10, ts="2026-10-22T10:05:00"),
                row("RISE", "U4", 2, 2, ts="2026-10-22T10:10:00"), row("RISE", "U4", 1, 4, ts="2026-10-22T11:00:00")]
        med = R.medians(rows, self.module, {"RISE"})
        self.assertEqual(med["RISE"]["U4"], 3)  # latest run-1 value 4 and run-2 value 2 -> median 3

    def test_app_scoped_multi_run_metric_uses_median(self):  # I3
        rows = [row("RISE", "X4", i, v) for i, v in enumerate([0, 0, 0, 0, 9], start=1)]
        self.assertEqual(R.medians(rows, self.module, {"RISE"})["RISE"]["X4"], 0)

    def test_module_apps_excludes_apps_without_screen(self):  # I1
        mod = dict(self.module, apps={"Groww": {"screen": "x"}, "Kite": {"screen": None}})
        rows = [row("RISE", "L3", 1, 1), row("Groww", "L3", 1, 1), row("Kite", "L3", 1, 1)]
        app_rows = [row("Kite", "L1", 1, 1), row("Dhan", "L1", 1, 1)]
        self.assertEqual(R.module_apps(mod, rows, app_rows), ["RISE", "Groww"])

    def test_coldstart_off_drops_l1_and_x4(self):
        app_rows = [row("RISE", "L1", 1, 900), row("RISE", "X4", 1, 3), row("RISE", "R1", 1, 400)]
        self.assertEqual(R.module_app_rows(self.module, app_rows), app_rows)                  # unset = on
        self.assertEqual(R.module_app_rows(dict(self.module, coldstart=True), app_rows), app_rows)
        kept = R.module_app_rows(dict(self.module, coldstart=False), app_rows)
        self.assertEqual([r["metric"] for r in kept], ["R1"])

    def test_coverage(self):  # I11
        cs = {"Loading Time": {"RISE": 50, "Groww": 60}, "RAM": {"Groww": 10}}
        cov = R.coverage(cs, B.DEFAULT_WEIGHTS, ["RISE", "Groww"])
        self.assertEqual(cov["RISE"], 20.0)
        self.assertEqual(cov["Groww"], 27.0)


class BenchFixTests(unittest.TestCase):
    def test_gesture_rendering_only_accepts_fractions(self):  # I7
        import bench
        self.assertEqual(bench.render_gesture("input tap 0.5 0.25", 1000, 2000), "input tap 500 500")
        self.assertEqual(bench.render_gesture("input swipe 0.5 0.8 0.5 0.2 300", 1000, 2000), "input swipe 500 1600 500 400 300")
        self.assertEqual(bench.render_gesture("input keyevent KEYCODE_BACK", 1000, 2000), "input keyevent KEYCODE_BACK")
        for bad in ("input tap 300 1400", "rm -rf /sdcard", "input text hello", "input tap 0.5", "input keyevent 66"):
            with self.assertRaises(ValueError):
                bench.render_gesture(bad, 1000, 2000)

    def test_black_fraction_parse(self):  # I8
        import bench
        out = ("[blackdetect @ 0x1] black_start:0 black_end:30.5 black_duration:30.5\n"
               "[blackdetect @ 0x1] black_start:40 black_end:60 black_duration:20\n")
        self.assertEqual(bench.parse_black_seconds(out), 50.5)
        self.assertEqual(bench.parse_black_seconds(""), 0.0)

    def test_developer_name_has_no_underscore(self):  # minor promoted
        self.assertEqual(B.safe_developer("anil_k"), "anil-k")
        self.assertEqual(B.results_dir("fno", "anil_k", "Pixel 8").name, "anil-k_Pixel-8")

    def test_resolve_app_in_benchlib(self):  # I10
        self.assertEqual(B.resolve_app("groww"), "Groww")
        self.assertEqual(B.resolve_app("Riise"), "RISE")
        with self.assertRaises(SystemExit):
            B.resolve_app("grow")

    def test_rise_uat_uses_rise_screen(self):  # I9
        mod = B.load_module("fno")
        self.assertEqual(B.app_screen(mod, "RISE UAT"), mod["rise"]["screen"])
        self.assertIsNone(B.app_screen(mod, "Kite"))

if __name__ == "__main__":
    unittest.main()

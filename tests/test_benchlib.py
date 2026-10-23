"""Unit tests for benchlib and the pure parsers in bench.py. Run: python3 -m unittest discover tests"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
os.environ["RIISE_BENCH_HOME"] = tempfile.mkdtemp()

import benchlib as B  # noqa: E402


class CatalogueTests(unittest.TestCase):
    def test_catalogue_size_and_unique_ids(self):
        ids = [m["id"] for m in B.METRIC_CATALOGUE]
        self.assertEqual(len(ids), 51)  # 50 + L16 (second detail screen, 23 Oct 2026)
        self.assertEqual(len(set(ids)), 51)
        for new in ("L14", "L15", "S7", "U4", "U5", "R9", "X4"):
            self.assertIn(new, ids)

    def test_sdk_columns_do_not_collide(self):
        cols = [m["scope"][2] for m in B.METRIC_CATALOGUE if m["scope"][0] == "app" and m["scope"][1] == B.SDK]
        self.assertEqual(cols, ["B", "C", "D", "E"])

    def test_weights_cover_every_category(self):
        self.assertEqual(set(B.DEFAULT_WEIGHTS), set(B.CATEGORIES))
        self.assertEqual(sum(B.DEFAULT_WEIGHTS.values()), 100)

    def test_render_uses_module_words(self):
        mod = {"name": "fno", "rise": {"screen": "F&O tab", "list": "F&O movers", "detail": "contract"}}
        self.assertEqual(B.render(B.METRICS["L3"]["name"], mod), "F&O tab → F&O movers fully rendered (first open, Medium account)")
        self.assertEqual(B.render("{detail}", None), "the detail screen")


class ApplicabilityTests(unittest.TestCase):
    def mod(self, **rise):
        base = {"screen": "s", "list": "l", "detail": "d", "live_ticks": False, "account_sensitive": False}
        base.update(rise)
        return {"name": "x", "rise": base, "skip": []}

    def test_phone_metrics_only_under_app_scope(self):
        app = {"name": B.APP_SCOPE}
        ids = [m["id"] for m in B.module_metrics(app)]
        self.assertEqual(ids, B.PHONE_METRICS)
        self.assertIn("X4", ids)
        self.assertNotIn("L1", [m["id"] for m in B.module_metrics(self.mod())])

    def test_live_and_account_flags(self):
        quiet = [m["id"] for m in B.module_metrics(self.mod())]
        for mid in ("U1", "U4", "U5", "C1", "L9", "S6"):
            self.assertNotIn(mid, quiet)
        live = [m["id"] for m in B.module_metrics(self.mod(live_ticks=True, account_sensitive=True))]
        for mid in ("U4", "U5", "C4", "L10", "S6", "S7", "L14", "L15", "R9"):
            self.assertIn(mid, live)

    def test_skip_list(self):
        m = self.mod()
        m["skip"] = ["L14"]
        self.assertFalse(B.metric_applies("L14", m)[0])


class ModuleTests(unittest.TestCase):
    def test_version_changes_only_with_versioned_keys(self):
        m = {"name": "t", "rise": {"screen": "A"}, "apps": {}, "notes": "x"}
        v1 = B.module_version(m)
        m["notes"] = "changed"
        self.assertEqual(v1, B.module_version(m))
        m["rise"]["screen"] = "B"
        self.assertNotEqual(v1, B.module_version(m))
        self.assertEqual(len(v1), 8)

    def test_scroll_fracs_default_and_override(self):
        m = {"scroll": dict(B.DEFAULT_SCROLL, per_app={"Groww": {"y_to_frac": 0.4}})}
        self.assertEqual(B.scroll_fracs(m, "Kite"), (0.5, 0.75, 0.30))
        self.assertEqual(B.scroll_fracs(m, "Groww"), (0.5, 0.75, 0.4))

    def test_every_shipped_module_loads(self):
        names = B.list_modules()
        self.assertIn("portfolio", names)
        self.assertIn(B.APP_SCOPE, names)
        for n in names:
            m = B.load_module(n)
            self.assertEqual(len(m["version"]), 8, n)
            if n != B.APP_SCOPE:
                self.assertTrue(m["rise"]["screen"], n)


class ResultsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.module = {"name": "fno", "version": "abcd1234", "rise": {"screen": "F&O", "list": "l", "detail": "d",
                       "live_ticks": True, "account_sensitive": False}, "skip": [],
                       "offline_items": ["Stale label"], "data_items": ["Indices strip"]}
        self.meta = {"app": "Riise", "pkg": "com.mosl.mobile", "version": "6.2", "model": "samsung SM-S911B",
                     "android": "16", "ram_gb": 7.5, "developer": "vivek"}
        self.folder = B.results_dir("fno", "vivek", "samsung SM-S911B", base=self.tmp)

    def test_folder_name_is_safe(self):
        self.assertTrue(str(self.folder).endswith("fno/vivek_samsung-SM-S911B"))

    def test_append_then_read_and_state(self):
        rows = [{"metric": "S1", "run": 1, "value": 2.5, "note": ""},
                {"metric": "S1", "run": 2, "value": None, "note": "no frames"},
                {"metric": "O1.stale-label", "run": 1, "value": "Partial", "note": "", "source": "manual"}]
        B.append_rows(self.folder, rows, self.meta, self.module)
        got = B.read_runs(self.folder / "runs.csv")
        self.assertEqual([r["app"] for r in got], ["RISE"] * 3)
        self.assertEqual(got[0]["unit"], "%")
        self.assertEqual(got[0]["num"], 2.5)
        self.assertIsNone(got[1]["num"])
        self.assertEqual(got[2]["source"], "manual")
        self.assertEqual(B.runs_done(self.folder, "RISE", "S1"), [1])  # None values don't count
        self.assertEqual(B.next_run(self.folder, "RISE", "S1"), 2)

    def test_missing_counts_items_and_runs(self):
        B.append_rows(self.folder, [{"metric": "S1", "run": 1, "value": 1, "note": ""}], self.meta, self.module)
        gaps = B.missing(self.module, self.folder, "RISE")
        self.assertEqual(gaps["S1"], (1, 5))
        self.assertEqual(gaps["O1.stale-label"], (0, 1))
        self.assertEqual(gaps["U4"], (0, 3))
        self.assertNotIn("L1", gaps)

    def test_all_runs_skips_conflict_copies(self):
        B.append_rows(self.folder, [{"metric": "S1", "run": 1, "value": 1, "note": ""}], self.meta, self.module)
        bad = Path(self.tmp) / "fno" / "vivek_x (conflicted copy)"
        bad.mkdir(parents=True)
        (bad / "runs.csv").write_text("x\n")
        found = B.all_runs(self.tmp)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0][0], "fno")

    def test_env_roundtrip(self):
        B.append_env(self.folder, {"timestamp": "t", "module": "fno", "battery_pct": 80})
        self.assertEqual(B.read_env(self.folder)[0]["battery_pct"], "80")

    def test_me_file(self):
        B.write_me("Vivek Dubey")
        self.assertEqual(B.get_developer(), "Vivek-Dubey")


class BenchParserTests(unittest.TestCase):
    def test_parsers(self):
        import bench
        self.assertEqual(bench.parse_total_time("ThisTime: 1\nTotalTime: 842\n"), 842)
        mem = ("App Summary\n   Java Heap:    18800\n   Native Heap:  42800\n   Code:  40200\n"
               "   Graphics:  60900\n TOTAL PSS:   182500 \n  WebViews: 1\n")
        d = bench.parse_meminfo(mem)
        self.assertEqual(d["pss_mb"], 178.2)
        self.assertEqual(d["java_mb"], 18.4)
        self.assertEqual(d["webviews"], 1)
        self.assertEqual(bench.parse_pss_mb(mem), 178.2)
        log = ("I/art: Long monitor contention with owner main (1) at void a.b() waiters=0 in x for 960ms\n"
               "W/other: Long monitor contention ... for 12ms\n")
        self.assertEqual(bench.parse_contention(log), (2, 960))
        self.assertEqual(bench.parse_contention(""), (0, 0))
        mp = ("frame=  120 fps=0.0 q=-0.0 size=N/A time=00:00:10.00\n"
              "frame=  600 fps=0.0 q=-0.0 Lsize=N/A time=00:01:00.00\n")
        self.assertEqual(bench.parse_frame_count(mp), 600)
        self.assertEqual(bench.parse_nb_frames("4200\n"), 4200)
        self.assertEqual(bench.identical_pct(4200, 600), 85.7)
        self.assertIsNone(bench.identical_pct(0, 600))

    def test_frame_stats_idle_rate(self):
        import bench
        frames = [(i * 30_000_000, 5_000_000, "None") for i in range(60)]  # 60 frames over ~1.8 s
        self.assertEqual(bench.idle_rate(frames, 60), 1.0)


if __name__ == "__main__":
    unittest.main()

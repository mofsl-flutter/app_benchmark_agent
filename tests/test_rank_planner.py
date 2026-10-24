"""Tests for the rank-impact layer of the execution planner. Run: python3 -m unittest discover tests"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
TOOLS = HERE / "execution-plan" / "tools"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(TOOLS))

import build_dashboard as D  # noqa: E402
import rank_impact as RI  # noqa: E402

# RISE trails on opening (L3), re-open (L4), memory (R2) and idle CPU (C1); four apps.
SNAP = {
    "source": "test",
    "module": "test",
    "ranked": ["RISE", "Groww", "Kite", "Angel One"],
    "medians": {
        "RISE": {"L3": 900.0, "L4": 450.0, "R2": 1000.0, "C1": 40.0, "S5": 58.0},
        "Groww": {"L3": 500.0, "L4": 300.0, "R2": 400.0, "C1": 15.0, "S5": 60.0},
        "Kite": {"L3": 380.0, "L4": 130.0, "R2": 350.0, "C1": 12.0, "S5": 61.0},
        "Angel One": {"L3": 700.0, "L4": 500.0, "R2": 450.0, "C1": 25.0, "S5": 59.0},
    },
    "runs": {},
    "facts": {"RISE": {"pull_to_refresh": False}, "Groww": {"pull_to_refresh": True},
              "Kite": {"pull_to_refresh": True}, "Angel One": {"pull_to_refresh": True}},
}

SECTIONS = {
    "A": [{"id": "A1", "title": "Show cached list first", "effort": "M", "risk": "Medium"},
          {"id": "A2", "title": "Keep tab alive", "effort": "S", "risk": "Low"},
          {"id": "A3", "title": "Add pull-to-refresh", "effort": "S", "risk": "Low"}],
    "B": [{"id": "B1", "title": "Lazy WebView", "effort": "L", "risk": "High"},
          {"id": "B2", "title": "Stop idle shimmer", "effort": "S", "risk": "Low"}],
}

IMPACT = {"goal": {"technical_rank": 3, "user_rank": 3}, "partial": 0.75, "levers": [
    {"id": "open", "title": "Faster open", "changes": ["A1"], "effects": [{"metric": "L3", "after": 400}], "chance": "High", "basis": "A1"},
    {"id": "reopen", "title": "Faster re-open", "changes": ["A2"], "effects": [{"metric": "L4", "after": 140}], "chance": "High", "basis": "A2"},
    {"id": "ptr", "title": "Pull-to-refresh", "changes": ["A3"], "effects": [{"metric": "L6", "after": 550}],
     "facts": {"pull_to_refresh": True}, "chance": "High", "basis": "A3"},
    {"id": "memory", "title": "Cut memory", "changes": ["B1"], "effects": [{"metric": "R2", "after": 380}], "chance": "Medium", "basis": "B1"},
    {"id": "idle", "title": "Stop idle redraws", "changes": ["B2"], "effects": [{"metric": "C1", "after": 14}], "chance": "Medium", "basis": "B2"},
]}

ROADMAP = {"title": "Test roadmap", "developers": 2, "scope_in": ["Test screen"], "scope_out": ["iOS"],
           "phases": [
               {"title": "Phase 1", "start": "2026-10-26", "end": "2026-11-06", "levers": ["reopen", "ptr", "idle"],
                "gate": {"date": "2026-11-09", "pass": "User feel top 2"}},
               {"title": "Phase 2", "start": "2026-11-09", "end": "2026-12-04", "levers": ["open", "memory"],
                "gate": {"date": "2026-12-07", "pass": "Technical top 2"}}],
           "risks": [{"risk": "Memory cut falls short", "effect": "Technical #3", "fallback": "Idle lever first"}]}


def run(*args):
    return subprocess.run([sys.executable, "-I", *map(str, args)], capture_output=True, text=True)


def write_plan(folder, code_path=None):
    folder.mkdir(parents=True, exist_ok=True)
    meta = {"title": "Test Change Plan", "app": "RISE", "subject": "Test screen", "module_path": "packages/mo_test", "date": "23 Oct 2026"}
    if code_path:
        meta["code_root"] = str(code_path)
    (folder / "meta.json").write_text(json.dumps(meta))
    for letter, chs in SECTIONS.items():
        full = [dict(c, categories=["FE"], summary="s", current="c", after_improvement="a", risk_reason="r",
                     files=[{"path": "packages/mo_test/lib/a.dart", "lines": "1-2"}]) for c in chs]
        (folder / f"section-{letter}.json").write_text(json.dumps({"section": letter, "title": letter, "changes": full}))
    (folder / "impact.json").write_text(json.dumps(IMPACT))
    (folder / "roadmap.json").write_text(json.dumps(ROADMAP))
    (folder / "snapshot.json").write_text(json.dumps(SNAP))


class ScoringTests(unittest.TestCase):
    def setUp(self):
        self.sc = RI.Scorer(SNAP, "RISE")

    def test_baseline_matches_the_dashboard_scoring(self):
        import benchlib as B
        sc = D.scorecards(SNAP["medians"], SNAP["runs"], SNAP["facts"], SNAP["ranked"], B.load_weights(), D.load_rubric())
        self.assertEqual(self.sc.base["technical"], sc["tech"]["RISE"])
        self.assertEqual(self.sc.base["user_rank"], sc["ux_rank"]["RISE"])
        self.assertEqual(self.sc.base["technical_rank"], 4)

    def test_scan_lists_every_gap_sorted_by_gain(self):
        gaps = RI.scan(SNAP, "RISE", self.sc)
        ids = [g["metric"] for g in gaps]
        for m in ("L3", "L4", "R2", "C1", "S5", "fact:pull_to_refresh"):
            self.assertIn(m, ids)
        gains = [g["gain"] for g in gaps]
        self.assertEqual(gains, sorted(gains, reverse=True))

    def test_partial_delivery_moves_part_way_and_never_backwards(self):
        lv = {"id": "x", "effects": [{"metric": "L3", "after": 500}]}
        sm, _ = RI.apply_levers(SNAP, "RISE", [lv], {"x": 0.5})
        self.assertEqual(sm["L3"], 700)
        worse = {"id": "y", "effects": [{"metric": "L3", "after": 1200}]}
        sm, _ = RI.apply_levers(SNAP, "RISE", [worse])
        self.assertEqual(sm["L3"], 900)

    def test_a_missing_measurement_appears_at_its_value(self):
        sm, sf = RI.apply_levers(SNAP, "RISE", [IMPACT["levers"][2]])
        self.assertEqual(sm["L6"], 550)
        self.assertEqual(sf, {"pull_to_refresh": True})


class PlanTests(unittest.TestCase):
    def setUp(self):
        changes = {c["id"]: c for chs in SECTIONS.values() for c in chs}
        self.out = RI.plan(SNAP, "RISE", IMPACT, changes, ROADMAP)

    def test_minimum_and_robust_sets_meet_the_goal(self):
        self.assertTrue(self.out["reachable"])
        m = self.out["minimum"]
        self.assertLessEqual(m["technical_rank"], 3)
        self.assertLessEqual(m["user_rank"], 3)
        if self.out["robust"]:
            p = self.out["robust"]["at_partial"]
            self.assertLessEqual(p["technical_rank"], 3)
            self.assertLessEqual(p["user_rank"], 3)
        self.assertEqual(self.out["sets_scored"], 2 ** len(IMPACT["levers"]))

    def test_needed_levers_have_a_break_even_and_dropping_them_misses(self):
        for lv in self.out["levers"]:
            if lv.get("needed"):
                self.assertIsNotNone(lv["break_even"])
                self.assertTrue(0 < lv["break_even"] <= 1)
                w = lv["without"]
                self.assertTrue(w["technical_rank"] > 3 or w["user_rank"] > 3)

    def test_every_lever_of_the_minimum_set_has_a_real_break_even(self):
        sc = RI.Scorer(SNAP, "RISE")
        by = {lv["id"]: lv for lv in IMPACT["levers"]}
        chosen = [by[i] for i in self.out["minimum"]["levers"]]
        for lv in chosen:
            be = RI.break_even(sc, SNAP, "RISE", chosen, lv["id"], IMPACT["goal"])
            self.assertTrue(0 < be <= 1, (lv["id"], be))  # a minimum set has no spare lever
            partial = RI.evaluate(sc, SNAP, "RISE", chosen, {lv["id"]: max(0.0, be - 0.05)})
            self.assertFalse(RI.meets(partial, IMPACT["goal"]))

    def test_phases_are_cumulative_and_end_at_the_goal(self):
        ph = self.out["phases"]
        self.assertEqual(len(ph), 2)
        self.assertEqual(ph[1]["levers"], ["reopen", "ptr", "idle", "open", "memory"])
        self.assertTrue(ph[-1]["meets"])

    def test_unreachable_goal_is_reported(self):
        changes = {c["id"]: c for chs in SECTIONS.values() for c in chs}
        small = dict(IMPACT, goal={"technical_rank": 1, "user_rank": 1}, levers=[IMPACT["levers"][4]])
        out = RI.plan(SNAP, "RISE", small, changes)
        self.assertFalse(out["reachable"])
        self.assertIsNone(out["recommended"])

    def test_weakest_app_note(self):
        changes = {c["id"]: c for chs in SECTIONS.values() for c in chs}
        weak = dict(IMPACT, levers=[{"id": "mem", "changes": ["B1"], "effects": [{"metric": "R2", "after": 470}]}])
        out = RI.plan(SNAP, "RISE", weak, changes)
        self.assertTrue(out["levers"][0]["notes"])


class EndToEndTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        write_plan(self.data)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_plan_check_build(self):
        r = run(TOOLS / "rank_impact.py", "plan", self.data)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue((self.data / "rank.json").exists())
        r = run(TOOLS / "check_plan.py", self.data)
        self.assertIn("0 errors", r.stdout, r.stdout)
        r = run(TOOLS / "build_plan.py", self.data, self.tmp / "site")
        self.assertEqual(r.returncode, 0, r.stderr)
        page = (self.tmp / "site" / "roadmap.html").read_text()
        self.assertIn("Impact after each phase", page)
        self.assertIn('href="roadmap.html"', (self.tmp / "site" / "index.html").read_text())

    def test_stale_rank_json_is_an_error(self):
        run(TOOLS / "rank_impact.py", "plan", self.data)
        imp = json.loads((self.data / "impact.json").read_text())
        imp["levers"][0]["effects"][0]["after"] = 450
        (self.data / "impact.json").write_text(json.dumps(imp))
        r = run(TOOLS / "check_plan.py", self.data)
        self.assertIn("rank.json is older", r.stdout)
        self.assertEqual(r.returncode, 1)

    def test_recommended_lever_missing_from_roadmap_is_an_error(self):
        run(TOOLS / "rank_impact.py", "plan", self.data)
        rank = json.loads((self.data / "rank.json").read_text())
        rec = rank[rank["recommended"]]["levers"]
        road = json.loads((self.data / "roadmap.json").read_text())
        road["phases"][1]["levers"] = [x for x in road["phases"][1]["levers"] if x not in rec] or []
        road["phases"][0]["levers"] = [x for x in road["phases"][0]["levers"] if x not in rec]
        (self.data / "roadmap.json").write_text(json.dumps(road))
        run(TOOLS / "rank_impact.py", "plan", self.data)
        r = run(TOOLS / "check_plan.py", self.data)
        self.assertIn("is in no phase", r.stdout)


class CheckerRuleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.data = self.tmp / "data"
        write_plan(self.data)
        run(TOOLS / "rank_impact.py", "plan", self.data)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def edit_change(self, **fields):
        p = self.data / "section-A.json"
        s = json.loads(p.read_text())
        s["changes"][0].update(fields)
        p.write_text(json.dumps(s))
        run(TOOLS / "rank_impact.py", "plan", self.data)

    def test_competitor_names_in_any_case_are_errors(self):
        self.edit_change(summary="Same as Sahi and zerodha do.")
        out = run(TOOLS / "check_plan.py", self.data).stdout
        self.assertIn("'SAHI'", out)
        self.assertIn("'Zerodha'", out)

    def test_rank_wording_is_an_error_in_engineering_files(self):
        self.edit_change(summary="This takes us to the top 3.")
        r = run(TOOLS / "check_plan.py", self.data)
        self.assertIn("ERROR section-A.json: rank wording", r.stdout)

    def test_code_that_does_not_match_the_file_is_an_error(self):
        code = self.tmp / "repo"
        (code / "packages/mo_test/lib").mkdir(parents=True)
        (code / "packages/mo_test/lib/a.dart").write_text("void main() {\n  runApp(const App());\n}\n")
        self.edit_change(before_code={"path": "packages/mo_test/lib/a.dart", "lines": "1-3", "code": "void main() {\n  runApp(App());\n}"})
        r = run(TOOLS / "check_plan.py", self.data, "--code-root", code)
        self.assertIn("ERROR A1: 1 before_code line(s) not found", r.stdout)
        r = run(TOOLS / "check_plan.py", self.data, "--code-root", self.tmp / "nowhere")
        self.assertIn("ERROR A1: before_code file not found", r.stdout)

    def test_package_rules(self):
        (self.data / "summary.json").write_text(json.dumps({"title": "S", "package": {"plan": [
            {"owner": "Dev 1", "rows": [{"when": "Day 1", "ids": ["B1", "A2"], "what": "x"}]}]}}))
        out = run(TOOLS / "check_plan.py", self.data).stdout
        self.assertIn("B1 is High risk", out)
        self.assertIn("B1 has effort L", out)
        self.assertIn("about 7.5 days of work in 1 day", out)

    def test_absolute_paths_under_code_root_become_relative(self):
        code = self.tmp / "repo"
        write_plan(self.data, code_path=code)
        self.edit_change(files=[{"path": str(code / "packages/mo_test/lib/a.dart"), "lines": "1-2"}])
        run(TOOLS / "build_plan.py", self.data, self.tmp / "site")
        files = (self.tmp / "site" / "files.html").read_text()
        self.assertNotIn(str(code), files)
        self.assertIn("packages/mo_test/lib/a.dart", files)


if __name__ == "__main__":
    unittest.main()

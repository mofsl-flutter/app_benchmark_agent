"""Tests for the execution-plan checker and generator. Run: python3 -m unittest discover tests"""
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
EXAMPLE = HERE / "execution-plan" / "examples" / "quote"
CHECK = HERE / "execution-plan" / "tools" / "check_plan.py"
BUILD = HERE / "execution-plan" / "tools" / "build_plan.py"


def run(*args):
    return subprocess.run([sys.executable, "-I", *map(str, args)], capture_output=True, text=True)


class ExecutionPlanTests(unittest.TestCase):
    def test_example_passes_the_checker(self):
        r = run(CHECK, EXAMPLE)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("0 errors", r.stdout)

    def test_example_builds_all_pages_without_broken_links(self):
        out = tempfile.mkdtemp()
        try:
            r = run(BUILD, EXAMPLE, out)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            pages = {os.path.basename(p) for p in glob.glob(os.path.join(out, "*.html"))}
            for p in ("index.html", "files.html", "teams.html", "risk.html", "full-report.html",
                      "summary.html", "optimized-plan.html", "most-preferred-plan.html", "section-a.html"):
                self.assertIn(p, pages)
            ids = set()
            for p in pages:
                ids |= {(p, m) for m in re.findall(r'id="([^"]+)"', open(os.path.join(out, p), encoding="utf-8").read())}
            broken = []
            for p in pages:
                for href, anchor in re.findall(r'href="([^"#:]*\.html)(?:#([^"]+))?"', open(os.path.join(out, p), encoding="utf-8").read()):
                    if href not in pages or (anchor and (href, anchor) not in ids):
                        broken.append((p, href, anchor))
            self.assertEqual(broken, [])
            pref = open(os.path.join(out, "most-preferred-plan.html"), encoding="utf-8").read()
            self.assertNotRegex(pref, r"developer-days")
        finally:
            shutil.rmtree(out, ignore_errors=True)

    def test_checker_flags_competitor_names_and_bad_ids(self):
        d = tempfile.mkdtemp()
        try:
            shutil.copy(EXAMPLE / "meta.json", d)
            sec = json.load(open(EXAMPLE / "section-A.json", encoding="utf-8"))
            sec["changes"] = sec["changes"][:2]
            sec["changes"][0]["summary"] += " Groww does this better."
            sec["changes"][1]["id"] = "A5"
            json.dump(sec, open(os.path.join(d, "section-A.json"), "w", encoding="utf-8"))
            for c in sec["changes"]:
                c["depends_on"] = []
            json.dump(sec, open(os.path.join(d, "section-A.json"), "w", encoding="utf-8"))
            r = run(CHECK, d)
            self.assertEqual(r.returncode, 1)
            self.assertIn("Groww", r.stdout)
            self.assertIn("out of sequence", r.stdout)
        finally:
            shutil.rmtree(d, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()

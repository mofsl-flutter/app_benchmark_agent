"""Check the execution-plan data folder before building the pages.

Usage: python3 execution-plan/tools/check_plan.py <data_dir> [--code-root <repo root>] [--apps apps.json]

Checks:
  - every JSON file parses, and meta.json plus at least one section-*.json exist
  - section ids run A1, A2, ... with no gaps; categories, risk and effort values are valid
  - every Product change has a product_decision
  - depends_on and the ids used in summary / optimized / preferred exist
  - preferred.json uses FE / FE-Shared changes only and carries no effort or time wording
  - plan text names no competitor app (from apps.json) and uses no rank / "top N" wording
  - with --code-root: every before_code line (ignoring "// ..." trims) appears in the named file
    near the stated line range

Exit code 0 = clean, 1 = errors found (warnings alone do not fail).
"""
import argparse
import glob
import json
import os
import re
import sys

CATS = {"FE", "FE-Shared", "BE", "Product"}
RISKS = {"Low", "Medium", "High"}
EFFORTS = {"S", "M", "L"}
RANK_WORDS = re.compile(r"\b(top[ -]?\d|top three|ranked|ranks?\b|rank #|#\d of \d|competitor)", re.I)
TIME_WORDS = re.compile(r"\b(developer-days?|dev-days?|\d+(\.\d+)?\s*(days?|weeks?)|man-days?)\b", re.I)

errors, warnings = [], []


def err(msg):
    errors.append(msg)


def warn(msg):
    warnings.append(msg)


def load(path):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:  # noqa: BLE001
        err("%s: invalid JSON (%s)" % (os.path.basename(path), e))
        return None


def text_of(obj):
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(text_of(v) for k, v in obj.items() if k not in ("before_code", "after_code", "before", "after", "files", "path"))
    if isinstance(obj, list):
        return " ".join(text_of(v) for v in obj)
    return ""


def resolve(code_root, path):
    """All candidate files for a path; several when a dependency has more than one cached version."""
    m = re.match(r"^([a-z_0-9]+): (.*)$", path or "")
    if m:  # pub-cache / git dependency
        bases = [os.path.join(code_root, "packages", m.group(1))]
        bases += glob.glob(os.path.expanduser("~/.pub-cache/*/%s-*" % m.group(1)))
        bases += glob.glob(os.path.expanduser("~/.pub-cache/hosted/*/%s-*" % m.group(1)))
        return [c for c in (os.path.join(b, m.group(2)) for b in bases) if os.path.exists(c)]
    p = os.path.join(code_root, path)
    return [p] if os.path.exists(p) else []


def check_code(cid, code_root, bc):
    path, lines, code = bc.get("path"), str(bc.get("lines", "")), bc.get("code") or ""
    if not path or not code.strip():
        return
    cands = resolve(code_root, path)
    if not cands:
        warn("%s: before_code file not found under code root: %s" % (cid, path))
        return
    nums = [int(x) for x in re.findall(r"\d+", lines)]
    best = None
    for f in cands:
        with open(f, encoding="utf-8", errors="replace") as fh:
            src = fh.read().split("\n")
        lo, hi = (min(nums), max(nums)) if nums else (1, len(src))
        window = [l.strip() for l in src[max(0, lo - 6):hi + 5]]
        missing = []
        for line in code.split("\n"):
            s = line.strip()
            if not s or s.startswith("// ...") or s == "..." or s.startswith("//") and "…" in s:
                continue
            if not any(s == w or (len(s) > 12 and s in w) for w in window):
                missing.append(s)
        if best is None or len(missing) < len(best):
            best = missing
    missing = best
    if missing:
        warn("%s: %d before_code line(s) not found in %s:%s, e.g. %r" % (cid, len(missing), path, lines, missing[0][:70]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("data_dir")
    ap.add_argument("--code-root")
    ap.add_argument("--apps", default=os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "apps.json"))
    ap.add_argument("--target-app", default="RISE", help="the app the plan is for; its name is allowed in the text")
    a = ap.parse_args()
    d = a.data_dir

    meta = load(os.path.join(d, "meta.json")) if os.path.exists(os.path.join(d, "meta.json")) else err("meta.json missing")
    sec_files = sorted(glob.glob(os.path.join(d, "section-*.json")))
    if not sec_files:
        err("no section-*.json files")
    by_id = {}
    for sf in sec_files:
        s = load(sf)
        if not s:
            continue
        letter = s.get("section") or os.path.basename(sf)[8:9]
        chs = s.get("changes") or []
        if not chs:
            err("%s: no changes" % os.path.basename(sf))
        for n, c in enumerate(chs, 1):
            cid = c.get("id", "?")
            if cid != "%s%d" % (letter, n):
                err("%s: id %s out of sequence (expected %s%d)" % (os.path.basename(sf), cid, letter, n))
            if cid in by_id:
                err("duplicate id %s" % cid)
            by_id[cid] = c
            cats = set(c.get("categories") or [])
            if not cats or not cats <= CATS:
                err("%s: bad categories %s" % (cid, sorted(cats)))
            if c.get("risk") not in RISKS:
                err("%s: bad risk %r" % (cid, c.get("risk")))
            if c.get("effort") not in EFFORTS:
                err("%s: bad effort %r" % (cid, c.get("effort")))
            if "Product" in cats and not c.get("product_decision"):
                err("%s: Product change without product_decision" % cid)
            for k in ("title", "summary", "current", "after_improvement", "risk_reason"):
                if not c.get(k):
                    warn("%s: empty %s" % (cid, k))
            if not c.get("files"):
                warn("%s: no files listed" % cid)
            if a.code_root and c.get("before_code"):
                check_code(cid, a.code_root, c["before_code"])
    for cid, c in by_id.items():
        for dep in c.get("depends_on") or []:
            if dep not in by_id:
                err("%s: depends_on unknown id %s" % (cid, dep))

    def ids_in(obj):
        out = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("ids", "later") and isinstance(v, list):
                    out += v
                else:
                    out += ids_in(v)
        elif isinstance(obj, list):
            for v in obj:
                out += ids_in(v)
        return out

    extras = {}
    for name in ("summary.json", "optimized.json", "preferred.json"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            extras[name] = load(p)
            for i in ids_in(extras[name] or {}):
                if i not in by_id:
                    err("%s: unknown id %s" % (name, i))

    pref = extras.get("preferred.json")
    if pref:
        for i in ids_in(pref):
            c = by_id.get(i)
            if c and not set(c.get("categories", [])) & {"FE", "FE-Shared"}:
                err("preferred.json: %s is not an FE change (%s)" % (i, c.get("categories")))
        t = text_of(pref)
        for m in TIME_WORDS.finditer(t):
            err("preferred.json: effort/time wording not allowed: %r" % m.group(0))
            break
    opt = extras.get("optimized.json")
    if opt:
        for it in opt.get("items", []):
            for i in it.get("ids", []):
                c = by_id.get(i)
                if c and "FE" not in c.get("categories", []):
                    warn("optimized.json: item %s uses %s, which is not tagged FE" % (it.get("n"), i))

    # competitor names / rank wording in plan text
    names = []
    try:
        with open(a.apps, encoding="utf-8") as f:
            names = [n for n in json.load(f) if not n.upper().startswith(a.target_app.upper())]
    except Exception:  # noqa: BLE001
        warn("apps.json not readable; competitor-name check skipped")
    texts = {"meta.json": text_of(meta or {})}
    for sf in sec_files:
        s = load(sf) or {}
        texts[os.path.basename(sf)] = text_of(s)
    for k, v in extras.items():
        texts[k] = text_of(v or {})
    for fname, t in texts.items():
        for n in names:
            if re.search(r"\b%s\b" % re.escape(n), t):
                err("%s: mentions competitor app %r (plans talk only about today vs after)" % (fname, n))
        m = RANK_WORDS.search(t)
        if m:
            warn("%s: rank-like wording %r — plans should not compare with other apps" % (fname, m.group(0)))

    for w in warnings:
        print("WARN  " + w)
    for e in errors:
        print("ERROR " + e)
    print("%d changes in %d sections · %d errors · %d warnings" % (len(by_id), len(sec_files), len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

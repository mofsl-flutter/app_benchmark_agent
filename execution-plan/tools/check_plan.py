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
    near the stated line range (an error: code is copied, never paraphrased)
  - the 2-4 day package: Low/Medium risk, effort S or M, every depends_on inside the package,
    and a warning when one owner's package is more work than their days
  - impact.json (levers), roadmap.json (phases) and rank.json: ids exist, metric ids are real,
    phases are dated in order, every lever of the recommended set is in a phase, and rank.json
    was computed from the current files (re-run rank_impact.py plan otherwise)
  - impact.json, roadmap.json and rank.json are the management layer: ranks and app names are
    allowed there and nowhere else

Exit code 0 = clean, 1 = errors found (warnings alone do not fail).
"""
import argparse
import datetime
import glob
import hashlib
import json
import os
import re
import sys

CATS = {"FE", "FE-Shared", "BE", "Product"}
RISKS = {"Low", "Medium", "High"}
EFFORTS = {"S", "M", "L"}
PKG_DAYS = {"S": 0.5, "M": 3, "L": 7}   # typical days, for the package load check only
CHANCES = {"High", "Medium", "Low"}
CASE_SENSITIVE_NAMES = {"Coin"}         # an ordinary word in lower case
EXTRA_NAMES = {"Kite": ["Zerodha"], "SAHI": ["Sahi"], "Kotak Neo": ["Kotak"], "Angel One": ["Angel Broking"]}
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
        err("%s: before_code file not found under code root: %s" % (cid, path))
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
        err("%s: %d before_code line(s) not found in %s:%s, e.g. %r" % (cid, len(missing), path, lines, missing[0][:70]))


def check_package(summary, by_id):
    """The 2-4 day package: small, safe, self-contained, and not more work than the days it names."""
    pkg = (summary or {}).get("package") or {}
    rows = [(g.get("owner", "?"), r) for g in pkg.get("plan", []) for r in g.get("rows", [])]
    ids = {i for _, r in rows for i in r.get("ids", [])}
    for i in sorted(ids):
        c = by_id.get(i)
        if not c:
            continue
        if c.get("risk") == "High":
            err("summary.json package: %s is High risk (the package takes Low or Medium only)" % i)
        if c.get("effort") == "L":
            err("summary.json package: %s has effort L (the package takes S or a short M)" % i)
        for dep in c.get("depends_on") or []:
            if dep not in ids:
                err("summary.json package: %s depends on %s, which is not in the package" % (i, dep))
    mine, days = {}, {}
    for owner, r in rows:
        if re.search(r"\b(BE|Platform|Product)\b", owner):
            continue
        days.setdefault(owner, set()).add(r.get("when"))
        mine.setdefault(owner, set()).update(r.get("ids", []))  # a change spread over two days counts once
    for owner, cids in mine.items():
        work = sum(PKG_DAYS.get(by_id.get(i, {}).get("effort"), 1) for i in cids)
        n = len(days[owner])
        if n and work > 1.5 * n:
            warn("summary.json package: %s has about %.1f days of work in %d day(s)" % (owner, work, n))


def _digest(d):
    """Same as rank_impact.digest over impact.json, roadmap.json and the sections."""
    h = hashlib.sha256()
    for p in [os.path.join(d, "impact.json"), os.path.join(d, "roadmap.json")] + sorted(glob.glob(os.path.join(d, "section-*.json"))):
        if os.path.exists(p):
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()[:16]


def _date(s, where):
    try:
        return datetime.date.fromisoformat(str(s))
    except ValueError:
        err("%s: %r is not a YYYY-MM-DD date" % (where, s))
        return None


def check_management(d, by_id):
    """impact.json, rank.json and roadmap.json, when present."""
    ip, rp, mp = (os.path.join(d, n) for n in ("impact.json", "rank.json", "roadmap.json"))
    if not os.path.exists(ip):
        if os.path.exists(mp):
            err("roadmap.json needs impact.json and rank.json (run rank_impact.py plan)")
        return
    impact = load(ip) or {}
    metrics = None
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        import benchlib  # noqa: PLC0415
        metrics = benchlib.METRICS
    except Exception:  # noqa: BLE001
        warn("benchlib not importable; metric ids in impact.json not checked")
    goal = impact.get("goal") or {}
    if not (goal.get("technical_rank") or goal.get("user_rank")):
        err("impact.json: goal needs technical_rank and/or user_rank")
    lever_ids = set()
    used = {}
    for lv in impact.get("levers", []):
        lid = lv.get("id")
        if not lid or lid in lever_ids:
            err("impact.json: missing or duplicate lever id %r" % lid)
        lever_ids.add(lid)
        if not lv.get("changes"):
            err("impact.json: lever %s lists no changes" % lid)
        for c in lv.get("changes", []):
            if c not in by_id:
                err("impact.json: lever %s names unknown change %s" % (lid, c))
            elif c in used:
                warn("impact.json: change %s is in levers %s and %s (its effect counts twice)" % (c, used[c], lid))
            used[c] = lid
        if not lv.get("effects") and not lv.get("facts"):
            err("impact.json: lever %s moves no measurement (effects) or fact" % lid)
        for e in lv.get("effects", []):
            if metrics is not None and e.get("metric") not in metrics:
                err("impact.json: lever %s: unknown metric id %r" % (lid, e.get("metric")))
            if not isinstance(e.get("after"), (int, float)):
                err("impact.json: lever %s: effect on %s needs a numeric 'after'" % (lid, e.get("metric")))
        if lv.get("chance", "Medium") not in CHANCES:
            err("impact.json: lever %s: chance must be High, Medium or Low" % lid)
        if not lv.get("basis"):
            warn("impact.json: lever %s has no basis (why the 'after' values are believable)" % lid)

    rank = load(rp) if os.path.exists(rp) else None
    if not rank:
        err("rank.json missing: run rank_impact.py plan %s" % d)
        return
    if rank.get("inputs") != _digest(d):
        err("rank.json is older than impact.json, roadmap.json or the sections: re-run rank_impact.py plan %s" % d)
    rec = rank.get(rank.get("recommended") or "", None) or {}
    if not rank.get("reachable"):
        warn("rank.json: the goal is not reachable with these levers; the roadmap must say so")

    if not os.path.exists(mp):
        warn("roadmap.json missing: the management page is not built")
        return
    road = load(mp) or {}
    placed = []
    prev_end = None
    for n, ph in enumerate(road.get("phases", []), 1):
        where = "roadmap.json phase %d" % n
        for lid in ph.get("levers", []):
            if lid not in lever_ids:
                err("%s: unknown lever %s" % (where, lid))
            placed.append(lid)
        s, e = _date(ph.get("start"), where), _date(ph.get("end"), where)
        if s and e and e < s:
            err("%s: ends before it starts" % where)
        if s and prev_end and s < prev_end:
            warn("%s: starts before the previous phase ends (fine only if they run in parallel)" % where)
        g = ph.get("gate") or {}
        if not g.get("pass"):
            err("%s: needs a gate with a pass mark (what the re-test must show)" % where)
        gd = _date(g.get("date"), where + " gate") if g.get("date") else None
        if gd and e and gd < e:
            err("%s: gate is dated before the phase ends" % where)
        prev_end = e or prev_end
        devs = road.get("developers")
        if devs and s and e:
            work_days = sum(1 for k in range((e - s).days + 1) if (s + datetime.timedelta(k)).weekday() < 5)
            need = sum(next((x["days"] for x in rank.get("levers", []) if x["id"] == lid), 0) for lid in ph.get("levers", []))
            if need > devs * work_days * 1.1:
                warn("%s: about %d engineer-days of work in %d working days for %d developer(s)" % (where, need, work_days, devs))
    for lid in rec.get("levers", []):
        if lid not in placed:
            err("roadmap.json: lever %s of the recommended set is in no phase" % lid)
    for k in ("scope_in", "risks"):
        if not road.get(k):
            warn("roadmap.json: empty %s" % k)


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
            reg = json.load(f)
        for n, v in reg.items():
            if n.upper().startswith(a.target_app.upper()):
                continue
            names.append(n)
            names += EXTRA_NAMES.get(n, [])
            if isinstance(v, dict):
                names += v.get("aliases", [])
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
            flags = 0 if n in CASE_SENSITIVE_NAMES else re.I
            if re.search(r"\b%s\b" % re.escape(n), t, flags):
                err("%s: mentions competitor app %r (plans talk only about today vs after)" % (fname, n))
        m = RANK_WORDS.search(t)
        if m:
            err("%s: rank wording %r — ranks belong in roadmap.json only; engineering pages compare today with after" % (fname, m.group(0)))

    check_package(extras.get("summary.json"), by_id)
    check_management(d, by_id)

    for w in warnings:
        print("WARN  " + w)
    for e in errors:
        print("ERROR " + e)
    print("%d changes in %d sections · %d errors · %d warnings" % (len(by_id), len(sec_files), len(errors), len(warnings)))
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())

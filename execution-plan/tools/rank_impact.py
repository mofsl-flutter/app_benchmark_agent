"""Rank impact: which changes move the target app on the two scorecards, and which set is enough.

Uses the same scoring as the module dashboard (build_dashboard.scorecards): Scorecard 1 technical
(weights.json) and Scorecard 2 user feel (ux_rubric.json). Nothing here is a new formula.

  scan      Before reading code: every measurement where the target app trails, its target (median
            of the other apps, or the best of them), and how much closing it moves both scores.
            Tells the planner where the rank actually is, so root-cause work starts there.
  plan      After the change plan: reads <data>/impact.json (levers = groups of change ids and the
            measurements they move), searches the lever sets and writes <data>/rank.json: the
            minimum set, a robust set that survives partial delivery, what each lever is worth,
            how much of each lever must land (break-even), and the scores after each roadmap phase.
  snapshot  Writes the per-app numbers the other commands score, as JSON, so a benchmark that is
            not a results folder of this repo (a workbook, a scorecard file) can be scored too.

Numbers come from either a results folder (--module + --results) or a snapshot (--snapshot).

  python3 -I execution-plan/tools/rank_impact.py scan --module funds --results results/funds/<dev>_<phone>
  python3 -I execution-plan/tools/rank_impact.py plan <plan>/data --snapshot <plan>/data/snapshot.json
  python3 -I execution-plan/tools/rank_impact.py snapshot --module funds --results results/funds/<dev>_<phone> --out <plan>/data/snapshot.json
"""
import argparse
import copy
import hashlib
import itertools
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import benchlib as B  # noqa: E402
import build_dashboard as D  # noqa: E402
import build_report as R  # noqa: E402

EFFORT_DAYS = {"S": 1, "M": 3, "L": 7}          # SCHEMA.md: S <= 1 day, M 2-4 days, L 1 week +
CHANCE = {"High": 0.9, "Medium": 0.6, "Low": 0.3}  # used only to rank sets by expected cost
RISK_ORDER = {"Low": 0, "Medium": 1, "High": 2}
EXHAUSTIVE_MAX = 12                               # 2^12 sets; above this a greedy search is used
DEFAULT_PARTIAL = 0.75


# ---------------------------------------------------------------- inputs

def load_results(module_name, folder):
    """Snapshot dict from a results folder of this repo (same selection as build_report --module)."""
    module = B.load_module(module_name)
    folder = Path(folder).resolve()
    rows = B.read_runs(folder / "runs.csv")
    if not rows:
        raise SystemExit(f"No runs.csv in {folder}")
    app_folder = folder.parent.parent / B.APP_SCOPE / folder.name
    app_rows = R.module_app_rows(module, B.read_runs(app_folder / "runs.csv"))
    apps = R.module_apps(module, rows, app_rows)
    registry = B.load_apps()
    ranked = [a for a in apps if registry.get(a, {}).get("ranked", True)]
    all_rows = rows + [r for r in app_rows if r["app"] in apps]
    med = R.medians(all_rows, module, set(apps))
    runs = D.run_values(all_rows, set(apps))
    facts = D.read_facts(rows)
    return {
        "source": str(folder.relative_to(ROOT)) if folder.resolve().is_relative_to(ROOT) else str(folder),
        "module": module_name,
        "ranked": ranked,
        "medians": {a: dict(med.get(a, {})) for a in ranked},
        "runs": {a: {m: list(v) for m, v in runs.get(a, {}).items()} for a in ranked},
        "facts": {a: dict(facts.get(a, {})) for a in ranked},
    }


def load_snapshot(path):
    with open(path, encoding="utf-8") as f:
        s = json.load(f)
    for k in ("ranked", "medians"):
        if k not in s:
            raise SystemExit(f"{path}: snapshot needs '{k}'")
    unknown = sorted({m for a in s["medians"].values() for m in a if m not in B.METRICS})
    if unknown:
        raise SystemExit(f"{path}: unknown metric ids {unknown} (use the ids in METRICS.md)")
    s.setdefault("runs", {})
    s.setdefault("facts", {})
    return s


def numbers(args):
    if args.snapshot:
        return load_snapshot(args.snapshot)
    if args.module and args.results:
        return load_results(args.module, args.results)
    raise SystemExit("give --snapshot <file>, or --module <name> with --results <folder>")


def target_app(snap, name=None):
    if name:
        if name not in snap["ranked"]:
            raise SystemExit(f"target app {name!r} is not among the ranked apps {snap['ranked']}")
        return name
    t = next((a for a in snap["ranked"] if B.is_rise(a)), None)
    if not t:
        raise SystemExit("no RISE app in the ranked apps; pass --target-app")
    return t


# ---------------------------------------------------------------- scoring (pure)

class Scorer:
    """Scores a snapshot with chosen values changed for the target app."""

    def __init__(self, snap, target, weights=None, rubric=None):
        self.snap, self.target = snap, target
        self.ranked = list(snap["ranked"])
        self.weights = weights or B.load_weights()
        self.rubric = rubric or D.load_rubric()
        self.base = self.score({}, {})

    def score(self, set_med, set_facts):
        med = copy.deepcopy(self.snap["medians"])
        runs = copy.deepcopy(self.snap.get("runs", {}))
        facts = copy.deepcopy(self.snap.get("facts", {}))
        t = self.target
        med.setdefault(t, {}).update(set_med)
        for m, v in set_med.items():
            if m in runs.get(t, {}):
                runs[t][m] = [v] * len(runs[t][m])  # a met target is a steady one, same run count
        facts.setdefault(t, {}).update(set_facts)
        sc = D.scorecards(med, runs, facts, self.ranked, self.weights, self.rubric)
        return {
            "technical": sc["tech"].get(t), "technical_rank": sc["tech_rank"].get(t),
            "user": sc["ux"].get(t), "user_rank": sc["ux_rank"].get(t),
            "tech_all": sc["tech"], "ux_all": sc["ux"],
        }


def short(res):
    return {k: res[k] for k in ("technical", "technical_rank", "user", "user_rank")}


def meets(res, goal):
    ok = True
    if goal.get("technical_rank"):
        ok &= res["technical_rank"] is not None and res["technical_rank"] <= goal["technical_rank"]
    if goal.get("user_rank"):
        ok &= res["user_rank"] is not None and res["user_rank"] <= goal["user_rank"]
    return ok


def margin(res, scores_key, rank_goal, target):
    """Points between the target app and the first app outside the goal rank (negative = short of it)."""
    allv = res[scores_key]
    v = allv.get(target)
    others = sorted((x for a, x in allv.items() if a != target and x is not None), reverse=True)
    if v is None or not rank_goal or len(others) < rank_goal:
        return None
    return round(v - others[rank_goal - 1], 1)


def nearest_rival(res, scores_key, rank_goal, target):
    allv = res[scores_key]
    others = sorted(((x, a) for a, x in allv.items() if a != target and x is not None), reverse=True)
    if not rank_goal or len(others) < rank_goal:
        return None
    x, a = others[rank_goal - 1]
    return {"app": a, "score": x}


# ---------------------------------------------------------------- scan

def scan(snap, target, scorer=None):
    """Every gap of the target app, closed one at a time, sorted by gain in both scores."""
    sc = scorer or Scorer(snap, target)
    med = snap["medians"]
    ranked = snap["ranked"]
    out = []
    for mid in sorted(med.get(target, {}), key=lambda m: (B.CATEGORIES.index(B.METRICS[m]["category"]), m)):
        tgt, best_app = D._target(med, mid, target, ranked)
        if tgt is None:
            continue
        res = sc.score({mid: tgt}, {})
        out.append({"metric": mid, "name": B.METRICS[mid]["name"], "category": B.METRICS[mid]["category"],
                    "unit": B.METRICS[mid]["unit"], "today": med[target][mid], "target": tgt, "best_app": best_app,
                    "hint": D.HINTS.get(mid, ""), **short(res)})
    facts = snap.get("facts", {}).get(target, {})
    if facts.get("pull_to_refresh") is False:
        others = sorted(med[a]["L6"] for a in ranked if a != target and "L6" in med.get(a, {}))
        set_med = {"L6": others[len(others) // 2]} if others else {}
        res = sc.score(set_med, {"pull_to_refresh": True})
        out.append({"metric": "fact:pull_to_refresh", "name": "Add pull-to-refresh", "category": "User feel",
                    "unit": "", "today": "no", "target": "yes", "best_app": None, "hint": D.HINTS.get("L6", ""), **short(res)})
    if facts.get("pin_on_resume") is True:
        res = sc.score({}, {"pin_on_resume": False})
        out.append({"metric": "fact:pin_on_resume", "name": "No PIN on resume", "category": "User feel",
                    "unit": "", "today": "yes", "target": "no", "best_app": None, "hint": "", **short(res)})
    b = sc.base
    for g in out:
        g["gain_technical"] = round((g["technical"] or 0) - (b["technical"] or 0), 1)
        g["gain_user"] = round((g["user"] or 0) - (b["user"] or 0), 1)
        g["gain"] = round(g["gain_technical"] + g["gain_user"], 1)
    out.sort(key=lambda g: -g["gain"])
    return out


# ---------------------------------------------------------------- plan

def load_plan_changes(data_dir):
    by_id = {}
    for p in sorted(Path(data_dir).glob("section-*.json")):
        with open(p, encoding="utf-8") as f:
            for c in json.load(f).get("changes", []):
                by_id[c.get("id")] = c
    return by_id


def lever_cost(lever, changes):
    """(effort days, highest risk, chance) of a lever from its changes and its own 'chance'."""
    cs = [changes[i] for i in lever.get("changes", []) if i in changes]
    days = sum(EFFORT_DAYS.get(c.get("effort"), 3) for c in cs) or EFFORT_DAYS["M"]
    risk = max((c.get("risk", "Medium") for c in cs), key=lambda r: RISK_ORDER.get(r, 1), default="Medium")
    chance = lever.get("chance", "Medium")
    return days, risk, chance


def apply_levers(snap, target, levers, frac=None):
    """set_med and set_facts with each lever delivering frac (per lever id) of its improvement."""
    frac = frac or {}
    base = snap["medians"].get(target, {})
    set_med, set_facts = {}, {}
    for lv in levers:
        f = frac.get(lv["id"], 1.0)
        for e in lv.get("effects", []):
            m, after = e["metric"], float(e["after"])
            now = set_med.get(m, base.get(m))
            if now is None:                       # not measured today (a missing feature): it appears at its value
                set_med[m] = after
                continue
            lower = B.METRICS[m]["better"] == "Lower"
            moved = now + (after - now) * f
            better = min(now, moved) if lower else max(now, moved)
            set_med[m] = round(better, 3)
        if f > 0:
            set_facts.update(lv.get("facts") or {})
    return set_med, set_facts


def evaluate(scorer, snap, target, levers, frac=None):
    sm, sf = apply_levers(snap, target, levers, frac)
    return scorer.score(sm, sf)


def search_sets(scorer, snap, target, levers, goal, partial, costs):
    """All lever sets (or a greedy path when there are many) with their result at full and at partial delivery."""
    ids = [lv["id"] for lv in levers]
    by = {lv["id"]: lv for lv in levers}
    seen = {}

    def run(combo):
        key = tuple(sorted(combo))
        if key not in seen:
            chosen = [by[i] for i in key]
            full = evaluate(scorer, snap, target, chosen)
            part = evaluate(scorer, snap, target, chosen, {i: partial for i in key}) if meets(full, goal) else None
            cost = sum(costs[i]["days"] for i in key)
            exp_cost = sum(costs[i]["days"] / CHANCE.get(costs[i]["chance"], 0.6) for i in key)
            seen[key] = {"levers": list(key), "full": full, "partial": part, "days": cost, "expected_days": round(exp_cost, 1),
                         "meets": meets(full, goal), "robust": bool(part and meets(part, goal))}
        return seen[key]

    if len(ids) <= EXHAUSTIVE_MAX:
        for n in range(len(ids) + 1):
            for combo in itertools.combinations(ids, n):
                run(combo)
        method = "exhaustive"
    else:  # greedy: add the lever with the best score gain per expected day until nothing helps
        chosen = []
        run(chosen)
        while True:
            cur = run(chosen)
            best, best_val = None, 0.0
            for i in ids:
                if i in chosen:
                    continue
                r = run(chosen + [i])
                gain = ((r["full"]["technical"] or 0) + (r["full"]["user"] or 0)) - \
                       ((cur["full"]["technical"] or 0) + (cur["full"]["user"] or 0))
                val = gain / (costs[i]["days"] / CHANCE.get(costs[i]["chance"], 0.6))
                if val > best_val:
                    best, best_val = i, val
            if not best:
                break
            chosen.append(best)
        for i in ids:  # also every single lever and every drop-one of the path
            run([i])
        for i in chosen:
            run([x for x in chosen if x != i])
        method = "greedy"
    return list(seen.values()), method


def break_even(scorer, snap, target, chosen, lever_id, goal, step=0.05):
    """Smallest share of lever_id's improvement (others in full) that still meets the goal; None if even 100 % fails."""
    if not meets(evaluate(scorer, snap, target, chosen), goal):
        return None
    lo = 0.0
    if meets(evaluate(scorer, snap, target, chosen, {lever_id: 0.0}), goal):
        return 0.0
    f = step
    while f < 1.0 + 1e-9:
        if meets(evaluate(scorer, snap, target, chosen, {lever_id: f}), goal):
            return round(f, 2)
        lo = f
        f += step
    return 1.0 if lo else None


def plan(snap, target, impact, changes, roadmap=None, scorer=None):
    goal = impact.get("goal") or {}
    partial = float(impact.get("partial", DEFAULT_PARTIAL))
    levers = impact.get("levers", [])
    sc = scorer or Scorer(snap, target)
    by = {lv["id"]: lv for lv in levers}
    costs = {}
    for lv in levers:
        d, r, ch = lever_cost(lv, changes)
        costs[lv["id"]] = {"days": d, "risk": r, "chance": ch}

    base = sc.base
    sets, method = search_sets(sc, snap, target, levers, goal, partial, costs)
    meeting = [s for s in sets if s["meets"]]
    robust = [s for s in meeting if s["robust"]]
    minimum = min(meeting, key=lambda s: (len(s["levers"]), s["expected_days"]), default=None)
    safest = min(robust, key=lambda s: (s["expected_days"], len(s["levers"])), default=None)
    everything = max(sets, key=lambda s: len(s["levers"]))
    recommended = safest or minimum

    def res_block(s):
        if not s:
            return None
        out = {"levers": s["levers"], "days": s["days"], "expected_days": s["expected_days"], **short(s["full"]),
               "margin_technical": margin(s["full"], "tech_all", goal.get("technical_rank"), target),
               "margin_user": margin(s["full"], "ux_all", goal.get("user_rank"), target),
               "rival_technical": nearest_rival(s["full"], "tech_all", goal.get("technical_rank"), target),
               "rival_user": nearest_rival(s["full"], "ux_all", goal.get("user_rank"), target)}
        if s["partial"]:
            out["at_partial"] = short(s["partial"])
        return out

    per_lever = []
    rec_ids = recommended["levers"] if recommended else []
    rec_levers = [by[i] for i in rec_ids]
    for lv in levers:
        i = lv["id"]
        alone = evaluate(sc, snap, target, [lv])
        row = {"id": i, "title": lv.get("title", i), "changes": lv.get("changes", []), **costs[i],
               "alone": short(alone),
               "gain_technical": round((alone["technical"] or 0) - (base["technical"] or 0), 1),
               "gain_user": round((alone["user"] or 0) - (base["user"] or 0), 1),
               "in_recommended": i in rec_ids, "in_minimum": bool(minimum and i in minimum["levers"])}
        notes = []
        for e in lv.get("effects", []):
            m = e["metric"]
            others = [snap["medians"][a][m] for a in snap["ranked"] if a != target and m in snap["medians"].get(a, {})]
            if not others:
                continue
            lower = B.METRICS[m]["better"] == "Lower"
            worst = max(others) if lower else min(others)
            if (lower and e["after"] >= worst) or (not lower and e["after"] <= worst):
                notes.append(f"{m} at {e['after']} is still the weakest of all apps, so it earns no technical points; "
                             f"it needs to be {'below' if lower else 'above'} {worst} to count.")
        row["notes"] = notes
        if i in rec_ids:
            without = evaluate(sc, snap, target, [x for x in rec_levers if x["id"] != i])
            row["without"] = short(without)
            row["needed"] = not meets(without, goal)
            row["break_even"] = break_even(sc, snap, target, rec_levers, i, goal)
        else:
            plus = evaluate(sc, snap, target, rec_levers + [lv])
            row["plus"] = short(plus)
        per_lever.append(row)

    phases = []
    phase_src = (roadmap or {}).get("phases") or []
    if not phase_src and rec_ids:  # suggested order: best gain per expected day first
        order = sorted(rec_ids, key=lambda i: -(
            (next(r for r in per_lever if r["id"] == i)["gain_technical"] + next(r for r in per_lever if r["id"] == i)["gain_user"])
            / (costs[i]["days"] / CHANCE.get(costs[i]["chance"], 0.6))))
        phase_src = [{"title": f"Step {n} · {by[i].get('title', i)}", "levers": [i]} for n, i in enumerate(order, 1)]
    done = []
    for ph in phase_src:
        done += [i for i in ph.get("levers", []) if i in by and i not in done]
        r = evaluate(sc, snap, target, [by[i] for i in done])
        phases.append({"title": ph.get("title", ""), "levers": list(done), **short(r),
                       "meets": meets(r, goal),
                       "margin_technical": margin(r, "tech_all", goal.get("technical_rank"), target),
                       "margin_user": margin(r, "ux_all", goal.get("user_rank"), target)})

    return {
        "target": target, "goal": goal, "partial": partial, "method": method, "sets_scored": len(sets),
        "today": {**short(base),
                  "technical_scores": base["tech_all"], "user_scores": base["ux_all"]},
        "minimum": res_block(minimum),
        "robust": res_block(safest),
        "recommended": "robust" if safest else ("minimum" if minimum else None),
        "everything": res_block(everything),
        "reachable": bool(minimum),
        "levers": per_lever,
        "phases": phases,
    }


def digest(*paths):
    h = hashlib.sha256()
    for p in paths:
        if p and os.path.exists(p):
            with open(p, "rb") as f:
                h.update(f.read())
    return h.hexdigest()[:16]


# ---------------------------------------------------------------- CLI

def fmt(v):
    return "–" if v is None else (f"{v:,.1f}" if isinstance(v, float) else str(v))


def cmd_scan(a):
    snap = numbers(a)
    t = target_app(snap, a.target_app)
    sc = Scorer(snap, t)
    gaps = scan(snap, t, sc)
    b = sc.base
    print(f"{t} today: technical {fmt(b['technical'])} (#{b['technical_rank']}), user feel {fmt(b['user'])} (#{b['user_rank']}) of {len(snap['ranked'])}")
    print(f"{'metric':<22}{'today':>10}{'target':>10}  tech        user        gain")
    for g in gaps:
        print(f"{g['metric']:<22}{fmt(g['today']):>10}{fmt(g['target']):>10}  "
              f"{fmt(g['technical']):>5} #{g['technical_rank']:<4} {fmt(g['user']):>5} #{g['user_rank']:<4} {g['gain']:+.1f}")
    if a.out:
        Path(a.out).write_text(json.dumps({"target": t, "today": short(b), "gaps": gaps}, indent=1, ensure_ascii=False))
        print(f"wrote {a.out}")


def cmd_plan(a):
    d = Path(a.data_dir)
    snap_path = a.snapshot or (str(d / "snapshot.json") if (d / "snapshot.json").exists() and not a.results else None)
    a.snapshot = snap_path
    snap = numbers(a)
    t = target_app(snap, a.target_app)
    impact_p = d / "impact.json"
    if not impact_p.exists():
        raise SystemExit(f"{impact_p} is missing (see SCHEMA.md, impact.json)")
    impact = json.loads(impact_p.read_text())
    roadmap_p = d / "roadmap.json"
    roadmap = json.loads(roadmap_p.read_text()) if roadmap_p.exists() else None
    changes = load_plan_changes(d)
    out = plan(snap, t, impact, changes, roadmap)
    out["source"] = snap.get("source", snap_path)
    out["inputs"] = digest(str(impact_p), str(roadmap_p), *sorted(str(p) for p in d.glob("section-*.json")))  # check_plan.py recomputes this
    (d / "rank.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    td = out["today"]
    print(f"{t} today: technical {fmt(td['technical'])} (#{td['technical_rank']}), user feel {fmt(td['user'])} (#{td['user_rank']}); "
          f"{out['sets_scored']} lever sets scored ({out['method']})")
    for k in ("minimum", "robust", "everything"):
        s = out[k]
        if s:
            print(f"  {k:<10} {', '.join(s['levers']) or '—'}: technical {fmt(s['technical'])} (#{s['technical_rank']}), "
                  f"user {fmt(s['user'])} (#{s['user_rank']}), ~{s['days']} engineer-days")
    if not out["reachable"]:
        print("  goal not reachable with these levers; see 'everything' for the best result")
    for p in out["phases"]:
        print(f"  after {p['title']}: technical #{p['technical_rank']} ({fmt(p['technical'])}), user #{p['user_rank']} ({fmt(p['user'])})"
              + ("  ✓ goal" if p["meets"] else ""))
    print(f"wrote {d / 'rank.json'}")


def cmd_snapshot(a):
    if not (a.module and a.results):
        raise SystemExit("snapshot needs --module and --results")
    snap = load_results(a.module, a.results)
    Path(a.out).write_text(json.dumps(snap, indent=1, ensure_ascii=False))
    print(f"wrote {a.out} ({len(snap['ranked'])} apps)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--module")
        p.add_argument("--results", help="results/<module>/<developer>_<phone>")
        p.add_argument("--snapshot", help="snapshot JSON instead of a results folder")
        p.add_argument("--target-app", help="default: RISE")

    s = sub.add_parser("scan")
    common(s)
    s.add_argument("--out")
    s.set_defaults(fn=cmd_scan)
    p = sub.add_parser("plan")
    p.add_argument("data_dir")
    common(p)
    p.set_defaults(fn=cmd_plan)
    n = sub.add_parser("snapshot")
    common(n)
    n.add_argument("--out", required=True)
    n.set_defaults(fn=cmd_snapshot)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()

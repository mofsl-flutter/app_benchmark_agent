#!/usr/bin/env python3
"""Management dashboard for one module: a self-contained HTML page written next to the module workbook.

  Scorecard 1 (technical): the workbook score. Each metric 0-100 (best = 100, worst = 0), averaged per
                           category, weighted by weights.json.
  Scorecard 2 (user feel): the same measurements against fixed published limits (ux_rubric.json), so
                           it shows what a user notices rather than who is best at each counter.
  Verdict:                 RISE's gaps ranked by how far closing each one moves RISE's two scores,
                           found by re-scoring everything with RISE at the target value.

Called by build_report.py --module; no network, no external scripts. Pure functions are unit-tested.
"""
import copy
import datetime
import html
import json
import re
import statistics
from collections import defaultdict

import benchlib as B
import build_report as R

RUBRIC_FILE = B.HERE / "ux_rubric.json"

# Starting points for the verdict table. They say where to look, not what is wrong.
HINTS = {
    "L1": "Start-up work before the first frame (SDK init, synchronous disk reads).",
    "L3": "Show the last saved list first and fill live values in after.",
    "L4": "Keep the screen and its state in memory between tab switches instead of rebuilding it.",
    "L5": "Prefetch or cache the detail data from the list response.",
    "L6": "Refresh only what changed; check the refresh API round trips.",
    "L7": "Restore the last frame on resume and refresh prices behind it.",
    "L8": "Same as L7 after a longer background; check for a full reload.",
    "L14": "Keep sibling tabs built, or load their data before the tap.",
    "L15": "Bytes per open: payload size, duplicate calls, uncompressed images.",
    "S1": "Work done per frame while scrolling: item rebuilds, image decoding, layout.",
    "S2": "Work done per frame while scrolling: item rebuilds, image decoding, layout.",
    "S3": "Work done per frame while scrolling: item rebuilds, image decoding, layout.",
    "S4": "Occasional long frames while scrolling: synchronous work, GC, large images.",
    "S5": "Work done per frame while scrolling: item rebuilds, image decoding, layout.",
    "U4": "Repaint only the values that changed; stop idle animations and shimmer.",
    "U5": "Frames redrawn with nothing changed: animations or timers that repaint.",
    "R1": "Graphics memory after launch: renderer, image caches, WebViews created early.",
    "R2": "Graphics and heap memory on the screen: image caches, WebViews, list size.",
    "R3": "Memory growth while the screen stays open: caches or listeners not released.",
    "R9": "Memory not released after closing the screen: leaked listeners or controllers.",
    "C1": "Idle CPU on the screen: timers, tick handling, redraws.",
    "C2": "Battery on the screen: idle CPU, redraws, socket traffic.",
    "C4": "Data while idle: tick payload size, polling.",
    "X1": "Consolidate overlapping analytics and tracking SDKs.",
    "X2": "Review permissions the module does not need.",
    "X3": "Third-party calls made on this screen.",
    "X4": "Main-thread lock contention during start-up.",
    "R4": "Ship Play app bundles so each phone downloads only its split.",
    "R6": "What is written to disk at login.",
    "R7": "Cache size after the first screen open.",
    "O1": "Show cached data with a clear offline label and refresh on reconnect.",
}


# ---------------------------------------------------------------- inputs (pure)

def load_rubric(path=RUBRIC_FILE):
    data = json.loads(path.read_text())
    rubric = {k: v for k, v in data.items() if not k.startswith("_")}
    total = sum(v["weight"] for v in rubric.values())
    if total != 100:
        raise SystemExit(f"ux_rubric.json weights total {total}, not 100")
    return rubric


def run_values(rows, apps):
    """{app: {metric: [values]}} from the newest row per run."""
    out = defaultdict(lambda: defaultdict(list))
    for r in R.latest_per_run(rows):
        if r["app"] in apps and r["num"] is not None and r["metric"] in B.METRICS:
            out[r["app"]][r["metric"]].append(r["num"])
    return out


def read_facts(rows):
    """{app: {fact: True/False}} from F.<fact> rows (Yes/No); newest wins."""
    out = defaultdict(dict)
    for r in sorted(rows, key=lambda r: r.get("timestamp") or ""):
        mid = r["metric"]
        if mid.startswith("F.") and (r.get("value") or "").strip().capitalize() in ("Yes", "No"):
            out[r["app"]][mid[2:]] = r["value"].strip().capitalize() == "Yes"
    return out


def parse_holdings(text):
    """'RISE=447, Groww=22' -> {'RISE': 447, 'Groww': 22}; anything else is ignored."""
    out = {}
    for name, n in re.findall(r"([A-Za-z][\w .]*?)\s*[=:]\s*(\d+)", text or ""):
        out[B.canonical_app(name.strip())] = int(n)
    return out


def confidence(values):
    """High = 3+ runs within 20 % spread; Medium = 2 runs or within 50 %; Low = over 50 %; One = a single reading."""
    if not values:
        return None, None
    if len(values) == 1:
        return "One", 0.0
    med = statistics.median(values)
    spread = 0.0 if max(values) == min(values) else (100.0 * (max(values) - min(values)) / med if med else 999.0)
    if len(values) >= 3 and spread <= 20:
        return "High", round(spread)
    if spread > 50:
        return "Low", round(spread)
    return "Medium", round(spread)


# ---------------------------------------------------------------- scoring (pure)

def band(ms, bands):
    for limit, score in bands:
        if ms <= limit:
            return score
    return 0


def ux_scores(med, runs, facts, apps, rubric):
    """{criterion: {app: 0-100}}; a criterion with no data for an app is left out for that app."""
    out = {k: {} for k in rubric}
    for a in apps:
        m = med.get(a, {})
        if "speed" in rubric:
            vals = [band(m[x], rubric["speed"]["bands_ms"]) for x in rubric["speed"]["metrics"] if x in m]
            if vals:
                out["speed"][a] = round(statistics.mean(vals), 1)
        if "smooth" in rubric and rubric["smooth"]["metric"] in m:
            sm = rubric["smooth"]
            out["smooth"][a] = sm["pass"] if m[sm["metric"]] >= sm["min_fps"] else sm["fail"]
        if "offline" in rubric and rubric["offline"]["metric"] in m:
            out["offline"][a] = m[rubric["offline"]["metric"]]
        if "friction" in rubric:
            f = facts.get(a, {})
            if "pin_on_resume" in f or "pull_to_refresh" in f:
                pen = rubric["friction"]["penalty"]
                s = 100 - pen * (f.get("pin_on_resume") is True) - pen * (f.get("pull_to_refresh") is False)
                out["friction"][a] = max(0, s)
        if "reliability" in rubric:
            rel = rubric["reliability"]
            screens = [runs.get(a, {}).get(x, []) for x in rel["metrics"]]
            screens = [v for v in screens if len(v) >= 2]
            if screens:
                hangs = sum(1 for v in screens if max(v) > rel["factor"] * statistics.median(v))
                out["reliability"][a] = max(0, 100 - rel["penalty"] * hangs)
    if "battery" in rubric:
        have = {a: med[a][rubric["battery"]["metric"]] for a in apps if rubric["battery"]["metric"] in med.get(a, {})}
        if have:
            lo = min(have.values())
            for a, v in have.items():
                out["battery"][a] = 100.0 if v <= lo else round(100 * max(lo, 0) / v, 1)
    return {k: v for k, v in out.items() if v}


def scorecards(med, runs, facts, ranked, weights, rubric):
    """Both scorecards and their ranks for the ranked apps."""
    tech_cat = R.category_scores(R.metric_scores(med, ranked), ranked)
    tech = R.overall(tech_cat, weights, ranked)
    ux_cat = ux_scores(med, runs, facts, ranked, rubric)
    ux = R.overall(ux_cat, {k: v["weight"] for k, v in rubric.items()}, ranked)
    return {
        "tech_cat": tech_cat, "tech": tech, "tech_rank": {a: R.rank_of(tech, a) for a in ranked},
        "tech_cov": R.coverage(tech_cat, weights, ranked),
        "ux_cat": ux_cat, "ux": ux, "ux_rank": {a: R.rank_of(ux, a) for a in ranked},
        "ux_cov": R.coverage(ux_cat, {k: v["weight"] for k, v in rubric.items()}, ranked),
    }


def _target(med, mid, rise, ranked):
    """Median of the other apps, or the best of them when RISE already beats the median. None if RISE is best."""
    others = {a: med[a][mid] for a in ranked if a != rise and mid in med.get(a, {})}
    if not others or mid not in med.get(rise, {}):
        return None, None
    lower = B.METRICS[mid]["better"] == "Lower"
    rv = med[rise][mid]
    best_app = min(others, key=others.get) if lower else max(others, key=others.get)
    for tgt in (statistics.median(others.values()), others[best_app]):
        if (lower and tgt < rv) or (not lower and tgt > rv):
            return round(tgt, 2), best_app
    return None, best_app


def actions(med, runs, facts, ranked, weights, rubric, limit=8):
    """RISE's gaps, each re-scored as if closed; sorted by gain in technical + user-feel score."""
    rise = next((a for a in ranked if B.is_rise(a)), None)
    if not rise:
        return [], None
    base = scorecards(med, runs, facts, ranked, weights, rubric)
    cands = []

    def evaluate(new_med, new_runs, new_facts):
        sc = scorecards(new_med, new_runs, new_facts, ranked, weights, rubric)
        return {"tech": sc["tech"][rise], "tech_rank": sc["tech_rank"][rise], "ux": sc["ux"][rise], "ux_rank": sc["ux_rank"][rise]}

    for mid in sorted({m for m in med.get(rise, {}) if m in B.METRICS}, key=lambda m: B.CATEGORIES.index(B.METRICS[m]["category"])):
        tgt, best_app = _target(med, mid, rise, ranked)
        if tgt is None:
            continue
        new_med = copy.deepcopy(med)
        new_med[rise][mid] = tgt
        new_runs = copy.deepcopy(runs)
        if mid in new_runs.get(rise, {}):
            new_runs[rise][mid] = [tgt]  # a met target is a steady one
        cands.append({"id": mid, "kind": "metric", "category": B.METRICS[mid]["category"], "from": med[rise][mid], "to": tgt,
                      "unit": B.METRICS[mid]["unit"], "better": B.METRICS[mid]["better"], "best_app": best_app,
                      "best": med[best_app][mid], "set_med": {mid: tgt}, "set_facts": {},
                      **evaluate(new_med, new_runs, facts)})
    f = facts.get(rise, {})
    if f.get("pull_to_refresh") is False:
        new_facts = copy.deepcopy(facts)
        new_facts[rise]["pull_to_refresh"] = True
        new_med = copy.deepcopy(med)
        others = [med[a]["L6"] for a in ranked if a != rise and "L6" in med.get(a, {})]
        set_med = {"L6": round(statistics.median(others), 2)} if others else {}
        new_med[rise].update(set_med)
        cands.append({"id": "pull_to_refresh", "kind": "fact", "category": "User feel", "set_med": set_med,
                      "set_facts": {"pull_to_refresh": True}, **evaluate(new_med, runs, new_facts)})
    if f.get("pin_on_resume") is True:
        new_facts = copy.deepcopy(facts)
        new_facts[rise]["pin_on_resume"] = False
        cands.append({"id": "pin_on_resume", "kind": "fact", "category": "User feel", "set_med": {},
                      "set_facts": {"pin_on_resume": False}, **evaluate(med, runs, new_facts)})

    t0, u0 = base["tech"][rise] or 0, base["ux"][rise] or 0
    for c in cands:
        c["gain"] = round(((c["tech"] or 0) - t0) + ((c["ux"] or 0) - u0), 1)
    chosen = sorted((c for c in cands if c["gain"] > 0), key=lambda c: -c["gain"])[:limit]

    combined = None
    if chosen:
        new_med, new_runs, new_facts = copy.deepcopy(med), copy.deepcopy(runs), copy.deepcopy(facts)
        for c in chosen:
            new_med[rise].update(c["set_med"])
            for k, v in c["set_med"].items():
                if k in new_runs.get(rise, {}):
                    new_runs[rise][k] = [v]
            new_facts.setdefault(rise, {}).update(c["set_facts"])
        combined = evaluate(new_med, new_runs, new_facts)
    return chosen, combined


# ---------------------------------------------------------------- HTML

CSS = """
:root{--bg:#f7f7f5;--card:#ffffff;--ink:#1d1d1b;--muted:#6b6b66;--line:#e3e2dd;--accent:#2f5bd3;--accent-ink:#ffffff;
--heat:#2f5bd3;--good:#1f7a4d;--warn:#a15c00;--bad:#b3261e;--chip:#efeee9}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#141413;--card:#1f1f1d;--ink:#ecebe6;--muted:#a3a29b;
--line:#34332f;--accent:#7d9cf0;--accent-ink:#111;--heat:#5b80e8;--good:#5cc28f;--warn:#e0a24a;--bad:#ef7d74;--chip:#2a2a27}}
:root[data-theme="dark"]{--bg:#141413;--card:#1f1f1d;--ink:#ecebe6;--muted:#a3a29b;--line:#34332f;--accent:#7d9cf0;--accent-ink:#111;
--heat:#5b80e8;--good:#5cc28f;--warn:#e0a24a;--bad:#ef7d74;--chip:#2a2a27}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 4px}h2{font-size:19px;margin:0 0 4px}
h3{font-size:15px;margin:16px 0 6px}.sub{color:var(--muted);margin:0 0 12px}section{background:var(--card);border:1px solid var(--line);
border-radius:12px;padding:18px;margin:16px 0}.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}.kpi .v{font-size:28px;font-weight:650}
.kpi .l{color:var(--muted);font-size:13px}.wrap{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}th:first-child,td:first-child{text-align:left}
th{font-weight:600;color:var(--muted);font-size:12.5px}tr.rise td{font-weight:650}tr.rise td:first-child{box-shadow:inset 3px 0 var(--accent)}
td.na{color:var(--muted)}.bar{display:inline-block;height:8px;border-radius:4px;background:var(--accent);vertical-align:middle;margin-right:6px}
.chip{display:inline-block;padding:1px 7px;border-radius:9px;background:var(--chip);font-size:12px;color:var(--muted)}
.c-High{color:var(--good)}.c-Medium{color:var(--warn)}.c-Low{color:var(--bad)}.c-One{color:var(--muted)}
.note{color:var(--muted);font-size:13px}.best{text-decoration:underline;text-decoration-thickness:2px;text-underline-offset:3px}
ul{margin:6px 0;padding-left:20px}li{margin:3px 0}svg text{fill:var(--ink);font-size:13px}svg .m{fill:var(--muted)}
svg line.o{stroke:var(--line);stroke-width:2}svg line.r{stroke:var(--accent);stroke-width:4}svg circle.o{fill:var(--muted)}svg circle.r{fill:var(--accent)}
td.tx{text-align:left;white-space:normal;min-width:220px}a{color:var(--accent)}.warn{border-left:3px solid var(--warn);padding:8px 12px;background:var(--chip);border-radius:6px;margin:10px 0}
"""


def _e(x):
    return html.escape("" if x is None else str(x))


def _num(v, unit=""):
    if v is None:
        return "–"
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    if isinstance(v, float):
        v = round(v, 1 if abs(v) >= 10 else 2)
    return f"{v:,}" if unit != "★" else str(v)


def _heat(s):
    if s is None:
        return '<td class="na">–</td>'
    return f'<td style="background:color-mix(in srgb,var(--heat) {round(s * 0.45)}%,transparent)">{round(s)}</td>'


def _rank_chart(left, right, apps, labels):
    """Slope chart: technical rank on the left, user-feel rank on the right."""
    n = len(apps)
    h, w, top, gap = 60 + 34 * n, 640, 44, 34
    pos = {}
    for side, ranks in (("l", left), ("r", right)):
        order = sorted((a for a in apps if ranks.get(a) is not None), key=lambda a: (ranks[a], a))
        pos[side] = {a: i + 1 for i, a in enumerate(order)}  # ties get adjacent slots
    yl, yr = (lambda a: top + (pos["l"][a] - 1) * gap), (lambda a: top + (pos["r"][a] - 1) * gap)
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Technical rank versus user-feel rank">',
           f'<text x="200" y="20" text-anchor="end" class="m">Technical</text><text x="440" y="20" class="m">User feel</text>']
    for a in sorted(apps, key=lambda a: B.is_rise(a)):
        if left.get(a) is None or right.get(a) is None:
            continue
        c = "r" if B.is_rise(a) else "o"
        out.append(f'<line class="{c}" x1="210" y1="{yl(a)}" x2="430" y2="{yr(a)}"/>'
                   f'<circle class="{c}" cx="210" cy="{yl(a)}" r="5"/><circle class="{c}" cx="430" cy="{yr(a)}" r="5"/>'
                   f'<text x="200" y="{yl(a) + 4}" text-anchor="end">#{left[a]} {_e(labels[a])}</text>'
                   f'<text x="440" y="{yr(a) + 4}">#{right[a]} {_e(labels[a])}</text>')
    out.append("</svg>")
    return "".join(out)


def render_html(ctx):
    sc, ranked, rise = ctx["sc"], ctx["ranked"], ctx["rise"]
    labels = {a: a + ("*" if ctx["holdings"].get(a) == 0 else "") for a in ranked}
    order_t = sorted(ranked, key=lambda a: (sc["tech"][a] is None, -(sc["tech"][a] or 0)))
    order_u = sorted(ranked, key=lambda a: (sc["ux"][a] is None, -(sc["ux"][a] or 0)))
    cats = [c for c in B.CATEGORIES if c in sc["tech_cat"]]
    crit = [k for k in ctx["rubric"] if k in sc["ux_cat"]]
    p = []
    p.append(f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
             f"<title>{_e(ctx['title'])} Benchmark</title><style>{CSS}</style></head><body><main>")
    p.append(f"<h1>{_e(ctx['title'])}: RISE vs competitors</h1><p class='sub'>{_e(ctx['meta_line'])}</p>")

    # KPIs
    def kpi(v, l):
        return f"<div class='kpi'><div class='v'>{v}</div><div class='l'>{l}</div></div>"
    n = sum(1 for a in ranked if sc["tech"][a] is not None)
    k = []
    if rise:
        k.append(kpi(f"#{sc['tech_rank'][rise]} of {n}", f"RISE technical rank · score {_num(sc['tech'][rise])}"))
        k.append(kpi(f"#{sc['ux_rank'][rise]} of {n}", f"RISE user-feel rank · score {_num(sc['ux'][rise])}"))
        if ctx["combined"]:
            cb = ctx["combined"]
            k.append(kpi(f"#{cb['tech_rank']} · #{cb['ux_rank']}", f"RISE ranks if the {len(ctx['actions'])} verdict items are done (technical · user feel)"))
        k.append(kpi(f"{_num(sc['tech_cov'][rise])}%", "Share of the technical weight with RISE data"))
    p.append(f"<div class='kpis'>{''.join(k)}</div>")
    if ctx["warnings"]:
        p.append("".join(f"<div class='warn'>{_e(w)}</div>" for w in ctx["warnings"]))

    # Scorecard 1
    p.append("<section><h2>Scorecard 1: technical</h2><p class='sub'>Each metric scored 0–100 among these apps (best = 100, worst = 0), "
             "averaged per category, then weighted. The number in brackets is the category weight. "
             "“–” means not measured: that category is left out of the app's score, not counted as zero.</p><div class='wrap'><table><tr><th>Rank</th><th>App</th><th>Score</th>"
             + "".join(f"<th>{_e(c)} ({ctx['weights'][c]})</th>" for c in cats) + "<th>Coverage</th></tr>")
    for a in order_t:
        s = sc["tech"][a]
        bar = f"<span class='bar' style='width:{round((s or 0) * 0.6)}px'></span>" if s is not None else ""
        p.append(f"<tr class='{'rise' if B.is_rise(a) else ''}'><td>{_num(sc['tech_rank'][a])}</td><td style='text-align:left'>{_e(labels[a])}</td>"
                 f"<td>{bar}{_num(s)}</td>" + "".join(_heat(sc["tech_cat"][c].get(a)) for c in cats) + f"<td>{_num(sc['tech_cov'][a])}%</td></tr>")
    p.append("</table></div><p class='note'>Coverage = share of the total weight with data. Compare ranks with care when coverages differ.</p></section>")

    # Scorecard 2
    p.append("<section><h2>Scorecard 2: user feel</h2><p class='sub'>The same measurements against fixed limits a user notices "
             "(response-time and frame-rate standards), so an app is not penalised for being slightly slower than the fastest one.</p>"
             "<div class='wrap'><table><tr><th>Rank</th><th>App</th><th>Score</th>"
             + "".join(f"<th>{_e(ctx['rubric'][c]['label'])} ({ctx['rubric'][c]['weight']})</th>" for c in crit) + "</tr>")
    for a in order_u:
        s = sc["ux"][a]
        bar = f"<span class='bar' style='width:{round((s or 0) * 0.6)}px'></span>" if s is not None else ""
        p.append(f"<tr class='{'rise' if B.is_rise(a) else ''}'><td>{_num(sc['ux_rank'][a])}</td><td style='text-align:left'>{_e(labels[a])}</td>"
                 f"<td>{bar}{_num(s)}</td>" + "".join(_heat(sc["ux_cat"][c].get(a)) for c in crit) + "</tr>")
    p.append("</table></div><h3>How each criterion is scored</h3><div class='wrap'><table><tr><th>Criterion</th><th>Weight</th><th style='text-align:left'>Rule</th><th style='text-align:left'>Basis</th></tr>")
    for c in crit:
        r = ctx["rubric"][c]
        src = f"<a href='{_e(r['url'])}'>{_e(r['source'])}</a>" if r.get("url") else _e(r.get("source"))
        p.append(f"<tr><td>{_e(r['label'])}</td><td>{r['weight']}</td><td class='tx'>{_e(r['rule'])}</td><td class='tx'>{src}</td></tr>")
    p.append("</table></div></section>")

    # Rank comparison
    p.append("<section><h2>Why the two rankings differ</h2><p class='sub'>Technical ranks reward being best at each counter; "
             "user-feel ranks only care whether a limit a person notices is crossed.</p>"
             + _rank_chart(sc["tech_rank"], sc["ux_rank"], ranked, labels))
    moves = sorted(((a, sc["tech_rank"][a] - sc["ux_rank"][a]) for a in ranked if sc["tech_rank"][a] and sc["ux_rank"][a]), key=lambda x: -abs(x[1]))
    if moves and moves[0][1]:
        a, d = moves[0]
        p.append(f"<p>Biggest difference: <b>{_e(a)}</b> is #{sc['tech_rank'][a]} technically and #{sc['ux_rank'][a]} on user feel.</p>")
    p.append("</section>")

    # Verdict
    if rise:
        p.append("<section><h2>Verdict: what RISE needs to work on</h2><p class='sub'>Each row re-scores both scorecards with RISE at the target "
                 "(the other apps' median, or the best of them if RISE already beats the median). Sorted by combined gain. "
                 "“Where to look” is a starting point, not a diagnosis.</p><div class='wrap'><table><tr><th>#</th><th>Gap</th><th>Now</th><th>Target</th>"
                 "<th>Best</th><th>Technical</th><th>User feel</th><th style='text-align:left'>Where to look</th></tr>")
        for i, c in enumerate(ctx["actions"], 1):
            if c["kind"] == "metric":
                name = B.render(B.METRICS[c["id"]]["name"], ctx["module"])
                now, to = f"{_num(c['from'])} {_e(c['unit'])}", f"{_num(c['to'])} {_e(c['unit'])}"
                best = f"{_e(c['best_app'])} {_num(c['best'])}"
                hint = HINTS.get(c["id"], "")
            else:
                name = {"pull_to_refresh": "Add pull-to-refresh", "pin_on_resume": "No PIN on a short resume"}[c["id"]]
                now, to, best = ("No", "Yes", "") if c["id"] == "pull_to_refresh" else ("Asks", "Doesn't ask", "")
                hint = "Users expect to pull down to refresh a list." if c["id"] == "pull_to_refresh" else "Keep the session for short background trips."
            p.append(f"<tr><td>{i}</td><td class='tx'>{_e(c['id']) + ' · ' if c['kind'] == 'metric' else ''}{_e(name)}</td><td>{now}</td><td>{to}</td><td>{best}</td>"
                     f"<td>#{sc['tech_rank'][rise]} → #{c['tech_rank']} ({_num(c['tech'])})</td><td>#{sc['ux_rank'][rise]} → #{c['ux_rank']} ({_num(c['ux'])})</td>"
                     f"<td class='tx'>{_e(hint)}</td></tr>")
        if ctx["combined"]:
            cb = ctx["combined"]
            p.append(f"<tr class='rise'><td></td><td style='text-align:left'>All of the above</td><td></td><td></td><td></td>"
                     f"<td>#{sc['tech_rank'][rise]} → #{cb['tech_rank']} ({_num(cb['tech'])})</td><td>#{sc['ux_rank'][rise]} → #{cb['ux_rank']} ({_num(cb['ux'])})</td><td></td></tr>")
        if not ctx["actions"]:
            p.append("<tr><td colspan='8' style='text-align:left'>RISE is best or tied on every measured metric.</td></tr>")
        p.append("</table></div>")
        if ctx["strengths"]:
            p.append("<h3>Where RISE is already best</h3><ul>" + "".join(f"<li>{_e(s)}</li>" for s in ctx["strengths"]) + "</ul>")
        p.append("</section>")

    # Measurements
    p.append("<section><h2>Measurements</h2><p class='sub'>Median of the runs. Underlined = best among ranked apps. "
             "Confidence: <span class='c-High'>High</span> 3+ runs within 20 %, <span class='c-Medium'>Medium</span> 2 runs or within 50 %, "
             "<span class='c-Low'>Low</span> over 50 %, <span class='c-One'>One</span> a single reading.</p><div class='wrap'><table><tr><th>Metric</th><th>Unit</th>"
             + "".join(f"<th>{_e(labels.get(a, a))}</th>" for a in ctx["apps"]) + "</tr>")
    for mid in ctx["metric_ids"]:
        m = B.METRICS[mid]
        have = {a: ctx["med"][a][mid] for a in ranked if mid in ctx["med"].get(a, {})}
        best = None
        if len(have) >= 2:
            best = (min if m["better"] == "Lower" else max)(have.values())
        cells = []
        for a in ctx["apps"]:
            v = ctx["med"].get(a, {}).get(mid)
            if v is None:
                cells.append("<td class='na'>–</td>")
                continue
            conf, spread = confidence(ctx["runs"].get(a, {}).get(mid, []))
            badge = f" <span class='c-{conf}' title='spread {spread}%'>●</span>" if conf else ""
            cls = " class='best'" if best is not None and v == best and a in have else ""
            cells.append(f"<td><span{cls}>{_num(v)}</span>{badge}</td>")
        solo = " <span class='chip'>one app only, not scored</span>" if len(have) < 2 else ""
        p.append(f"<tr><td class='tx' title='{_e(m['category'])}'>{mid} · {_e(B.render(m['name'], ctx['module']))}{solo}</td><td>{_e(m['unit'])} {'↓' if m['better'] == 'Lower' else '↑'}</td>{''.join(cells)}</tr>")
    p.append("</table></div></section>")

    # Method
    p.append("<section><h2>Method</h2><ul>"
             "<li>Black-box: every app is the installed release build, measured from outside with adb, Perfetto, screen recordings and PCAPdroid, "
             "on one phone, with the run protocol in PROTOCOL.md.</li>"
             "<li>Technical score: per metric, best = 100 and worst = 0 among the ranked apps; category = mean of its metrics; overall = weighted mean over the categories with data (weights.json).</li>"
             "<li>User-feel score: fixed limits in ux_rubric.json; criteria without data are left out and the rest re-weighted.</li>"
             "<li>Verdict: re-scores both scorecards with RISE moved to the target; other apps' scores move too because the best/worst range changes.</li>"
             f"<li>Data: {_e(ctx['folder'])} (module version {_e(ctx['module'].get('version'))}).</li></ul>")
    if ctx["holdings"]:
        p.append("<p class='note'>Holdings / list size per app: " + _e(", ".join(f"{a} {n}" for a, n in ctx["holdings"].items()))
                 + ". * = empty account: its screen times are not comparable.</p>")
    p.append("</section></main></body></html>")
    return "".join(p)


# ---------------------------------------------------------------- entry point

def build(module, folder, rows, app_rows, apps, developer, model, out_path):
    """Write the dashboard; returns a short summary for the console."""
    ranked = [x for x in apps if B.load_apps().get(x, {}).get("ranked", True)]
    all_rows = rows + [r for r in app_rows if r["app"] in apps]
    med = R.medians(all_rows, module, set(apps))
    runs = run_values(all_rows, set(apps))
    facts = read_facts(rows)
    weights, rubric = B.load_weights(), load_rubric()
    sc = scorecards(med, runs, facts, ranked, weights, rubric)
    acts, combined = actions(med, runs, facts, ranked, weights, rubric)
    rise = next((a for a in ranked if B.is_rise(a)), None)

    envs = B.read_env(folder) or B.read_env(folder.parent.parent / B.APP_SCOPE / folder.name)
    e = envs[-1] if envs else {}
    holdings = parse_holdings(e.get("holdings", ""))
    stamps = sorted(r.get("timestamp") or "" for r in all_rows if r.get("timestamp"))
    when = f"{stamps[0][:10]} to {stamps[-1][:10]}" if stamps else datetime.date.today().isoformat()
    versions = dict(part.strip().split("=", 1) for part in (e.get("app_versions") or "").split(";") if "=" in part)
    meta = [f"{developer} · {model}" + (f" · Android {e['android']}" if e.get("android") else ""),
            f"measured {when}", f"RISE {versions.get('RISE', '?')}" if versions else "",
            f"{e.get('render_rate_hz')} Hz" if e.get("render_rate_hz") else ""]

    warnings = []
    covs = [v for v in sc["tech_cov"].values() if v]
    if covs and max(covs) - min(covs) > 10:
        low = [a for a in ranked if sc["tech_cov"][a] is not None and sc["tech_cov"][a] < max(covs) - 10]
        warnings.append(f"{', '.join(low)} have less data than the others (coverage {min(covs)}% vs {max(covs)}%); "
                        f"their technical scores leave out the missing categories, so compare their ranks with care.")
    if module.get("runs") or module.get("skip"):
        dev = [f"{k} {v} run(s)" for k, v in sorted(module.get("runs", {}).items())]
        warnings.append("Protocol deviations (module file): "
                        + (module["deviation_note"] if module.get("deviation_note") else
                           "; ".join(x for x in (", ".join(dev), f"{len(module.get('skip', []))} metric(s) not measured") if x)))
    empty = [a for a, n in holdings.items() if n == 0 and a in ranked]
    if empty:
        warnings.append(f"{', '.join(empty)} had an empty account during the test (*).")

    strengths = []
    if rise:
        ms = R.metric_scores(med, ranked)
        for mid in sorted(ms, key=lambda m: B.CATEGORIES.index(B.METRICS[m]["category"])):
            if ms[mid].get(rise) == 100 and len(ms[mid]) >= 3 and len(set(med[a][mid] for a in ms[mid])) > 1:
                strengths.append(f"{mid} · {B.render(B.METRICS[mid]['name'], module)}: {_num(med[rise][mid])} {B.METRICS[mid]['unit']}")

    metric_ids = [m["id"] for m in B.METRIC_CATALOGUE if any(m["id"] in med.get(a, {}) for a in apps)]
    ctx = {"title": module.get("title") or module["name"], "module": module, "meta_line": " · ".join(x for x in meta if x),
           "sc": sc, "ranked": ranked, "apps": apps, "rise": rise, "holdings": holdings, "weights": weights, "rubric": rubric,
           "actions": acts, "combined": combined, "warnings": warnings, "strengths": strengths, "med": med, "runs": runs,
           "metric_ids": metric_ids, "folder": str(folder.relative_to(B.HERE)) if folder.is_relative_to(B.HERE) else str(folder)}
    out_path.write_text(render_html(ctx))
    summary = {"tech_rank": sc["tech_rank"].get(rise), "ux_rank": sc["ux_rank"].get(rise), "tech": sc["tech"].get(rise),
               "ux": sc["ux"].get(rise), "n": len(ranked), "actions": [a["id"] for a in acts], "combined": combined}
    return summary

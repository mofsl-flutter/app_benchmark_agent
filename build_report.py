#!/usr/bin/env python3
"""Reports from the shared results folder.

  python3 build_report.py --module fno [--developer NAME] [--device-model MODEL]
        One module's workbook, filled from results/fno/<developer>_<device>/runs.csv (+ the same
        developer's _app folder for phone-scoped metrics). -> reports/fno/fno_<dev>_<device>_<date>.xlsx

  python3 build_report.py --combined
        Every module, every developer -> reports/combined/combined_<date>.xlsx and scorecard_<date>.md
        Ranks and 0-100 scores are compared across modules; raw values are not (different phones).

  python3 build_report.py --module fno --html
        Also writes <workbook name>_api.html next to the workbook: the API / network comparison
        (sheet 10) as a standalone page, for sharing without Excel.

  python3 build_report.py --metrics-md
        Regenerates METRICS.md from the catalogue in benchlib.py.
"""
import argparse
import datetime
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import apilog
import benchlib as B
import netcap

RUN_FIRST, COL_NOTE = 7, 16
CALLS_SHEET = "10 API & Network calls"
MAX_LISTING = 3000


# ---------------------------------------------------------------- API / network side tables (pure)

def _num(v):
    try:
        return float(v) if v not in ("", None) else None
    except ValueError:
        return None


def _median(xs):
    xs = sorted(x for x in xs if x is not None)
    return xs[len(xs) // 2] if xs else None


def api_summary(folder):
    """[{app, phase, run, calls, endpoints, repeats, errors, total_ms, wall_ms, longest_ms, longest, cache, bytes}]
    from api_calls.csv (newest rows per app/phase/run win), ordered by app, phase, run."""
    rows = B.read_calls(folder, "api_calls.csv")
    groups = defaultdict(dict)
    for r in rows:  # later timestamps for the same run replace earlier ones (a --redo)
        key = (r["app"], r.get("phase", ""), int(float(r.get("run") or 0)))
        groups[key].setdefault(r.get("timestamp", ""), []).append(r)
    out = []
    for (app, phase, run), by_ts in sorted(groups.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
        calls = by_ts[max(by_ts)]
        conv = [{"method": c["method"], "host": c["host"], "path": c["path"], "status": c["status"],
                 "duration_ms": _num(c["duration_ms"]), "t_rel_ms": _num(c["t_rel_ms"]), "cache": c["cache"],
                 "size_bytes": _num(c["size_bytes"]), "repeat_of": c["repeat_of"]} for c in calls]
        s = apilog.summarize(conv)
        s.update({"app": app, "phase": phase, "run": run,
                  "cache": f"{s['cache_hits']}/{s['cache_total']}" if s["cache_total"] else ""})
        out.append(s)
    return out


def net_summary(folder):
    """[{app, run, phase, connections, hosts, third_party, kb_in, kb_out, median_first_response_ms}] from net_calls.csv."""
    rows = B.read_calls(folder, "net_calls.csv")
    groups = defaultdict(dict)
    for r in rows:
        key = (r["app"], int(float(r.get("run") or 0)), r.get("phase", ""))
        groups[key].setdefault(r.get("timestamp", ""), []).append(r)
    out = []
    for (app, run, phase), by_ts in sorted(groups.items()):
        fl = by_ts[max(by_ts)]
        hosts = sorted({f["host"] for f in fl if f["host"]})
        own = B.own_domains(app)
        tp = netcap.third_party(hosts, own) if own else sorted({f["host"] for f in fl if f.get("third_party") == "yes"})
        out.append({"app": app, "run": run, "phase": phase, "connections": len(fl), "hosts": len(hosts),
                    "third_party": tp,  # recomputed from apps.json own_domains as they are now, not as captured
                    "kb_in": round(sum(_num(f["bytes_in"]) or 0 for f in fl) / 1024, 1),
                    "kb_out": round(sum(_num(f["bytes_out"]) or 0 for f in fl) / 1024, 1),
                    "median_first_response_ms": _median([_num(f["first_response_ms"]) for f in fl]),
                    "host_list": hosts})
    return out


def calls_compare(folder):
    """App-by-app comparison of the API / network side tables: [(label, {app: value})], apps in B.app_order.
    Medians over runs. RISE-only rows (API calls) are blank for apps that log nothing."""
    api = [s for s in api_summary(folder) if s["phase"] == "open"]
    net = net_summary(folder)
    apps = B.app_order({s["app"] for s in api} | {s["app"] for s in net})
    rows = []

    def add(label, fn, source):
        by = defaultdict(list)
        for s in source:
            by[s["app"]].append(s)
        vals = {a: fn(by[a]) for a in apps if by.get(a)}
        if any(v not in (None, "") for v in vals.values()):
            rows.append((label, vals))

    net_open = [s for s in net if s["phase"] == "open"]
    net_launch = [s for s in net if s["phase"] == "launch"]
    net_screen = [s for s in net if s["phase"] == "screen"]
    add("Connections opened at launch (to home)", lambda ss: _median([s["connections"] for s in ss]), net_launch)
    add("KB received at launch", lambda ss: _median([s["kb_in"] for s in ss]), net_launch)
    add("Hosts contacted at launch", lambda ss: _median([s["hosts"] for s in ss]), net_launch)
    add("Connections opened on screen open (L11 window)", lambda ss: _median([s["connections"] for s in ss]), net_open)
    add("KB received on screen open", lambda ss: _median([s["kb_in"] for s in ss]), net_open)
    add("Median time to first byte on screen open (ms)", lambda ss: _median([s["median_first_response_ms"] for s in ss]), net_open)
    add("New connections while exercising the screen (60 s)", lambda ss: _median([s["connections"] for s in ss]), net_screen)
    add("Third-party hosts seen (open + 60 s)", lambda ss: len({h for s in ss for h in s["third_party"]}), net_open + net_screen)
    add("Third-party host names", lambda ss: ", ".join(sorted({h for s in ss for h in s["third_party"]})), net_open + net_screen)
    add("API calls per screen open (from the app's log)", lambda ss: _median([s["calls"] for s in ss]), api)
    add("Distinct endpoints per open", lambda ss: _median([s["endpoints"] for s in ss]), api)
    add("Repeated requests per open", lambda ss: _median([s["repeats"] for s in ss]), api)
    add("API network wall time per open (ms)", lambda ss: _median([s["wall_ms"] for s in ss]), api)
    add("Longest API call (ms)", lambda ss: _median([s["longest_ms"] for s in ss]), api)
    add("Longest API call", lambda ss: ss[0]["longest"], api)
    return apps, rows


def api_pointers(folder, app="RISE"):
    """Rule-based optimisation pointers for one app's API / network behaviour: [(title, detail)].
    Each rule fires only on evidence in api_calls.csv / net_calls.csv, with the numbers in the text."""
    out = []
    api = [s for s in api_summary(folder) if s["app"] == app and s["phase"] == "open"]
    calls = [c for c in B.read_calls(folder, "api_calls.csv") if c["app"] == app and c.get("phase") == "open"]
    net = net_summary(folder)
    mine = [s for s in net if s["app"] == app]
    others = [s for s in net if s["app"] != app]
    flows = [f for f in B.read_calls(folder, "net_calls.csv") if f["app"] == app]
    if calls:
        run = max(int(float(c["run"] or 0)) for c in calls)  # the newest run, newest rows for it
        in_run = [c for c in calls if int(float(c["run"] or 0)) == run]
        latest = max(c["timestamp"] for c in in_run)
        cur = [c for c in in_run if c["timestamp"] == latest]
        reps = [c for c in cur if c.get("repeat_of")]
        if reps:
            paths = sorted({f"{c['method']} {c['path']}" for c in reps})
            saved = sum(_num(c["duration_ms"]) or 0 for c in reps)
            out.append(("Repeated requests on one screen open",
                        f"{len(reps)} of {len(cur)} calls repeat an earlier call within the same open ({', '.join(paths)}). "
                        f"Dedupe in-flight requests or keep the first response in memory: saves {int(saved)} ms of network time and "
                        f"{sum((_num(c['size_bytes']) or 0) for c in reps) / 1024:.0f} KB per open."))
        durs = [(c, _num(c["duration_ms"]) or 0) for c in cur]
        total = sum(d for _, d in durs) or 1
        slow = [(c, d) for c, d in durs if d >= 300]
        for c, d in sorted(slow, key=lambda x: -x[1])[:3]:
            out.append((f"Slow call: {c['method']} {c['path']}",
                        f"{int(d)} ms, {d / total * 100:.0f}% of the open's API time"
                        + (f", {int(_num(c['size_bytes']) or 0) // 1024} KB" if c.get("size_bytes") else "")
                        + (f", CDN cache {c['cache']}" if c.get("cache") else ", no CDN cache header") +
                        ". Serve it from cache (ETag / CDN) or trim the payload; this call sets the screen's network floor."))
        with_cache = [c for c in cur if c.get("cache")]
        if with_cache and not any(c["cache"].upper() == "HIT" for c in with_cache):
            out.append(("No CDN cache hits", f"{len(with_cache)} call(s) carry a CDN cache header and none was a HIT on a repeat open. "
                                             "Check cache keys and TTLs for the screen's read-only calls."))
        elif not with_cache and len(cur) >= 2:
            out.append(("Screen calls bypass the CDN", f"None of the {len(cur)} calls carries a CDN cache header, so every open hits origin. "
                                                      "Route the read-only calls (dashboard, recent, static lists) through the CDN with ETag revalidation."))
    if mine:
        launch = [s for s in mine if s["phase"] == "launch"]
        best = min((s["connections"] for s in others if s["phase"] == "launch"), default=None)
        if launch and best and _median([s["connections"] for s in launch]) >= 1.5 * best:
            mconn = _median([s["connections"] for s in launch])
            kb = _median([s["kb_in"] for s in launch])
            out.append(("Launch opens too many connections",
                        f"{mconn:.0f} connections and {kb:.0f} KB to reach home, against {best} for the leanest competitor. "
                        "Each connection costs a TCP + TLS handshake on mobile; reuse one HTTP/2 connection per host and bundle static assets."))
        by_host = defaultdict(int)
        for f in flows:
            if f["phase"] == "launch":
                by_host[f["host"]] += 1
        for host, n in sorted(by_host.items(), key=lambda kv: -kv[1])[:2]:
            if n >= 10:
                out.append((f"{n} connections to {host} at launch",
                            "One short connection per asset. Keep the connection alive (HTTP/2 multiplexing) or ship the assets in the app bundle."))
        screen = [s for s in mine if s["phase"] == "screen"]
        best_s = min((s["connections"] for s in others if s["phase"] == "screen"), default=None)
        if screen and best_s is not None and _median([s["connections"] for s in screen]) >= best_s + 3:
            out.append(("Connections are not reused while using the screen",
                        f"{_median([s['connections'] for s in screen]):.0f} new connections in 60 s of typing and tab taps, against {best_s} for the "
                        "leanest competitor. Enable keep-alive / HTTP/2 on the CDN client so repeated fetches share a connection."))
        tp_open = sorted({h for s in mine if s["phase"] == "open" for h in s["third_party"]})
        if tp_open:
            out.append(("Analytics on the critical path of the screen open",
                        f"Third-party hosts contacted while {app}'s screen was loading: {', '.join(tp_open)}. "
                        "Defer SDK uploads until the screen is interactive so they do not compete for the radio."))
        own = B.own_domains(app)
        own_hosts = {f["host"] for f in flows} - set(netcap.third_party({f["host"] for f in flows}, own)) if own else set()
        uat = sorted(h for h in own_hosts if re.search(r"uat|staging|stage|sandbox|preprod|test|(^|[.-])dev[.-]", h))
        if uat:
            out.append(("Non-production host in the production build",
                        f"{', '.join(uat)} contacted by the Play Store build. Point the asset / config URLs at production and strip "
                        "non-production hosts and certificates from release builds."))
    return out


def calls_lines(folder):
    """One-line summaries for the console and the combined scorecard; [] when neither side table exists."""
    lines = []
    api = [s for s in api_summary(folder) if s["phase"] == "open"]
    if api:
        by_app = defaultdict(list)
        for s in api:
            by_app[s["app"]].append(s)
        for app, ss in by_app.items():
            lines.append(f"API calls ({app}): median {_median([s['calls'] for s in ss])} per open, "
                         f"{_median([s['repeats'] for s in ss])} repeats, network wall {_median([s['wall_ms'] for s in ss])} ms "
                         f"over {len(ss)} run(s)")
    net = [s for s in net_summary(folder) if s["phase"] == "open"]
    if net:
        by_app = defaultdict(list)
        for s in net:
            by_app[s["app"]].append(s)
        parts = []
        for app, ss in by_app.items():
            tp = sorted({h for s in ss for h in s["third_party"]})
            parts.append(f"{app} {_median([s['connections'] for s in ss])} conn / {_median([s['hosts'] for s in ss])} hosts"
                         + (f" / {len(tp)} third-party" if tp else ""))
        lines.append("Network per open (PCAPdroid): " + "; ".join(parts))
    return lines


# ---------------------------------------------------------------- aggregation (pure)

def latest_per_run(rows):
    """Keep only the newest row per (app, metric, run): a re-measured or replaced run supersedes the old row."""
    best = {}
    for r in rows:
        key = (r["app"], r["metric"], int(float(r.get("run") or 0)))
        if key not in best or (r.get("timestamp") or "") >= (best[key].get("timestamp") or ""):
            best[key] = r
    return list(best.values())


def medians(rows, module, apps):
    """{app: {metric: median or score}} from runs.csv rows for one folder. Items roll up into O1 / D1.
    Newest row per (app, metric, run) wins; app-scoped facts use the latest run unless the catalogue expects
    several runs (X4), in which case the median is used like any other metric."""
    vals = defaultdict(lambda: defaultdict(list))
    items = defaultdict(lambda: defaultdict(dict))  # app -> metric(O1/D1) -> slug -> answer
    for r in latest_per_run(rows):
        app = r["app"]
        mid = r["metric"]
        if "." in mid:
            base, s = mid.split(".", 1)
            items[app][base][s] = (r.get("value") or "").strip()
        elif r["num"] is not None:
            vals[app][mid].append((int(float(r.get("run") or 0)), r["num"]))
    out = defaultdict(dict)
    for app in set(list(vals) + list(items)):
        if apps is not None and app not in apps:
            continue
        for mid, lst in vals[app].items():
            if mid not in B.METRICS:
                continue
            m = B.METRICS[mid]
            if m["scope"][0] == "app" and m["runs"] == 1:
                out[app][mid] = sorted(lst)[-1][1]  # latest run wins for single facts
            else:
                out[app][mid] = round(statistics.median(v for _, v in lst), 2)
        for base, answers in items[app].items():
            score = item_score(base, answers.values())
            if score is not None:
                out[app][base] = score
    return out


def item_score(base, answers):
    counts = defaultdict(int)
    for a in answers:
        counts[a.capitalize() if a.upper() != "N/A" else "N/A"] += 1
    y, p, n = counts["Yes"], counts["Partial"], counts["No"]
    if y + p + n == 0:
        return None
    if base == "O1":
        return round(100 * (2 * y + p) / (2 * (y + p + n)), 1)
    return round(100 * (y + 0.5 * p) / (y + p + n), 1)


def metric_scores(med, ranked_apps):
    """{metric: {app: 0-100}} using the Scorecard formula; needs >= 2 ranked apps with a value."""
    out = defaultdict(dict)
    mids = {m for app in ranked_apps for m in med.get(app, {})}
    for mid in mids:
        have = {a: med[a][mid] for a in ranked_apps if mid in med.get(a, {})}
        if len(have) < 2 or mid not in B.METRICS:
            continue
        lo, hi = min(have.values()), max(have.values())
        for a, x in have.items():
            if hi == lo:
                out[mid][a] = 100.0
            elif B.METRICS[mid]["better"] == "Lower":
                out[mid][a] = round(100 * (hi - x) / (hi - lo), 1)
            else:
                out[mid][a] = round(100 * (x - lo) / (hi - lo), 1)
    return out


def category_scores(mscores, apps):
    cats = defaultdict(lambda: defaultdict(list))
    for mid, per_app in mscores.items():
        cat = B.METRICS[mid]["category"]
        for a, s in per_app.items():
            cats[cat][a].append(s)
    return {cat: {a: round(statistics.mean(v), 1) for a, v in per_app.items()} for cat, per_app in cats.items()}


def overall(cscores, weights, apps):
    out = {}
    for a in apps:
        num = den = 0.0
        for cat, per_app in cscores.items():
            if a in per_app:
                num += weights[cat] * per_app[a]
                den += weights[cat]
        out[a] = round(num / den, 1) if den else None
    return out


def coverage(cscores, weights, apps):
    """Share of the total weight that has data for each app, in %."""
    total = sum(weights.values())
    out = {}
    for a in apps:
        have = sum(weights[cat] for cat, per_app in cscores.items() if a in per_app)
        out[a] = round(100 * have / total, 1) if total else None
    return out


def module_apps(module, rows, app_rows):
    """Apps that take part in a module's report: RISE (and unranked RISE builds) plus every app that has module
    rows AND a screen in this module. Apps known only from _app rows, or with screen null, stay out."""
    with_rows = {r["app"] for r in rows}
    chosen = set()
    for a in with_rows | {r["app"] for r in app_rows}:
        if B.is_rise(a) or B.is_unranked_rise(a):
            if a in with_rows or (B.is_rise(a) and app_rows and a in {r["app"] for r in app_rows}):
                chosen.add(a)
        elif a in with_rows and B.app_screen(module, a) is not None:
            chosen.add(a)
    return B.app_order(chosen)


def rank_of(values, app, higher_is_better=True):
    v = values.get(app)
    if v is None:
        return None
    others = [x for a, x in values.items() if x is not None]
    better = sum(1 for x in others if (x > v if higher_is_better else x < v))
    return better + 1


def best_and_gap(med, mid, ranked_apps):
    have = {a: med[a][mid] for a in ranked_apps if mid in med.get(a, {})}
    if len(have) < 2:
        return None, None
    lower = B.METRICS[mid]["better"] == "Lower"
    best_app = min(have, key=have.get) if lower else max(have, key=have.get)
    rise = next((a for a in have if B.is_rise(a)), None)
    gap = None
    if rise:
        gap = round(have[rise] - have[best_app], 2) if lower else round(have[best_app] - have[rise], 2)
    return best_app, gap


def latest_ts(rows):
    return max((r.get("timestamp") or "" for r in rows), default="")


def group_folders(all_runs):
    """{module: [(folder, rows)]} sorted so the latest folder is first."""
    by_mod = defaultdict(list)
    for module, folder, rows in all_runs:
        by_mod[module].append((folder, rows))
    for module in by_mod:
        by_mod[module].sort(key=lambda fr: latest_ts(fr[1]), reverse=True)
    return by_mod


def completeness(module, folder, rows):
    """[(app, missing_count, missing_list, version_mismatch_rows)]"""
    out = []
    apps = sorted({r["app"] for r in rows})
    cur = module.get("version")
    for app in apps:
        gaps = B.missing(module, folder, app)
        mism = sum(1 for r in rows if r["app"] == app and r.get("module_version") and r["module_version"] != cur)
        out.append((app, len(gaps), sorted(gaps), mism))
    return out


# ---------------------------------------------------------------- per-module workbook

def fill_module_workbook(module, folder, rows, app_rows, out_path, developer, device_label):
    from openpyxl import load_workbook
    import build_benchmark as W

    apps = module_apps(module, rows, app_rows)
    app_rows = [r for r in app_rows if r["app"] in apps]
    layout = W.build_workbook(out_path, apps=apps, device_label=device_label, module=module)
    wb = load_workbook(out_path)
    med = medians(rows + app_rows, module, set(apps))

    def fill_runs(rrows, allow_phone):
        notes = defaultdict(set)
        for r in latest_per_run(rrows):
            mid = r["metric"]
            if "." in mid or mid not in B.METRICS:
                continue
            m = B.METRICS[mid]
            if m["phone"] != allow_phone and allow_phone is not None:
                continue
            key = (mid, r["app"])
            if m["scope"][0] == "runs" and key in layout["runs"]:
                sheet, row = layout["runs"][key]
                ws = wb[sheet]
                run = int(float(r.get("run") or 0))
                if r["num"] is not None and 1 <= run <= B.NRUNS:
                    ws.cell(row=row, column=RUN_FIRST + run - 1).value = r["num"]
                if r.get("note"):
                    notes[(sheet, row)].add(r["note"][:120])
            elif m["scope"][0] == "app":
                sheet, col = m["scope"][1], m["scope"][2]
                rows_map = layout["sdk_rows"] if sheet == B.SDK else layout["info_rows"]
                if r["app"] in rows_map and mid in med.get(r["app"], {}):
                    wb[sheet][f"{col}{rows_map[r['app']]}"].value = med[r["app"]][mid]  # median for multi-run facts (X4)
        for (sheet, row), ns in notes.items():
            wb[sheet].cell(row=row, column=COL_NOTE).value = " | ".join(sorted(ns))[:250]

    fill_runs(rows, False)
    fill_runs(app_rows, True)

    # O1 / D1 items
    for r in rows:
        mid = r["metric"]
        if "." not in mid:
            continue
        base, s = mid.split(".", 1)
        rows_map, cols_map, sheet = ((layout["off_rows"], layout["off_cols"], B.OFF) if base == "O1"
                                     else (layout["dp_rows"], layout["dp_cols"], B.DP))
        if s in rows_map and r["app"] in cols_map:
            wb[sheet].cell(row=rows_map[s], column=cols_map[r["app"]]).value = (r.get("value") or "").strip()
            if base == "O1" and r.get("note") and s in layout.get("off_note_rows", {}):
                wb[sheet].cell(row=layout["off_note_rows"][s], column=cols_map[r["app"]]).value = r["note"][:200]

    # N/A notes for metrics that do not apply
    for (mid, app), (sheet, row) in layout["runs"].items():
        ok, why = B.metric_applies(mid, module)
        if not ok and not B.METRICS[mid]["phone"]:
            wb[sheet].cell(row=row, column=COL_NOTE).value = f"N/A: {why}"

    # Test Setup + App Info from env.csv
    envs = B.read_env(folder) or B.read_env(folder.parent.parent / B.APP_SCOPE / folder.name)
    ts = wb["Test Setup"]
    if envs:
        e = envs[-1]
        for col, key in ((2, "device_model"), (3, "android"), (4, "device_ram_gb"), (5, "render_rate_hz"),
                         (6, "refresh_rate_mode"), (7, "developer"), (8, "notes")):
            ts.cell(row=6, column=col).value = e.get(key, "")
        vals = [f"{e.get('wifi_rssi_dbm', '')} / {e.get('wifi_link_mbps', '')}", e.get("speedtest_mbps", ""),
                e.get("private_dns_mode", ""), f"{e.get('battery_pct', '')} / {e.get('charging', '')}",
                e.get("thermal_status", ""), e.get("animation_scales", "")]
        for i, v in enumerate(vals):
            ts.cell(row=11 + i, column=2).value = v
        versions = {}
        for part in (e.get("app_versions") or "").split(";"):
            if "=" in part:
                k, v = part.strip().split("=", 1)
                versions[B.canonical_app(k)] = v
        for app, row in layout["setup_app_rows"].items():
            ts.cell(row=row, column=2).value = versions.get(app, "")
            ts.cell(row=row, column=4).value = e.get("holdings", "") if B.is_rise(app) else ""
        info = wb[B.INFO]
        apps_reg = B.load_apps()
        for app, row in layout["info_rows"].items():
            info.cell(row=row, column=2).value = apps_reg.get(app, {}).get("package", "")
            info.cell(row=row, column=3).value = versions.get(app, "")
            info.cell(row=row, column=4).value = (e.get("timestamp") or "")[:10]
    fill_calls_sheet(wb, folder)
    wb.save(out_path)
    return apps


def fill_calls_sheet(wb, folder):
    """Sheet 10: RISE's API calls per open/launch (from api_calls.csv) and every app's connections from the
    PCAPdroid pass (net_calls.csv). Diagnostic only: nothing here feeds the scores."""
    import build_benchmark as W
    api, net = api_summary(folder), net_summary(folder)
    if not api and not net:
        return
    ws = wb.create_sheet(CALLS_SHEET)
    ws["A1"] = "API & network calls (diagnostic, not scored)"; ws["A1"].font = W.f_title
    ws["A2"] = ("API calls come from the app's own log (RISE logs every call; competitors log nothing). Network rows come "
                "from a PCAPdroid capture per run (hosts, connections, bytes; contents stay encrypted). Compare the API "
                "wall time with L3 (screen fully rendered): the gap is rendering and app logic.")
    ws["A2"].font = W.f_sub

    def header(row, cols):
        for i, h in enumerate(cols):
            c = ws.cell(row=row, column=1 + i, value=h)
            c.font, c.fill, c.alignment, c.border = W.f_head, W.fill_head, W.center, W.box
        ws.row_dimensions[row].height = 30

    def put(row, values):
        for i, v in enumerate(values):
            c = ws.cell(row=row, column=1 + i, value=v)
            c.font, c.border = W.f_base, W.box

    r = 4
    apps_c, compare = calls_compare(folder)
    if compare:
        ws.cell(row=r, column=1, value="Comparison (medians over runs; RISE API rows come from its log, competitors log nothing)").font = W.f_sect; r += 1
        header(r, ["Metric"] + list(apps_c)); r += 1
        for label, vals in compare:
            put(r, [label] + [vals.get(a, "") for a in apps_c]); r += 1
        r += 2
    pointers = api_pointers(folder)
    if pointers:
        ws.cell(row=r, column=1, value="Where RISE's API calls need optimisation (from the rows below)").font = W.f_sect; r += 1
        header(r, ["Finding", "Evidence and fix"]); r += 1
        for t, d in pointers:
            put(r, [t, d]); ws.cell(row=r, column=2).alignment = W.wrap; r += 1
        r += 2
    if api:
        ws.cell(row=r, column=1, value="API calls per run (from the app's log)").font = W.f_sect; r += 1
        header(r, ["App", "Phase", "Run", "Calls", "Endpoints", "Repeats", "Errors", "Network ms (sum)", "Wall ms",
                   "Longest ms", "Longest call", "CDN cache HIT/total", "Bytes"]); r += 1
        for s in api:
            put(r, [s["app"], s["phase"], s["run"], s["calls"], s["endpoints"], s["repeats"], s["errors"], s["total_ms"],
                    s["wall_ms"], s["longest_ms"], s["longest"], s["cache"], s["bytes"]]); r += 1
        by = defaultdict(list)
        for s in api:
            by[(s["app"], s["phase"])].append(s)
        for (app, phase), ss in by.items():
            put(r, [app, phase, "median", _median([s["calls"] for s in ss]), _median([s["endpoints"] for s in ss]),
                    _median([s["repeats"] for s in ss]), _median([s["errors"] for s in ss]), _median([s["total_ms"] for s in ss]),
                    _median([s["wall_ms"] for s in ss]), _median([s["longest_ms"] for s in ss]), "", "", _median([s["bytes"] for s in ss])])
            for col in range(1, 14):
                ws.cell(row=r, column=col).font = W.f_bold
            r += 1
        r += 2
    if net:
        ws.cell(row=r, column=1, value="Network per run (PCAPdroid pass, --group net)").font = W.f_sect; r += 1
        header(r, ["App", "Run", "Phase", "Connections", "Hosts", "Third-party hosts", "KB in", "KB out",
                   "Median first-response ms", "Third-party list"]); r += 1
        for s in net:
            put(r, [s["app"], s["run"], s["phase"], s["connections"], s["hosts"], len(s["third_party"]), s["kb_in"],
                    s["kb_out"], s["median_first_response_ms"], ", ".join(s["third_party"])]); r += 1
        r += 2
    # listings
    for name, title in (("api_calls.csv", "Every API call"), ("net_calls.csv", "Every connection")):
        rows = B.read_calls(folder, name)
        if not rows:
            continue
        cols = [c for c in B.CALLS_FILES[name] if c not in ("module", "module_version", "developer", "device_model",
                                                             "package", "version", "source")]
        ws.cell(row=r, column=1, value=f"{title} ({name}" + (f", first {MAX_LISTING} rows" if len(rows) > MAX_LISTING else "") + ")").font = W.f_sect
        r += 1
        header(r, cols); first = r; r += 1
        for row in rows[:MAX_LISTING]:
            put(r, [row.get(c, "") for c in cols]); r += 1
        ws.auto_filter.ref = f"A{first}:{W.L(len(cols))}{r - 1}"
        r += 2
    for col, w in (("A", 14), ("B", 10), ("C", 10), ("D", 12), ("E", 12), ("F", 12), ("G", 12), ("H", 14), ("I", 12),
                   ("J", 14), ("K", 44), ("L", 16), ("M", 12), ("N", 12), ("O", 12), ("P", 12), ("Q", 14), ("R", 12)):
        ws.column_dimensions[col].width = w


HTML_CSS = """
:root { --bg:#ffffff; --fg:#1b1f24; --muted:#5b6470; --line:#d9dee5; --head:#1f3864; --headfg:#ffffff; --rise:#ddebf7; --band:#f5f7fa; --accent:#2e75b6; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#0f1419; --fg:#e6e9ee; --muted:#9aa4b2; --line:#2a323c; --head:#1f3864; --headfg:#ffffff; --rise:#1a2b44; --band:#151b22; --accent:#6ea8e0; } }
:root[data-theme="dark"] { --bg:#0f1419; --fg:#e6e9ee; --muted:#9aa4b2; --line:#2a323c; --rise:#1a2b44; --band:#151b22; --accent:#6ea8e0; }
* { box-sizing:border-box } body { margin:0; padding:24px 16px; background:var(--bg); color:var(--fg); font:14px/1.45 -apple-system, "Segoe UI", Roboto, Arial, sans-serif; }
main { max-width:1200px; margin:0 auto } h1 { font-size:22px; margin:0 0 4px } h2 { font-size:17px; margin:28px 0 8px; color:var(--accent) }
p.sub { color:var(--muted); margin:0 0 16px } .wrap { overflow-x:auto; border:1px solid var(--line); border-radius:6px }
table { border-collapse:collapse; width:100%; font-size:13px } th, td { border-bottom:1px solid var(--line); padding:6px 9px; text-align:left; vertical-align:top; white-space:nowrap }
th { background:var(--head); color:var(--headfg); position:sticky; top:0 } th.rise { background:var(--accent) } td.rise { background:var(--rise) }
tbody tr:nth-child(even) td { background:var(--band) } tbody tr:nth-child(even) td.rise { background:var(--rise) } td.num { text-align:right; font-variant-numeric:tabular-nums }
td.wrap { white-space:normal; min-width:260px } details { margin-top:10px } summary { cursor:pointer; color:var(--accent) } .note { color:var(--muted); font-size:12px; margin:6px 0 0 }
"""


def _esc(v):
    import html
    return html.escape("" if v is None else str(v))


def _html_table(cols, rows, rise_cols=(), num_cols=(), wrap_cols=()):
    out = ['<div class="wrap"><table><thead><tr>']
    for c in cols:
        out.append(f'<th class="rise">{_esc(c)}</th>' if c in rise_cols else f"<th>{_esc(c)}</th>")
    out.append("</tr></thead><tbody>")
    for r in rows:
        out.append("<tr>")
        for c, v in zip(cols, r):
            cls = " ".join(x for x in ("rise" if c in rise_cols else "", "num" if (c in num_cols or isinstance(v, (int, float))) else "",
                                       "wrap" if c in wrap_cols else "") if x)
            out.append(f'<td class="{cls}">{_esc(v)}</td>' if cls else f"<td>{_esc(v)}</td>")
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def calls_html(folder, module, developer, device_label, out_path):
    """Standalone HTML page with the API / network comparison and tables (same data as sheet 10)."""
    apps, compare = calls_compare(folder)
    api, net = api_summary(folder), net_summary(folder)
    if not compare and not api and not net:
        return None
    title = f"API & network calls — {module.get('title', module['name'])}"
    rise = [a for a in apps if B.is_rise(a)]
    h = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'>"
         f"<title>{_esc(title)}</title><style>{HTML_CSS}</style></head><body><main>",
         f"<h1>{_esc(title)}</h1><p class='sub'>Measured on {_esc(device_label)} by {_esc(developer)}, {datetime.date.today().isoformat()}. "
         "Diagnostic, not scored. RISE's API rows come from its own log; competitor apps log nothing, so for them only hosts, "
         "connections, bytes and timing from the PCAPdroid capture are shown. Request paths and bodies of competitors stay encrypted.</p>"]
    if compare:
        h.append("<h2>Comparison</h2>")
        h.append(_html_table(["Metric"] + list(apps), [[l] + [v.get(a, "") for a in apps] for l, v in compare], rise_cols=rise,
                             wrap_cols=["Metric"] + list(apps)))
        h.append("<p class='note'>Medians over runs. Launch = cold start to home. Screen open = the L15 window (open prompt to loaded + 8 s). "
                 "Exercising = 60 s using the screen's controls (search, clear, tabs) in run 1. Time to first byte = connection opened to the first server packet with data.</p>")
    pointers = api_pointers(folder)
    if pointers:
        h.append("<h2>Where RISE's API calls need optimisation</h2><ul>")
        h += [f"<li><b>{_esc(t)}.</b> {_esc(d)}</li>" for t, d in pointers]
        h.append("</ul><p class='note'>Generated from the rows below by fixed rules (repeats, calls over 300 ms, cache misses, launch fan-out, connection reuse, analytics during the open, non-production hosts).</p>")
    if api:
        h.append("<h2>API calls per run (RISE, from its log)</h2>")
        cols = ["App", "Phase", "Run", "Calls", "Endpoints", "Repeats", "Errors", "Network ms (sum)", "Wall ms", "Longest ms", "Longest call", "CDN cache HIT/total", "Bytes"]
        h.append(_html_table(cols, [[s["app"], s["phase"], s["run"], s["calls"], s["endpoints"], s["repeats"], s["errors"], s["total_ms"], s["wall_ms"],
                                     s["longest_ms"], s["longest"], s["cache"], s["bytes"]] for s in api], wrap_cols=["Longest call"]))
        h.append("<p class='note'>Compare the wall time with L3 (screen fully rendered): the gap is rendering and app logic.</p>")
    if net:
        h.append("<h2>Network per run (PCAPdroid pass)</h2>")
        cols = ["App", "Run", "Phase", "Connections", "Hosts", "Third-party hosts", "KB in", "KB out", "Median first-byte ms", "Third-party list"]
        h.append(_html_table(cols, [[s["app"], s["run"], s["phase"], s["connections"], s["hosts"], len(s["third_party"]), s["kb_in"], s["kb_out"],
                                     s["median_first_response_ms"], ", ".join(s["third_party"])] for s in net], wrap_cols=["Third-party list"]))
    for name, ttl in (("api_calls.csv", "Every API call"), ("net_calls.csv", "Every connection")):
        rows = B.read_calls(folder, name)
        if not rows:
            continue
        cols = [c for c in B.CALLS_FILES[name] if c not in ("module", "module_version", "developer", "device_model", "package", "version", "source", "artifact")]
        h.append(f"<details><summary>{_esc(ttl)} ({len(rows)} rows, {name})</summary>")
        h.append(_html_table(cols, [[r.get(c, "") for c in cols] for r in rows[:MAX_LISTING]]))
        h.append("</details>")
    h.append("</main></body></html>")
    Path(out_path).write_text("\n".join(h))
    return out_path


def module_report(a):
    module = B.load_module(a.module)
    developer = B.get_developer(a.developer)
    if a.device_model:
        model = a.device_model
    else:
        base = Path(a.results_dir) if a.results_dir else B.RESULTS_DIR
        cands = sorted((base / module["name"]).glob(f"{B.safe_name(developer)}_*"))
        if not cands:
            sys.exit(f"No results for {developer} under {base / module['name']}. Pass --device-model if the folder name differs.")
        if len(cands) > 1:
            print("  Several phones found; using the most recent: " + ", ".join(c.name for c in cands))
        folder = max(cands, key=lambda p: latest_ts(B.read_runs(p / "runs.csv")))
        model = folder.name.split("_", 1)[1]
    folder = B.results_dir(module["name"], developer, model, a.results_dir)
    rows = B.read_runs(folder / "runs.csv")
    if not rows:
        sys.exit(f"No runs.csv in {folder}")
    app_folder = B.results_dir(B.APP_SCOPE, developer, model, a.results_dir)
    app_rows = B.read_runs(app_folder / "runs.csv")
    out_dir = (Path(a.out) if a.out else B.REPORTS_DIR / module["name"])
    out_dir.mkdir(parents=True, exist_ok=True)
    date = datetime.date.today().isoformat()
    out = out_dir / f"{module['name']}_{B.safe_name(developer)}_{B.safe_name(model)}_{date}.xlsx"
    apps = fill_module_workbook(module, folder, rows, app_rows, out, developer, model)
    print(f"  Workbook: {out}")
    if a.html:
        page = calls_html(folder, module, developer, model, out.with_name(out.stem + "_api.html"))
        print(f"  HTML: {page}" if page else "  HTML: no api_calls.csv / net_calls.csv in the results folder, nothing to write")

    ranked = [x for x in apps if B.load_apps().get(x, {}).get("ranked", True)]
    app_rows = [r for r in app_rows if r["app"] in apps]
    med = medians(rows + app_rows, module, set(apps))
    cs = category_scores(metric_scores(med, ranked), ranked)
    ov = overall(cs, B.load_weights(), ranked)
    cov = coverage(cs, B.load_weights(), ranked)
    print(f"  RISE on {model}: overall {ov.get('RISE')} (rank {rank_of(ov, 'RISE')} of {sum(1 for v in ov.values() if v is not None)}; "
          f"coverage {cov.get('RISE')}% of weight, others {', '.join(f'{a} {cov[a]}%' for a in ranked if not B.is_rise(a))})")
    for cat in B.CATEGORIES:
        if cat in cs and "RISE" in cs[cat]:
            print(f"    {cat:<22} score {cs[cat]['RISE']:>5}  rank {rank_of(cs[cat], 'RISE')}")
    for line in calls_lines(folder):
        print(f"  {line}")
    for app, n, gaps, mism in completeness(module, folder, rows):
        if n:
            print(f"  {app}: {n} metric(s) still missing" + (f"; {mism} row(s) from an older module version" if mism else ""))


# ---------------------------------------------------------------- combined

def combined_report(a):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter as L

    base = Path(a.results_dir) if a.results_dir else B.RESULTS_DIR
    runs = B.all_runs(base)
    if not runs:
        sys.exit(f"No results under {base}")
    by_mod = group_folders(runs)
    weights = B.load_weights()
    reg = B.load_apps()
    date = datetime.date.today().isoformat()
    out_dir = Path(a.out) if a.out else B.REPORTS_DIR / "combined"
    out_dir.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    sc = wb.active
    sc.title = "Scorecard"
    head = Font(bold=True, color="FFFFFF"); hfill = PatternFill("solid", fgColor="1F3864")
    rise_fill = PatternFill("solid", fgColor="DDEBF7")

    def header(ws, row, cols):
        for i, h in enumerate(cols):
            c = ws.cell(row=row, column=1 + i, value=h); c.font = head; c.fill = hfill
            c.alignment = Alignment(wrap_text=True, vertical="center")
        ws.row_dimensions[row].height = 30

    md = [f"# RISE benchmark scorecard — {date}", "",
          "Within a module every app was measured on one phone, so ranks are fair. Across modules the phones differ: "
          "compare RISE's **rank** and **0–100 score**, never raw values.", ""]

    # ---- per-module scorecard rows
    cats = B.CATEGORIES
    cols = ["Module", "Phone", "Developer", "Measured", "Apps ranked", "RISE overall", "RISE rank", "RISE coverage %", "Coverage of others"] + \
           [f"{c} (score / rank)" for c in cats] + ["Other folders for this module"]
    sc["A1"] = f"RISE benchmark — combined scorecard ({date})"; sc["A1"].font = Font(size=14, bold=True)
    sc["A2"] = "Per module: RISE's 0–100 score and rank among the ranked apps measured on that phone. Weights from weights.json."
    header(sc, 4, cols)
    r = 5
    md += ["## Per module", "",
           "Coverage = share of the scorecard weight that has data. Compare ranks only when coverages are similar.", "",
           "| Module | Phone | Developer | Apps | RISE overall | RISE rank | RISE coverage | Others' coverage | " + " | ".join(cats) + " |",
           "|---|---|---|---|---|---|---|---|" + "---|" * len(cats)]
    rise_overall, rise_ranks, module_sheets, calls_md = [], [], [], []
    for module_name in sorted(by_mod):
        if module_name == B.APP_SCOPE:
            continue
        try:
            module = B.load_module(module_name)
        except SystemExit:
            print(f"  ! results for '{module_name}' but no modules/{module_name}.json; skipped")
            continue
        (folder, rows), others = by_mod[module_name][0], by_mod[module_name][1:]
        developer = rows[0].get("developer", folder.name.split("_", 1)[0]) if rows else ""
        phone = rows[0].get("device_model", "") if rows else folder.name.split("_", 1)[-1]
        app_folder = base / B.APP_SCOPE / folder.name
        app_rows = B.read_runs(app_folder / "runs.csv")
        apps = module_apps(module, rows, app_rows)
        app_rows = [x for x in app_rows if x["app"] in apps]
        ranked = [x for x in apps if reg.get(x, {}).get("ranked", True)]
        med = medians(rows + app_rows, module, set(apps))
        ms = metric_scores(med, ranked)
        cs = category_scores(ms, ranked)
        ov = overall(cs, weights, ranked)
        cov = coverage(cs, weights, ranked)
        rk = rank_of(ov, "RISE")
        others_cov = "; ".join(f"{x} {cov[x]}%" for x in ranked if not B.is_rise(x) and cov.get(x) is not None)
        if ov.get("RISE") is not None:
            rise_overall.append(ov["RISE"]); rise_ranks.append(rk)
        cells = [module.get("title", module_name), phone, developer, latest_ts(rows)[:10], len([x for x in ranked if ov.get(x) is not None]),
                 ov.get("RISE"), rk, cov.get("RISE"), others_cov]
        md_cells = []
        for cat in cats:
            if cat in cs and "RISE" in cs[cat]:
                cells.append(f"{cs[cat]['RISE']} / {rank_of(cs[cat], 'RISE')}")
                md_cells.append(f"{cs[cat]['RISE']} / #{rank_of(cs[cat], 'RISE')}")
            else:
                cells.append(""); md_cells.append("–")
        cells.append("; ".join(o[0].name for o in others))
        for i, v in enumerate(cells):
            sc.cell(row=r, column=1 + i, value=v)
        r += 1
        md.append(f"| {cells[0]} | {phone} | {developer} | {cells[4]} | {ov.get('RISE') if ov.get('RISE') is not None else '–'} | "
                  f"{('#' + str(rk)) if rk else '–'} | {cov.get('RISE', '–')}% | {others_cov or '–'} | " + " | ".join(md_cells) + " |")
        module_sheets.append((module, module_name, apps, ranked, med, ms, cs, ov, phone))
        cl = calls_lines(folder)
        if cl:
            calls_md.append(f"- **{module.get('title', module_name)}** ({phone}): " + ". ".join(cl))
    if calls_md:
        md += ["", "### API and network calls (diagnostic, phone-specific, not comparable across modules)", ""] + calls_md
    if rise_overall:
        sc.cell(row=r, column=1, value="RISE overall (mean of modules)").font = Font(bold=True)
        sc.cell(row=r, column=6, value=round(statistics.mean(rise_overall), 1)).font = Font(bold=True)
        sc.cell(row=r, column=7, value=round(statistics.mean(x for x in rise_ranks if x), 2)).font = Font(bold=True)
        md += ["", f"**RISE overall:** mean score {round(statistics.mean(rise_overall), 1)}, mean rank "
               f"{round(statistics.mean(x for x in rise_ranks if x), 2)} across {len(rise_overall)} module(s)."]
    for i in range(1, len(cols) + 1):
        sc.column_dimensions[L(i)].width = 16
    sc.column_dimensions["A"].width = 22

    # ---- phone-scoped block
    r += 3
    sc.cell(row=r, column=1, value="Phone-scoped metrics (_app), per phone").font = Font(bold=True, size=12)
    r += 1
    phone_mids = B.PHONE_METRICS
    header(sc, r, ["Phone", "Developer", "App"] + phone_mids + ["RISE rank (overall of these)"])
    r += 1
    md += ["", "## Phone-scoped metrics (once per phone)", "", "| Phone | Developer | App | " + " | ".join(phone_mids) + " |",
           "|---|---|---|" + "---|" * len(phone_mids)]
    for folder, rows in by_mod.get(B.APP_SCOPE, []):
        app_mod = B.load_module(B.APP_SCOPE)
        apps = B.app_order({x["app"] for x in rows})
        ranked = [x for x in apps if reg.get(x, {}).get("ranked", True)]
        med = medians(rows, app_mod, set(apps))
        ov = overall(category_scores(metric_scores(med, ranked), ranked), weights, ranked)
        phone = rows[0].get("device_model", folder.name) if rows else folder.name
        developer = rows[0].get("developer", "") if rows else ""
        for app in apps:
            vals = [med.get(app, {}).get(m) for m in phone_mids]
            cells = [phone, developer, app] + vals + [rank_of(ov, app) if B.is_rise(app) else ""]
            for i, v in enumerate(cells):
                c = sc.cell(row=r, column=1 + i, value=v)
                if B.is_rise(app):
                    c.fill = rise_fill
            r += 1
            md.append(f"| {phone} | {developer} | {app} | " + " | ".join("–" if v is None else str(v) for v in vals) + " |")

    # ---- per-module sheets
    for module, module_name, apps, ranked, med, ms, cs, ov, phone in module_sheets:
        ws = wb.create_sheet(module_name[:31])
        ws["A1"] = f"{module.get('title', module_name)} — medians per app on {phone}"; ws["A1"].font = Font(bold=True, size=12)
        header(ws, 3, ["ID", "Metric", "Unit", "Better"] + apps + ["Best", "RISE gap vs best"])
        rr = 4
        for m in B.METRIC_CATALOGUE:
            mid = m["id"]
            if not any(mid in med.get(x, {}) for x in apps):
                continue
            best_app, gap = best_and_gap(med, mid, ranked)
            vals = [mid, B.render(m["name"], module), m["unit"], m["better"]] + [med.get(x, {}).get(mid) for x in apps] + [best_app, gap]
            for i, v in enumerate(vals):
                c = ws.cell(row=rr, column=1 + i, value=v)
                if i >= 4 and i - 4 < len(apps) and B.is_rise(apps[i - 4]):
                    c.fill = rise_fill
            rr += 1
        rr += 1
        header(ws, rr, ["Category", "Weight"] + apps); rr += 1
        for cat in cats:
            if cat in cs:
                vals = [cat, weights[cat]] + [cs[cat].get(x) for x in apps]
                for i, v in enumerate(vals):
                    ws.cell(row=rr, column=1 + i, value=v)
                rr += 1
        vals = ["Overall (weighted)", ""] + [ov.get(x) for x in apps]
        for i, v in enumerate(vals):
            ws.cell(row=rr, column=1 + i, value=v).font = Font(bold=True)
        rr += 1
        vals = ["Rank", ""] + [rank_of(ov, x) if x in ranked else "unranked" for x in apps]
        for i, v in enumerate(vals):
            ws.cell(row=rr, column=1 + i, value=v).font = Font(bold=True)
        ws.column_dimensions["B"].width = 50
        for i in range(5, 5 + len(apps) + 2):
            ws.column_dimensions[L(i)].width = 13
        md += ["", f"## {module.get('title', module_name)} ({phone})", "",
               "| Category | " + " | ".join(apps) + " |", "|---|" + "---|" * len(apps)]
        for cat in cats:
            if cat in cs:
                md.append(f"| {cat} | " + " | ".join("–" if cs[cat].get(x) is None else str(cs[cat][x]) for x in apps) + " |")
        md.append("| **Overall** | " + " | ".join("–" if ov.get(x) is None else f"**{ov[x]}**" for x in apps) + " |")
        md.append("| Rank | " + " | ".join(str(rank_of(ov, x)) if x in ranked and ov.get(x) is not None else "–" for x in apps) + " |")

    # ---- completeness
    ws = wb.create_sheet("Completeness")
    header(ws, 1, ["Module", "Folder", "App", "Metrics missing", "Which", "Rows from older module version", "Latest folder?"])
    rr = 2
    md += ["", "## Completeness", "", "| Module | Folder | App | Missing | Older-version rows |", "|---|---|---|---|---|"]
    for module_name, folders in sorted(by_mod.items()):
        try:
            module = B.load_module(module_name)
        except SystemExit:
            continue
        for idx, (folder, rows) in enumerate(folders):
            for app, n, gaps, mism in completeness(module, folder, rows):
                which = ", ".join(gaps[:15]) + (f" … +{len(gaps) - 15}" if len(gaps) > 15 else "")
                latest = "per phone" if module_name == B.APP_SCOPE else ("yes" if idx == 0 else "no (older)")
                for i, v in enumerate([module_name, folder.name, app, n, which, mism, latest]):
                    ws.cell(row=rr, column=1 + i, value=v)
                rr += 1
                if n or mism:
                    md.append(f"| {module_name} | {folder.name} | {app} | {n} | {mism} |")
    ws.column_dimensions["B"].width = 34; ws.column_dimensions["E"].width = 80
    if md[-1].startswith("|---"):
        md.append("| – | – | – | 0 | 0 |")

    xlsx = out_dir / f"combined_{date}.xlsx"
    mdp = out_dir / f"scorecard_{date}.md"
    wb.save(xlsx)
    mdp.write_text("\n".join(md) + "\n")
    print(f"  Combined workbook: {xlsx}\n  Scorecard: {mdp}")
    print("\n".join(md[:60]))


# ---------------------------------------------------------------- METRICS.md

def metrics_md(a):
    lines = ["# Metric catalogue", "",
             "Generated from `benchlib.py` by `python3 build_report.py --metrics-md`; do not edit by hand.",
             "Placeholders `{screen}`, `{list}` and `{detail}` are filled from each module's definition. "
             "**Phone** = measured once per developer and phone under module `_app`. **Applies** = only when the module sets that flag.",
             "", "| ID | Category | Metric | Unit | Better | Runs | Tool | Scope |", "|---|---|---|---|---|---|---|---|"]
    for m in B.METRIC_CATALOGUE:
        scope = "phone" if m["phone"] else (f"if {m['applies']}" if m["applies"] else "module")
        lines.append(f"| {m['id']} | {m['category']} | {m['name']} | {m['unit']} | {m['better']} | {m['runs']} | {m['tool']} | {scope} |")
    lines += ["", "## How to measure", ""]
    for m in B.METRIC_CATALOGUE:
        auto = "automated by bench.py" if m["id"] in B.AUTOMATED else "manual, recorded with record.py"
        lines += [f"### {m['id']} — {m['name']}", "", f"*{m['category']} · {m['unit']} · {m['better']} is better · {m['runs']} run(s) · {auto}*", "",
                  m["how"], ""]
    lines += ["## Groups in bench.py", ""]
    for g, ids in B.BENCH_GROUPS.items():
        lines.append(f"- `--group {g}`: {', '.join(ids)}")
    lines += ["", "Added on 22 Oct 2026 from the Groww Quote-page report: L14, L15, S7, U4, U5, R9, X4."]
    (B.HERE / "METRICS.md").write_text("\n".join(lines) + "\n")
    print(f"  METRICS.md written with {len(B.METRIC_CATALOGUE)} metrics")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--module")
    p.add_argument("--developer")
    p.add_argument("--device-model")
    p.add_argument("--results-dir")
    p.add_argument("--out", help="output folder (default reports/<module> or reports/combined)")
    p.add_argument("--combined", action="store_true")
    p.add_argument("--html", action="store_true", help="with --module: also write the API / network comparison as <workbook>_api.html")
    p.add_argument("--metrics-md", action="store_true")
    a = p.parse_args()
    if a.metrics_md:
        metrics_md(a)
    elif a.combined:
        combined_report(a)
    elif a.module:
        module_report(a)
    else:
        p.print_help()


if __name__ == "__main__":
    main()

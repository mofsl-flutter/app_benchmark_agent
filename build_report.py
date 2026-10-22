#!/usr/bin/env python3
"""Reports from the shared results folder.

  python3 build_report.py --module fno [--developer NAME] [--device-model MODEL]
        One module's workbook, filled from results/fno/<developer>_<device>/runs.csv (+ the same
        developer's _app folder for phone-scoped metrics). -> reports/fno/fno_<dev>_<device>_<date>.xlsx

  python3 build_report.py --combined
        Every module, every developer -> reports/combined/combined_<date>.xlsx and scorecard_<date>.md
        Ranks and 0-100 scores are compared across modules; raw values are not (different phones).

  python3 build_report.py --metrics-md
        Regenerates METRICS.md from the catalogue in benchlib.py.
"""
import argparse
import datetime
import statistics
import sys
from collections import defaultdict
from pathlib import Path

import benchlib as B

RUN_FIRST, COL_NOTE = 7, 16


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
    wb.save(out_path)
    return apps


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
    rise_overall, rise_ranks, module_sheets = [], [], []
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

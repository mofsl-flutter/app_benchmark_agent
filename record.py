#!/usr/bin/env python3
"""Record a manual metric value (or an offline / data-pointer item answer) for one app and module.

Usage:
  python3 record.py --me "Vivek Dubey"                                  # store your name once
  python3 record.py --pcapdroid-key <key>                                # once per developer, for bench.py --group net
  python3 record.py --module fno --app Groww L14 --run 2 --value 1840 --note "Overview → Technicals"
  python3 record.py --module fno --app Groww O1 --item "Stale-data label" --value Partial
  python3 record.py --module fno --app Groww D1 --item "Indices strip" --value Yes
  python3 record.py --module fno --app Groww --list                       # what is still missing
  python3 record.py --module fno --app Groww --items                      # the module's O1 / D1 items

The phone model comes from the connected phone (or --device-model). Rows are appended to
results/<module>/<developer>_<device-model>/runs.csv with source=manual.
"""
import argparse
import sys

import benchlib as B

ITEM_VALUES = ("Yes", "Partial", "No", "N/A")


def device_model(a):
    if a.device_model:
        return a.device_model
    import bench
    adb = bench.Adb(a.serial)
    adb.ensure_device()
    return bench.device_props(adb)["model"]


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("metric", nargs="?", help="metric ID, e.g. L14, or O1 / D1 with --item")
    p.add_argument("-s", "--serial")
    p.add_argument("--me", help="store your developer name in ~/.riise-benchmark/me.json and exit")
    p.add_argument("--pcapdroid-key", metavar="KEY",
                   help="store the PCAPdroid API key (Settings → Control permissions → ⋮ → API key) in me.json for bench.py --group net")
    p.add_argument("--module")
    p.add_argument("--app")
    p.add_argument("--developer")
    p.add_argument("--device-model", help="phone model string; read from adb when omitted")
    p.add_argument("--results-dir")
    p.add_argument("--run", type=int, help="run number (default: next missing)")
    p.add_argument("--value", help="number, or Yes/Partial/No/N/A for --item")
    p.add_argument("--item", help="offline_items / data_items entry (for O1 / D1)")
    p.add_argument("--note", default="")
    p.add_argument("--artifact", default="", help="local recording / trace file name")
    p.add_argument("--list", action="store_true", help="show what is still missing for this app")
    p.add_argument("--items", action="store_true", help="show the module's O1 and D1 items")
    a = p.parse_args()

    if a.me or a.pcapdroid_key:
        B.write_me(a.me, pcapdroid_api_key=a.pcapdroid_key)
        if a.me:
            print(f"  Saved developer = {B.safe_name(a.me)} in {B.ME_FILE}")
        if a.pcapdroid_key:
            print(f"  Saved the PCAPdroid API key in {B.ME_FILE} (kept out of the repo)")
        return
    if not a.module:
        sys.exit("--module is required")
    module = B.load_module(a.module)

    if a.items:
        print("  O1 offline items:")
        for it in module.get("offline_items", []):
            print(f"    O1.{B.slug(it):<48} {it}")
        print("  D1 data items:")
        for it in module.get("data_items", []):
            print(f"    D1.{B.slug(it):<48} {it}")
        return

    if not a.app:
        sys.exit("--app is required")
    app = B.resolve_app(a.app)
    developer = B.get_developer(a.developer)
    folder = B.results_dir(module["name"], developer, device_model(a), a.results_dir)

    if a.list:
        gaps = B.missing(module, folder, app)
        if not gaps:
            print(f"  {app}: everything recorded for module {module['name']}")
            return
        print(f"  {app} · module {module['name']} · still missing ({folder}):")
        for mid, (done, n) in sorted(gaps.items(), key=lambda kv: (kv[0].split(".")[0], kv[0])):
            base = mid.split(".", 1)[0]
            how = "bench.py" if base in B.AUTOMATED else B.METRICS[base]["tool"]
            name = B.render(B.METRICS[base]["name"], module) if "." not in mid else mid
            print(f"    {mid:<40} {done}/{n}  {how:<28} {name}")
        return

    if not a.metric or a.value is None:
        sys.exit("Give a metric ID and --value (or --list / --items).")
    mid = a.metric.upper()
    if mid not in B.METRICS:
        sys.exit(f"Unknown metric {mid}. See METRICS.md.")
    ok, why = B.metric_applies(mid, module)
    if not ok:
        sys.exit(f"{mid} does not apply to module {module['name']}: {why}")

    if mid in ("O1", "D1"):
        if not a.item:
            sys.exit(f"{mid} is recorded per item: add --item \"<item text>\" (see --items).")
        items = module["offline_items"] if mid == "O1" else module["data_items"]
        match = [it for it in items if it == a.item or B.slug(it) == B.slug(a.item)]
        if not match:
            sys.exit(f"'{a.item}' is not in the module's {'offline_items' if mid == 'O1' else 'data_items'} (see --items).")
        val = a.value.strip().capitalize() if a.value.strip().upper() != "N/A" else "N/A"
        if val not in ITEM_VALUES:
            sys.exit(f"--value must be one of {', '.join(ITEM_VALUES)}")
        metric_key = f"{mid}.{B.slug(match[0])}"
        row = {"metric": metric_key, "run": 1, "value": val, "note": a.note, "source": "manual", "artifact": a.artifact}
    else:
        try:
            val = float(a.value)
        except ValueError:
            sys.exit(f"--value must be a number for {mid}")
        run = a.run or B.next_run(folder, app, mid)
        if run > B.NRUNS:
            sys.exit(f"{mid} already has {B.NRUNS} runs. Pass --run N to replace one (the old value goes to the note).")
        note = a.note
        if a.run and a.run in B.runs_done(folder, app, mid):
            prev = [r for r in B.read_runs(folder / "runs.csv") if r["app"] == app and r["metric"] == mid
                    and int(float(r.get("run") or 0)) == a.run and r["num"] is not None]
            if prev:
                note = f"replaces {prev[-1]['num']} (run {a.run})" + (f"; {a.note}" if a.note else "")
        row = {"metric": mid, "run": run, "value": val, "note": note, "source": "manual", "artifact": a.artifact}

    meta = {"app": app, "developer": developer, "pkg": B.load_apps().get(app, {}).get("package", ""),
            "version": "", "model": folder.name.split("_", 1)[1], "android": "", "ram_gb": ""}
    envs = B.read_env(folder)
    if envs:
        last = envs[-1]
        meta.update({"android": last.get("android", ""), "ram_gb": last.get("device_ram_gb", "")})
        for part in (last.get("app_versions") or "").split(";"):
            if "=" in part and part.strip().split("=", 1)[0] == app:
                meta["version"] = part.strip().split("=", 1)[1]
    path = B.append_rows(folder, [row], meta, module)
    print(f"  Recorded {row['metric']} run {row['run']} = {row['value']} for {app} → {path}")


if __name__ == "__main__":
    main()

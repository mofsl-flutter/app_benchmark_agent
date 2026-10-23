#!/usr/bin/env python3
"""Offline checklist (O1 items) with a per-app network block instead of airplane mode.

Only the app under test loses its network (cmd connectivity set-package-networking-enabled), so
adb, Wi-Fi and every other app keep working and nothing has to reconnect. The script walks the
developer through: network lost on the screen → detail screen offline → cold launch offline →
reconnect, and asks each of the module's offline_items at the step where it can be seen.
Answers: y = Yes, p = Partial, n = No, na = N/A. Rows go to runs.csv as O1.<item>.

  python3 offline.py RISE --module mf

Read-only: open and close screens only; never tap buy, invest, SIP, redeem, withdraw or add money.
"""
import argparse
import re
import sys
import time

import benchlib as B
import bench
from bench import Adb, Abort, ask

ANSWERS = {"y": "Yes", "p": "Partial", "n": "No", "na": "N/A"}
# Which step each standard item is observed at, by keywords in its text; anything else is asked at the end.
PHASES = [("lost", ("network lost", "offline message", "banner", "not presented as live")),
          ("detail", ("opens offline",)),
          ("cold", ("cold launch", "last updated", "stale")),
          ("reconnect", ("reconnect", "re-login"))]


def phase_of(item):
    t = item.lower()
    for name, words in PHASES:
        if any(w in t for w in words):
            return name
    return "end"


def answer(q):
    while True:
        try:
            r = input(f"  ? {q} [y/p/n/na, q = stop] ").strip().lower()
        except EOFError:
            raise Abort()
        if r == "q":
            raise Abort()
        if r in ANSWERS:
            return ANSWERS[r]


def crash_count(adb, pkg):
    out = adb.sh(f"dumpsys activity exit-info {pkg}", check=False)
    return len(re.findall(r"reason=(?:4|5|6) ", out))  # CRASH, CRASH_NATIVE, ANR


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("app")
    p.add_argument("--module", required=True)
    p.add_argument("-s", "--serial")
    p.add_argument("--developer")
    p.add_argument("--results-dir")
    p.add_argument("--pkg")
    a = p.parse_args()
    app = bench.resolve_app(a.app)
    module = B.load_module(a.module)
    screen = B.app_screen(module, app)
    if module["name"] == B.APP_SCOPE or screen is None:
        sys.exit(f"{app} has no screen for module {module['name']}.")
    detail = module["rise"].get("detail", "the detail screen")
    developer = B.get_developer(a.developer)
    adb = Adb(a.serial); adb.ensure_device(); bench.ensure_screen_ready(adb)
    pkg = bench.resolve_pkg(app, a.pkg)
    comp = bench.launcher_component(adb, pkg)
    d = bench.device_props(adb)
    meta = {"app": app, "developer": developer, "pkg": pkg, "version": bench.version_name(adb, pkg),
            "model": d["model"], "android": d["android"], "ram_gb": d["ram_gb"]}
    folder = B.results_dir(module["name"], developer, d["model"], a.results_dir)
    done = {r["metric"] for r in B.read_runs(folder / "runs.csv") if r["app"] == app}
    items = [it for it in module.get("offline_items", []) if f"O1.{B.slug(it)}" not in done]
    if not items:
        print(f"  {app}: every offline item is already recorded.")
        return
    by_phase = {}
    for it in items:
        by_phase.setdefault(phase_of(it), []).append(it)
    net = lambda on: adb.sh(f"cmd connectivity set-package-networking-enabled {'true' if on else 'false'} {pkg}")
    crashes0 = crash_count(adb, pkg)
    rows = []

    def ask_items(phase):
        for it in by_phase.get(phase, []):
            rows.append({"ts": B.now_iso(), "metric": f"O1.{B.slug(it)}", "run": 1, "value": answer(it),
                         "note": "offline.py (per-app network block)", "source": "offline.py", "artifact": ""})

    print(f"\nOffline checklist: {app} · module {module['name']} · screen: {screen} · {len(items)} item(s)")
    print("Read-only: open and close screens only.")
    try:
        ask(f"Open {screen} (online, fully loaded). Press Enter to cut this app's network.")
        net(False)
        print("    Network blocked for this app only. Watch the screen for 10 s.")
        time.sleep(10)
        ask_items("lost")
        if by_phase.get("detail"):
            ask(f"Open {detail} (still offline; open only, submit nothing). Look, then press Enter.")
            ask_items("detail")
            ask(f"Press Back to {screen}. Press Enter.")
        if by_phase.get("cold"):
            ask("Press Enter to cold-launch the app while still offline.")
            adb.sh(f"am force-stop {pkg}"); time.sleep(1)
            adb.sh(f"am start -n {comp}")
            ask(f"Enter the PIN if asked and try to open {screen} (offline). Press Enter when you've seen the result.")
            ask_items("cold")
        net(True)
        print("    Network restored. Wait 15 s without touching the phone.")
        time.sleep(15)
        ask_items("reconnect")
        new = crash_count(adb, pkg) - crashes0
        print(f"    Crash/ANR records during the test: {max(new, 0)}")
        for it in by_phase.get("end", []):
            if "crash" in it.lower() and new > 0:
                rows.append({"ts": B.now_iso(), "metric": f"O1.{B.slug(it)}", "run": 1, "value": "No",
                             "note": f"offline.py: {new} crash/ANR record(s)", "source": "offline.py", "artifact": ""})
            else:
                rows.append({"ts": B.now_iso(), "metric": f"O1.{B.slug(it)}", "run": 1, "value": answer(it),
                             "note": "offline.py (per-app network block)", "source": "offline.py", "artifact": ""})
    except (Abort, KeyboardInterrupt):
        print("\n  Stopped early, saving what was answered.")
    finally:
        net(True)
        if rows:
            B.append_rows(folder, rows, meta, module)
    print("  " + ", ".join(f"{r['metric'][3:]}={r['value']}" for r in rows))
    print(f"  Saved to {folder / 'runs.csv'}")


if __name__ == "__main__":
    main()

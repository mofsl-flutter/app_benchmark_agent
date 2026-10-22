#!/usr/bin/env python3
"""Pre-run checks for one block of benchmark runs (PROTOCOL.md "Before each block of runs").

Hard failures (exit 1): more than one device, private DNS fixed to a hostname, power saving on,
battery below 50 %. Soft findings are printed and recorded. Everything is written as one row to
results/<module>/<developer>_<device>/env.csv so every result can be traced to its conditions.

Usage:
  python3 preflight.py --module fno                 # checks + env row
  python3 preflight.py --module fno --fix           # also turn on Show taps
  python3 preflight.py --module fno --speedtest 180 --holdings "RISE=42, Groww=10" --notes "..."
"""
import argparse
import re
import sys

import benchlib as B
import bench

MIN_BATTERY = 50


def setting(adb, ns, key):
    v = adb.sh(f"settings get {ns} {key}", check=False).strip()
    return "" if v in ("null", "") else v


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-s", "--serial")
    p.add_argument("--module", required=True)
    p.add_argument("--developer")
    p.add_argument("--results-dir")
    p.add_argument("--fix", action="store_true", help="turn on Show taps if it is off")
    p.add_argument("--speedtest", help="measured download Mbps (free text)")
    p.add_argument("--holdings", help="holdings / watchlist size per app, free text")
    p.add_argument("--notes", default="")
    p.add_argument("--no-env", action="store_true", help="only check; do not write env.csv")
    a = p.parse_args()

    module = B.load_module(a.module)
    developer = B.get_developer(a.developer)
    adb = bench.Adb(a.serial)
    adb.ensure_device()
    d = bench.device_props(adb)
    hard, soft, env = [], [], {}

    dns = setting(adb, "global", "private_dns_mode")
    env["private_dns_mode"] = dns or "off"
    if dns == "hostname":
        hard.append(f"Private DNS is fixed to {setting(adb, 'global', 'private_dns_specifier') or 'a hostname'}. Set it to Automatic.")

    lp = setting(adb, "global", "low_power") or "0"
    env["low_power"] = lp
    if lp != "0":
        hard.append("Power saving is on. Turn it off (it also resets Motion smoothness).")

    bat = adb.sh("dumpsys battery")
    level = re.search(r"level:\s*(\d+)", bat)
    level = int(level.group(1)) if level else None
    env["battery_pct"] = level
    if level is not None and level < MIN_BATTERY:
        hard.append(f"Battery at {level} %. Charge above {MIN_BATTERY} % first.")
    charging = "USB powered: true" in bat or "AC powered: true" in bat or "Wireless powered: true" in bat
    env["charging"] = "yes" if charging else "no"
    if charging:
        soft.append("Phone is charging: temperature readings (C3) run high. Prefer wireless debugging, unplugged.")

    st = setting(adb, "system", "show_touches") or "0"
    if st != "1" and a.fix:
        adb.sh("settings put system show_touches 1", check=False)
        st = "1"
    env["show_touches"] = st
    if st != "1":
        soft.append("Show taps is off: tap moments won't be visible in recordings (rerun with --fix or enable it in Developer options).")

    scales = [setting(adb, "global", k) or "1.0" for k in ("window_animation_scale", "transition_animation_scale", "animator_duration_scale")]
    env["animation_scales"] = "/".join(scales)
    if any(s not in ("1", "1.0") for s in scales):
        soft.append(f"Animation scales are {env['animation_scales']}; the protocol keeps them at 1.0.")

    env["refresh_rate_mode"] = setting(adb, "secure", "refresh_rate_mode") or setting(adb, "system", "peak_refresh_rate") or ""
    disp = adb.sh("dumpsys display", timeout=60, check=False)
    rr = re.search(r"mActiveRenderFrameRate=([\d.]+)", disp) or re.search(r"renderFrameRate=([\d.]+)", disp)
    env["render_rate_hz"] = rr.group(1) if rr else ""

    th = adb.sh("dumpsys thermalservice", check=False)
    ts = re.search(r"Thermal Status:\s*(\d+)", th)
    env["thermal_status"] = ts.group(1) if ts else ""
    if ts and int(ts.group(1)) >= 2:
        soft.append(f"Thermal status {ts.group(1)}: let the phone cool before timing runs.")

    wifi = adb.sh("dumpsys wifi", timeout=60, check=False)
    rssi = re.search(r"RSSI:\s*(-?\d+)", wifi) or re.search(r"rssi=(-?\d+)", wifi)
    link = re.search(r"Link speed:\s*(\d+)", wifi) or re.search(r"(?:tx|rx)?[Ll]ink[Ss]peed[=:]\s*(\d+)", wifi)
    env["wifi_rssi_dbm"] = rssi.group(1) if rssi else ""
    env["wifi_link_mbps"] = link.group(1) if link else ""
    if not rssi:
        soft.append("Could not read the Wi-Fi signal; note it by hand.")

    found = bench.installed_apps(adb)
    env["app_versions"] = "; ".join(f"{n}={bench.version_name(adb, pkg)}" for n, pkg in found.items())

    env.update({"timestamp": B.now_iso(), "module": module["name"], "developer": developer,
                "device_model": d["model"], "device_ram_gb": d["ram_gb"], "android": d["android"],
                "speedtest_mbps": a.speedtest or "", "holdings": a.holdings or "", "notes": a.notes})

    print(f"  {d['model']} · Android {d['android']} · {d['ram_gb']} GB · battery {level}% · "
          f"{'charging' if charging else 'on battery'} · render {env['render_rate_hz'] or '?'} Hz · "
          f"Wi-Fi {env['wifi_rssi_dbm'] or '?'} dBm / {env['wifi_link_mbps'] or '?'} Mbps")
    print(f"  Installed: {', '.join(found) or 'none of the registry apps'}")
    for s in soft:
        print(f"  ~ {s}")
    for h in hard:
        print(f"  ✗ {h}")
    if not a.no_env:
        folder = B.results_dir(module["name"], developer, d["model"], a.results_dir)
        path = B.append_env(folder, env)
        print(f"  Env row written: {path}")
    if hard:
        sys.exit(1)
    print("  Pre-flight OK")


if __name__ == "__main__":
    main()

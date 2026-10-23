#!/usr/bin/env python3
"""Shared pieces of the RISE benchmark harness: the metric catalogue, module definitions,
app registry, developer identity, and the results files every script reads or writes.

Nothing here talks to a phone. bench.py, preflight.py, record.py and build_report.py import it.
"""
import csv
import datetime
import hashlib
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
APPS_FILE = HERE / "apps.json"
MODULES_DIR = HERE / "modules"
RESULTS_DIR = HERE / "results"
REPORTS_DIR = HERE / "reports"
WEIGHTS_FILE = HERE / "weights.json"
ME_FILE = Path(os.environ.get("RIISE_BENCH_HOME", Path.home() / ".riise-benchmark")) / "me.json"

APP_SCOPE = "_app"            # pseudo-module for phone-scoped metrics (measured once per developer+phone)
RISE_NAMES = ("RISE", "Riise", "Rise")
NRUNS = 5                     # Run columns in the workbook

RUN_COLUMNS = ["timestamp", "module", "module_version", "developer", "app", "device_model", "device_ram_gb",
               "android", "package", "version", "metric", "run", "value", "unit", "source", "artifact", "note"]
ENV_COLUMNS = ["timestamp", "module", "developer", "device_model", "device_ram_gb", "android", "refresh_rate_mode",
               "render_rate_hz", "private_dns_mode", "low_power", "show_touches", "animation_scales", "battery_pct",
               "charging", "thermal_status", "wifi_rssi_dbm", "wifi_link_mbps", "speedtest_mbps", "holdings",
               "app_versions", "notes"]

# ---------------------------------------------------------------- sheets
LOAD, SCROLL, UPD, OFF, DP, SDK, RAM, RES, INFO = (
    "1 Load & Network", "2 Scroll FPS", "3 Screen Updates", "4 Offline", "5 Data Pointers",
    "6 SDKs", "7 RAM & Storage", "8 CPU Battery Data", "9 App Info & Stability")
DATA_SHEETS = [LOAD, SCROLL, UPD, OFF, DP, SDK, RAM, RES, INFO]

# ---------------------------------------------------------------- metric catalogue
# Each metric: id, category, name (templated with {screen} {list} {detail}), unit, better,
# scope ("runs", sheet) | ("app", sheet, column) | ("score", sheet), tool, how (templated),
# runs = expected run count, applies = None | "live_ticks" | "account_sensitive",
# phone = True when the metric is phone-scoped (measured once under the _app module).


def _m(mid, cat, name, unit, better, scope, tool, how, runs=5, applies=None, phone=False):
    return {"id": mid, "category": cat, "name": name, "unit": unit, "better": better, "scope": scope,
            "tool": tool, "how": how, "runs": runs, "applies": applies, "phone": phone}


METRIC_CATALOGUE = [
    # ---- Loading time / API
    _m("L1", "Loading Time", "Cold start (OS-reported launch time)", "ms", "Lower", ("runs", LOAD), "ADB (bench.py)",
       "adb shell am force-stop <pkg>, then adb shell am start -W -n <pkg>/<activity> and read TotalTime. bench.py --group coldstart does this.", phone=True),
    _m("L2", "Loading Time", "PIN/biometric submit → home fully rendered", "ms", "Lower", ("runs", LOAD), "scrcpy",
       "Record with scrcpy --record. Count frames from the PIN-submit frame to the frame where home stops changing, then divide by the recording fps.", phone=True),
    _m("L3", "Loading Time", "{screen} → {list} fully rendered (first open, Medium account)", "ms", "Lower", ("runs", LOAD), "scrcpy",
       "Same frame-count method. 'Fully rendered' means every value in {list} is visible with no loader or shimmer."),
    _m("L4", "Loading Time", "{screen} re-open (second visit in same session)", "ms", "Lower", ("runs", LOAD), "scrcpy",
       "Leave {screen} for another tab, come back, and measure until fully rendered. Shows in-memory caching."),
    _m("L5", "Loading Time", "{detail} open", "ms", "Lower", ("runs", LOAD), "scrcpy",
       "Tap the first item in {list} and measure until {detail} is fully rendered."),
    _m("L6", "Loading Time", "Pull-to-refresh complete on {screen}", "ms", "Lower", ("runs", LOAD), "scrcpy",
       "Measure from release of the pull gesture until the refresh indicator disappears and values update."),
    _m("L7", "Loading Time", "Warm resume after 30 s in background (on {screen})", "ms", "Lower", ("runs", LOAD), "scrcpy",
       "On {screen}, press Home, wait 30 s, reopen from Recents. Measure until {screen} is interactive with fresh data. Note if it asks for the PIN again."),
    _m("L8", "Loading Time", "Resume after 5 min in background (on {screen})", "ms", "Lower", ("runs", LOAD), "scrcpy",
       "Same as L7 with a 5-minute wait. Note if it asks for the PIN again or reloads fully."),
    _m("L9", "User-wise", "{screen} load – Small account", "ms", "Lower", ("runs", LOAD), "scrcpy",
       "L3 method on the Small test account.", applies="account_sensitive"),
    _m("L10", "User-wise", "{screen} load – Large account", "ms", "Lower", ("runs", LOAD), "scrcpy",
       "L3 method on the Large test account.", applies="account_sensitive"),
    _m("L11", "API / Network", "Network connections during {screen} load", "count", "Lower", ("runs", LOAD), "PCAPdroid",
       "In PCAPdroid, filter to the app and start capture. Open {screen} cold and count the connections opened in the first 10 s."),
    _m("L12", "API / Network", "{screen} load on throttled network (~1 Mbps)", "ms", "Lower", ("runs", LOAD), "Developer options",
       "Phone: Developer options → Network download rate limit = 1 Mbps (note the value in env.csv). L3 method."),
    _m("L13", "Offline", "Recovery after reconnect → fresh data shown on {screen}", "ms", "Lower", ("runs", LOAD), "scrcpy",
       "On {screen}, turn airplane mode on for 30 s, then off. Measure from Wi-Fi reconnect (status bar icon) to updated values."),
    _m("L14", "Loading Time", "In-screen tab / sub-section switch on {screen}, tap to content", "ms", "Lower", ("runs", LOAD), "scrcpy",
       "On {screen}, tap a sibling tab or sub-section (e.g. Overview → Technicals). Frame-count from the tap to the new content fully drawn. Note which tab in the note."),
    _m("L15", "API / Network", "Data per {screen} open (received + sent, open + 8 s)", "KB", "Lower", ("runs", LOAD), "ADB netstats (bench.py)",
       "bench.py --group open: the app's UID byte counter from dumpsys netstats before the tap that opens {screen} and 8 s after it is loaded."),
    _m("L16", "Loading Time", "{detail2} open from {screen}", "ms", "Lower", ("runs", LOAD), "timing.py",
       "On {screen}, tap the entry for {detail2} and measure until it is fully drawn (timing.py --tests L16). Open and go Back only; submit nothing.",
       applies="detail2"),
    # ---- Scroll / gestures
    _m("S1", "Scroll & Gesture", "Janky frames while scrolling {list} (Medium account)", "%", "Lower", ("runs", SCROLL), "Perfetto (bench.py)",
       "bench.py --group scroll records a Perfetto FrameTimeline trace during 10 identical scripted flings on {list}. Janky = frames with a jank type other than None / Buffer Stuffing. Same for Native and Flutter apps."),
    _m("S2", "Scroll & Gesture", "Frame duration – 50th percentile", "ms", "Lower", ("runs", SCROLL), "Perfetto (bench.py)",
       "Same trace: time from the app starting a frame to that frame being on screen."),
    _m("S3", "Scroll & Gesture", "Frame duration – 90th percentile", "ms", "Lower", ("runs", SCROLL), "Perfetto (bench.py)",
       "Same trace, 90th percentile."),
    _m("S4", "Scroll & Gesture", "Frame duration – 99th percentile", "ms", "Lower", ("runs", SCROLL), "Perfetto (bench.py)",
       "Same trace, 99th percentile."),
    _m("S5", "Scroll & Gesture", "Average FPS while scrolling {list}", "fps", "Higher", ("runs", SCROLL), "Perfetto (bench.py)",
       "Same trace: 1000 ÷ average gap between frames, ignoring idle gaps over 100 ms. Capped by the display refresh rate (recorded in env.csv)."),
    _m("S6", "User-wise", "Janky frames – Large account", "%", "Lower", ("runs", SCROLL), "Perfetto (bench.py)",
       "S1 method with the Large account logged in.", applies="account_sensitive"),
    _m("S7", "Scroll & Gesture", "Gesture jank on non-list interactions of {screen} (chart range, scrub, tab swipe)", "%", "Lower", ("runs", SCROLL), "Perfetto (bench.py)",
       "bench.py --group gesture plays the module's scripted gestures for this app under a Perfetto trace and reports janky %. If the module defines no gestures for the app, record it by hand: dumpsys gfxinfo reset, perform the gestures, dumpsys gfxinfo (native apps only)."),
    # ---- Screen updates
    _m("U1", "Screen Updation", "LTP updates per minute on {screen} (same symbol, market hours)", "/min", "Higher", ("runs", UPD), "scrcpy",
       "During market hours, record 2 min on a liquid symbol present on every app. Count visible LTP changes and divide by 2.", applies="live_ticks"),
    _m("U2", "Screen Updation", "Tick lag vs reference feed", "ms", "Lower", ("runs", UPD), "Camera / scrcpy",
       "Optional. Film the app next to a reference terminal in one frame. Lag = time from the reference tick to the same price in the app.", applies="live_ticks"),
    _m("U3", "Screen Updation", "Live updates resume after 1 min in background", "ms", "Lower", ("runs", UPD), "scrcpy",
       "Background for 1 min, then return to {screen}. Measure until the first LTP tick is visible.", applies="live_ticks"),
    _m("U4", "Screen Updation", "Idle redraw rate on {screen} (frames per second, 60 s, no input)", "fps", "Lower", ("runs", UPD), "Perfetto (bench.py)",
       "bench.py --group idle: a 60 s Perfetto FrameTimeline trace on {screen} with no touch. Value = app frames ÷ 60. A high rate with few visible changes means the screen redraws on every socket message.", runs=3, applies="live_ticks"),
    _m("U5", "Screen Updation", "Wasted redraws on {screen}: idle frames identical to the previous frame", "%", "Lower", ("runs", UPD), "screenrecord + ffmpeg (bench.py)",
       "bench.py --group idle --with-video: a separate 60 s screenrecord on {screen}, then ffmpeg mpdecimate counts frames that are pixel-identical to the previous one. Value = identical ÷ total × 100.", runs=3, applies="live_ticks"),
    # ---- Offline, data pointers (computed from per-item answers)
    _m("O1", "Offline", "Offline caching score", "%", "Higher", ("score", OFF), "Manual (record.py --item)",
       "Answer every offline item in the module (Yes = 2, Partial = 1, No = 0, N/A excluded). The score is computed on tab '4 Offline'.", runs=1),
    _m("D1", "Data Pointers", "Data pointer / feature coverage", "%", "Higher", ("score", DP), "Manual (record.py --item)",
       "Answer every data item in the module (Yes = 1, Partial = 0.5, No = 0, N/A excluded). The score is computed on tab '5 Data Pointers'.", runs=1),
    # ---- SDKs
    _m("X1", "External SDKs", "Trackers detected (Exodus)", "count", "Lower", ("app", SDK, "B"), "Exodus Privacy",
       "Search the app on exodus-privacy.eu.org and use the latest report for the Play Store version.", runs=1, phone=True),
    _m("X2", "External SDKs", "Permissions requested (Exodus)", "count", "Lower", ("app", SDK, "C"), "Exodus Privacy",
       "Same Exodus report: permissions count.", runs=1, phone=True),
    _m("X3", "External SDKs", "Third-party domains contacted on {screen}", "count", "Lower", ("app", SDK, "D"), "PCAPdroid",
       "PCAPdroid capture for 60 s on {screen}. Count unique domains that don't belong to the app's own company.", runs=1),
    _m("X4", "External SDKs", "Start-up lock contention: 'Long monitor contention' events before home", "count", "Lower", ("app", SDK, "E"), "ADB logcat (bench.py)",
       "bench.py --group coldstart clears logcat, cold-starts the app and counts 'Long monitor contention' lines from the app's process until home is up. The longest wait in ms goes in the note.", runs=5, phone=True),
    # ---- RAM & storage
    _m("R1", "RAM", "RAM (Total PSS) after cold start", "MB", "Lower", ("runs", RAM), "ADB meminfo (bench.py)",
       "adb shell dumpsys meminfo <pkg>, TOTAL PSS (KB) ÷ 1024, taken 5 s after the home screen renders. The note carries the Java/native/code/graphics split.", phone=True),
    _m("R2", "RAM", "RAM (Total PSS) on {screen}", "MB", "Lower", ("runs", RAM), "ADB meminfo (bench.py)",
       "Same command 5 s after {screen} is fully rendered."),
    _m("R3", "RAM", "RAM (Total PSS) after 5 min on {screen}", "MB", "Lower", ("runs", RAM), "ADB meminfo (bench.py --group ram --with-r3)",
       "Same command after 5 min on {screen} with live ticks and a scroll every minute. A big rise from R2 suggests a leak. One soak per app.", runs=1),
    _m("R4", "Storage", "App size (installed)", "MB", "Lower", ("runs", RAM), "Settings / ADB diskstats",
       "Settings → Apps → <app> → Storage → App size (or adb shell dumpsys diskstats). One reading.", runs=1, phone=True),
    _m("R5", "Storage", "User data – fresh install (before login)", "MB", "Lower", ("runs", RAM), "Settings",
       "Storage → User data right after install and first open, before login. One reading.", runs=1, phone=True),
    _m("R6", "Storage", "User data – after login + first screen open", "MB", "Lower", ("runs", RAM), "Settings",
       "Storage → User data after login and opening the app's main screen once. One reading.", runs=1, phone=True),
    _m("R7", "Storage", "Cache – after login + first screen open", "MB", "Lower", ("runs", RAM), "Settings",
       "Storage → Cache at the same point as R6. One reading.", runs=1, phone=True),
    _m("R8", "Storage", "Total storage after 1 day of use", "MB", "Lower", ("runs", RAM), "Settings",
       "Storage → Total after a day of normal use. One reading.", runs=1, phone=True),
    _m("R9", "RAM", "Leak check: PSS growth over 10 open/close cycles of {screen}", "MB", "Lower", ("runs", RAM), "ADB meminfo (bench.py)",
       "bench.py --group leak: PSS on the screen before {screen}, then open and close {screen} ten times (scripted when the module has open_tap, otherwise by hand), 2 s settle, PSS again. Value = growth in MB.", runs=1),
    # ---- CPU / battery / data
    _m("C1", "CPU / Battery / Data", "Average CPU on {screen} (live ticks, 15 min equivalent)", "%", "Lower", ("runs", RES), "ADB (bench.py --group live)",
       "CPU time used by the app's processes (/proc/<pid>/stat) ÷ session length. 100% = one full core.", runs=3, applies="live_ticks"),
    _m("C2", "CPU / Battery / Data", "Battery drain – 15 min on {screen}", "mAh", "Lower", ("runs", RES), "ADB (bench.py --group live)",
       "Resets batterystats, simulates unplugged, then reads the app's estimated power use (mAh), scaled to 15 min.", runs=3, applies="live_ticks"),
    _m("C3", "CPU / Battery / Data", "Device temperature rise – session on {screen}", "°C", "Lower", ("runs", RES), "ADB (bench.py --group live)",
       "SKIN temperature from dumpsys thermalservice at start and end. Not scaled. Use wireless debugging if possible, because USB charging heats the phone.", runs=3, applies="live_ticks"),
    _m("C4", "CPU / Battery / Data", "Data used – 15 min on {screen}", "MB", "Lower", ("runs", RES), "ADB (bench.py --group live)",
       "The app's received + sent bytes from dumpsys netstats (forced poll) at start and end, scaled to 15 min.", runs=3, applies="live_ticks"),
    # ---- App info / stability
    _m("A1", "Stability", "Crashes during all testing", "count", "Lower", ("app", INFO, "J"), "ADB logcat",
       "adb logcat -b crash kept running during every session. Count FATAL EXCEPTION entries for the package.", runs=1),
    _m("A2", "Stability", "ANRs during all testing", "count", "Lower", ("app", INFO, "K"), "ADB logcat",
       "Count 'ANR in <pkg>' entries in adb logcat over all sessions.", runs=1),
    _m("A3", "Stability", "Play Store rating", "★", "Higher", ("app", INFO, "F"), "Play Store",
       "Rating shown on the Play Store listing on the test date.", runs=1, phone=True),
    _m("A4", "Stability", "Play Store download size", "MB", "Lower", ("app", INFO, "H"), "Play Store",
       "Size shown on the Play Store install button or in 'About this app' on the test device.", runs=1, phone=True),
]
METRICS = {m["id"]: m for m in METRIC_CATALOGUE}
CATEGORIES = []
for _mm in METRIC_CATALOGUE:
    if _mm["category"] not in CATEGORIES:
        CATEGORIES.append(_mm["category"])
PHONE_METRICS = [m["id"] for m in METRIC_CATALOGUE if m["phone"]]
BENCH_GROUPS = {  # which bench.py group produces which metric IDs
    "coldstart": ["L1", "X4"], "ram": ["R1", "R2"], "open": ["L15"], "scroll": ["S1", "S2", "S3", "S4", "S5"],
    "gesture": ["S7"], "idle": ["U4", "U5"], "leak": ["R9"], "live": ["C1", "C2", "C3", "C4"],
}
AUTOMATED = sorted({mid for ids in BENCH_GROUPS.values() for mid in ids} | {"R3"})

# Yes/No facts for the user-feel scorecard (record.py --fact), recorded once per app and module as F.<key>.
UX_FACTS = {
    "pin_on_resume": "Asks for the PIN again after 30 s in the background on {screen}",
    "pull_to_refresh": "{screen} has pull-to-refresh",
}

GENERIC_WORDS = {"screen": "the screen", "list": "the list", "detail": "the detail screen", "detail2": "a second detail screen"}


def render(text, module=None):
    """Fill {screen} {list} {detail} from a module definition (generic words for _app or None)."""
    words = dict(GENERIC_WORDS)
    if module and module.get("rise"):
        for k in ("screen", "list", "detail", "detail2"):
            if module["rise"].get(k):
                words[k] = module["rise"][k]
    return text.format(**words)


def metric_applies(metric, module):
    """Whether a metric is measured for this module, and why not if it isn't."""
    m = METRICS[metric] if isinstance(metric, str) else metric
    if module["name"] == APP_SCOPE:
        return (True, "") if m["phone"] else (False, "module-scoped metric")
    if m["phone"]:
        return False, "phone-scoped: measured once under _app"
    if m["id"] in module.get("skip", []):
        return False, "skipped by module"
    flag = m["applies"]
    if flag and not module.get("rise", {}).get(flag, False):
        return False, f"{flag} is false for this module"
    return True, ""


def module_metrics(module):
    return [m for m in METRIC_CATALOGUE if metric_applies(m, module)[0]]


# ---------------------------------------------------------------- apps

def load_apps():
    if not APPS_FILE.exists():
        raise SystemExit(f"{APPS_FILE} is missing.")
    apps = json.loads(APPS_FILE.read_text())
    out = {}
    for name, v in apps.items():
        if isinstance(v, str):  # old flat shape
            v = {"package": v, "ranked": True}
        v.setdefault("ranked", True)
        out[name] = v
    return out


def is_rise(name):
    return name in RISE_NAMES


def canonical_app(name):
    return "RISE" if name in RISE_NAMES else name


def resolve_app(name):
    """Registry name for a user-typed app name (case-insensitive, RISE aliases). SystemExit if unknown."""
    apps = load_apps()
    if name in apps:
        return name
    if name in RISE_NAMES:
        return "RISE"
    for n in apps:
        if n.lower() == str(name).lower():
            return n
    raise SystemExit(f"Unknown app '{name}'. Registry: {', '.join(apps)}")


def is_unranked_rise(name):
    """RISE UAT and similar: unranked builds of RISE that use RISE's screens."""
    v = load_apps().get(name)
    return bool(v) and not v.get("ranked", True) and str(name).upper().startswith("RISE")


def app_order(names):
    """RISE first, ranked apps in registry order, unranked (RISE UAT) last."""
    reg = list(load_apps().keys())
    present = set(canonical_app(n) for n in names)

    def key(n):
        ranked = load_apps().get(n, {}).get("ranked", True)
        return (0 if is_rise(n) else (1 if ranked else 2), reg.index(n) if n in reg else 99)
    return sorted(present, key=key)


# ---------------------------------------------------------------- modules

VERSIONED_KEYS = ("rise", "apps", "scroll", "gestures", "open_tap", "offline_items", "data_items")

DEFAULT_SCROLL = {"x_frac": 0.5, "y_from_frac": 0.75, "y_to_frac": 0.30, "per_app": {}}


def module_path(name):
    return MODULES_DIR / f"{name}.json"


def list_modules():
    return sorted(p.stem for p in MODULES_DIR.glob("*.json"))


def module_version(module):
    payload = {k: module.get(k) for k in VERSIONED_KEYS}
    if module.get("runs"):  # per-module run counts (a protocol deviation the lead signs off); absent = catalogue counts
        payload["runs"] = module["runs"]
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha1(blob.encode("utf-8")).hexdigest()[:8]


def load_module(name):
    p = module_path(name)
    if not p.exists():
        raise SystemExit(f"No module definition at {p}. Create it with /benchmark-module {name}.")
    m = json.loads(p.read_text())
    m.setdefault("name", name)
    m.setdefault("skip", [])
    m.setdefault("apps", {})
    m.setdefault("offline_items", [])
    m.setdefault("data_items", [])
    m.setdefault("gestures", {"per_app": {}})
    m.setdefault("open_tap", {"per_app": {}})
    if name != APP_SCOPE:
        m.setdefault("rise", {})
        for k, v in (("screen", name), ("list", "the list"), ("detail", "the detail screen"),
                     ("live_ticks", False), ("account_sensitive", False)):
            m["rise"].setdefault(k, v)
        scroll = dict(DEFAULT_SCROLL)
        scroll.update(m.get("scroll") or {})
        scroll.setdefault("per_app", {})
        m["scroll"] = scroll
    m["version"] = module_version(m)
    return m


def save_module(module):
    m = {k: v for k, v in module.items() if k != "version"}
    MODULES_DIR.mkdir(exist_ok=True)
    module_path(m["name"]).write_text(json.dumps(m, indent=2, ensure_ascii=False) + "\n")
    return module_version(m)


def app_screen(module, app):
    """Screen name for an app in this module; None means N/A."""
    if is_rise(app) or is_unranked_rise(app):
        return module.get("rise", {}).get("screen")
    entry = module.get("apps", {}).get(app)
    if entry is None:
        return None
    return entry.get("screen")


def scroll_fracs(module, app):
    s = dict(module.get("scroll") or DEFAULT_SCROLL)
    s.update((module.get("scroll") or {}).get("per_app", {}).get(app, {}))
    return s["x_frac"], s["y_from_frac"], s["y_to_frac"]


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:48]


# ---------------------------------------------------------------- developer identity

def read_me():
    if ME_FILE.exists():
        try:
            return json.loads(ME_FILE.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def write_me(developer):
    ME_FILE.parent.mkdir(parents=True, exist_ok=True)
    ME_FILE.write_text(json.dumps({"developer": developer}, indent=2) + "\n")


def get_developer(cli_value=None):
    dev = cli_value or read_me().get("developer") or os.environ.get("RIISE_BENCH_DEVELOPER")
    if not dev:
        raise SystemExit("No developer name. Pass --developer <name> once, or run: python3 record.py --me <name>")
    return safe_developer(dev)


def safe_name(text):
    return re.sub(r"[^A-Za-z0-9._-]+", "-", str(text).strip()).strip("-") or "unknown"


def safe_developer(text):
    """Developer names must not contain '_', which separates developer from device in folder names."""
    return safe_name(text).replace("_", "-")


# ---------------------------------------------------------------- results

def results_dir(module_name, developer, device_model, base=None):
    d = Path(base) if base else RESULTS_DIR
    return d / module_name / f"{safe_developer(developer)}_{safe_name(device_model)}"


def now_iso():
    return datetime.datetime.now().isoformat(timespec="seconds")


def append_rows(folder, rows, meta, module):
    """Append metric rows to runs.csv and mark them in state.json.

    rows: [{"metric", "run", "value", "note", "source"?, "artifact"?, "ts"?}]
    meta: {"app", "pkg", "version", "model", "android", "ram_gb"}
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "runs.csv"
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(RUN_COLUMNS)
        for r in rows:
            mid = r["metric"].split(".", 1)[0]
            unit = METRICS[mid]["unit"] if mid in METRICS else ""
            w.writerow([r.get("ts") or now_iso(), module["name"], module.get("version", module_version(module)),
                        meta.get("developer", ""), canonical_app(meta["app"]), meta.get("model", ""),
                        meta.get("ram_gb", ""), meta.get("android", ""), meta.get("pkg", ""), meta.get("version", ""),
                        r["metric"], r["run"], "" if r["value"] is None else r["value"], unit,
                        r.get("source", "bench.py"), r.get("artifact", ""), r.get("note", "")])
    update_state(folder, canonical_app(meta["app"]), rows)
    return path


def read_runs(path):
    path = Path(path)
    if not path.exists():
        return []
    with path.open(newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["app"] = canonical_app(r.get("app", ""))
        v = r.get("value", "")
        try:
            r["num"] = float(v) if v not in ("", None, "None") else None
        except ValueError:
            r["num"] = None
    return rows


def all_runs(base=None):
    """Every runs.csv under results/, skipping sync-conflict copies. Returns [(module, folder, rows)]."""
    base = Path(base) if base else RESULTS_DIR
    out = []
    for p in sorted(base.glob("*/*/runs.csv")):
        if any(bad in part.lower() for part in p.parts for bad in ("conflict", " copy", "(copy")):
            continue
        out.append((p.parent.parent.name, p.parent, read_runs(p)))
    return out


def state_path(folder):
    return Path(folder) / "state.json"


def read_state(folder):
    p = state_path(folder)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            pass
    return {"apps": {}, "updated": None}


def update_state(folder, app, rows):
    st = read_state(folder)
    a = st["apps"].setdefault(app, {})
    for r in rows:
        if r["value"] is None:
            continue
        done = a.setdefault(r["metric"], [])
        if r["run"] not in done:
            done.append(r["run"])
            done.sort()
    st["updated"] = now_iso()
    state_path(folder).write_text(json.dumps(st, indent=2) + "\n")
    return st


def forget_runs(folder, app, metrics, run):
    """Drop run number `run` of the given metrics from state.json so bench.py measures it again (--redo)."""
    st = read_state(folder)
    a = st["apps"].get(canonical_app(app), {})
    changed = []
    for m in metrics:
        if run in a.get(m, []):
            a[m].remove(run)
            changed.append(m)
    if changed:
        st["updated"] = now_iso()
        state_path(folder).write_text(json.dumps(st, indent=2) + "\n")
    return changed


def runs_done(folder, app, metric):
    return read_state(folder)["apps"].get(canonical_app(app), {}).get(metric, [])


def next_run(folder, app, metric):
    done = runs_done(folder, app, metric)
    n = 1
    while n in done:
        n += 1
    return n


def append_env(folder, values):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "env.csv"
    new = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(ENV_COLUMNS)
        w.writerow([values.get(c, "") for c in ENV_COLUMNS])
    return path


def read_env(folder):
    path = Path(folder) / "env.csv"
    if not path.exists():
        return []
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------- weights

DEFAULT_WEIGHTS = {"Loading Time": 20, "User-wise": 5, "API / Network": 5, "Offline": 5, "Scroll & Gesture": 15,
                   "Screen Updation": 15, "Data Pointers": 10, "External SDKs": 4, "RAM": 7, "Storage": 3,
                   "CPU / Battery / Data": 7, "Stability": 4}


def load_weights():
    w = dict(DEFAULT_WEIGHTS)
    if WEIGHTS_FILE.exists():
        data = json.loads(WEIGHTS_FILE.read_text())
        w.update({k: v for k, v in data.items() if not k.startswith("_")})
    missing = set(CATEGORIES) - set(w)
    if missing:
        raise SystemExit(f"weights.json lacks categories: {sorted(missing)}")
    return w


# ---------------------------------------------------------------- expected runs / completeness

def expected(module, app=None):
    """{metric_id: expected_runs} for a module (item metrics O1/D1 expand to their items)."""
    out = {}
    for m in module_metrics(module):
        if m["id"] == "O1":
            for it in module.get("offline_items", []):
                out[f"O1.{slug(it)}"] = 1
        elif m["id"] == "D1":
            for it in module.get("data_items", []):
                out[f"D1.{slug(it)}"] = 1
        else:
            out[m["id"]] = module.get("runs", {}).get(m["id"], m["runs"])
    if module["name"] != APP_SCOPE:
        for k in UX_FACTS:
            out[f"F.{k}"] = 1
    return out


def missing(module, folder, app):
    exp = expected(module, app)
    st = read_state(folder)["apps"].get(canonical_app(app), {})
    gaps = {}
    for mid, n in exp.items():
        done = len(st.get(mid, []))
        if done < n:
            gaps[mid] = (done, n)
    return gaps

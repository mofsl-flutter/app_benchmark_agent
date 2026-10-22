#!/usr/bin/env python3
"""RISE benchmark – ADB collector, one module at a time.

Collects, per run, on a Play Store (release) build, for the module given with --module:
  coldstart  L1 cold start (am start -S -W, TotalTime) and X4 start-up lock contention (logcat)
  ram        R1 RAM after home (5 s), R2 RAM on the module screen (5 s), with the meminfo split in the note
  open       L15 data per screen open (netstats UID delta, open + 8 s)
  scroll     S1–S5 Perfetto FrameTimeline over 10 scripted flings on the module's list
  gesture    S7 jank over the module's scripted gestures for this app (chart ranges, scrub, tab swipes)
  idle       U4 idle redraw rate (60 s Perfetto, no input) and, with --with-video, U5 wasted redraws
             (60 s screenrecord + ffmpeg mpdecimate)
  leak       R9 PSS growth over 10 open/close cycles of the module screen
  live       C1–C4 live session (market hours): CPU %, battery mAh, temperature rise, data MB
  --with-r3  R3 RAM after 5 min on the screen

Module `_app` holds the phone-scoped metrics (L1, X4, R1 …) measured once per developer and phone.

Rows go to results/<module>/<developer>_<device-model>/runs.csv and state.json; rerunning the same
command resumes at the first run number that is still missing. Traces and recordings stay on this
Mac under ~/.riise-benchmark/artifacts/ and are named in the artifact column.

Usage:
  python3 bench.py devices
  python3 bench.py find Groww groww --save                 # look up and remember a package name
  python3 bench.py info Groww [--framework]                # version, launcher, Native/Flutter/RN
  python3 bench.py run RISE --module _app                  # L1, X4, R1 once per phone
  python3 bench.py run Groww --module fno                  # default groups: ram,open,scroll
  python3 bench.py run Groww --module fno --group idle --with-video --runs 3
  python3 bench.py run Groww --module fno --group live --runs 3 --live-minutes 10
  python3 bench.py status --module fno                     # what is still missing per app

Use -s <serial> before the command when more than one phone is connected.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import benchlib as B

HERE = Path(__file__).resolve().parent
ARTIFACTS = B.ME_FILE.parent / "artifacts"

FLINGS = 10
SOAK_SECONDS = 300
LIVE_SECONDS = 900
IDLE_SECONDS = 60
LEAK_CYCLES = 10
OPEN_SETTLE = 8
GROUPS = ["coldstart", "ram", "open", "scroll", "gesture", "idle", "leak", "live"]
DEFAULT_GROUPS = {"module": "ram,open,scroll", B.APP_SCOPE: "coldstart,ram"}
REMOTE_TRACE = "/data/misc/perfetto-traces/bench.pftrace"
REMOTE_VIDEO = "/sdcard/bench_idle.mp4"
PERFETTO_CFG = """
buffers { size_kb: 32768 fill_policy: RING_BUFFER }
data_sources { config { name: "android.surfaceflinger.frametimeline" } }
data_sources { config { name: "linux.process_stats" process_stats_config { scan_all_processes_on_start: true } } }
duration_ms: %d
"""


class Abort(Exception):
    pass


# ---------------------------------------------------------------- adb

def find_adb():
    for cand in (os.environ.get("ADB"), shutil.which("adb"),
                 os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
                 os.path.expanduser("~/Android/Sdk/platform-tools/adb")):
        if cand and os.path.exists(cand):
            return cand
    sys.exit("adb not found. Install it (brew install android-platform-tools) or set ADB=/path/to/adb.")


class Adb:
    def __init__(self, serial=None):
        self.base = [find_adb()] + (["-s", serial] if serial else [])

    def run(self, *args, timeout=120, check=True):
        p = subprocess.run(self.base + list(args), capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
        if check and p.returncode != 0:
            raise RuntimeError(f"adb {' '.join(args)} failed: {(p.stderr or p.stdout).strip()}")
        return p.stdout

    def sh(self, cmd, **kw):
        return self.run("shell", cmd, **kw)

    def start_perfetto(self, duration_ms):
        p = subprocess.Popen(self.base + ["shell", f"perfetto --txt -c - -o {REMOTE_TRACE}"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        p.stdin.write(PERFETTO_CFG % duration_ms)
        p.stdin.close()
        return p

    def ensure_device(self):
        p = subprocess.run(self.base + ["get-state"], capture_output=True, text=True)
        if p.returncode != 0 or p.stdout.strip() != "device":
            msg = (p.stderr or p.stdout).strip()
            if "more than one" in msg:
                sys.exit("More than one device connected. Pass -s <serial> (see: python3 bench.py devices).")
            sys.exit(f"No device ready: {msg or 'not connected'}. Check USB debugging and run: adb devices")


# ---------------------------------------------------------------- parsers (pure, tested in tests/)

def parse_total_time(out):
    m = re.search(r"TotalTime:\s*(\d+)", out)
    return int(m.group(1)) if m else None


def parse_meminfo(out):
    """Total PSS plus the App Summary split, in MB, and the WebView count, from dumpsys meminfo <pkg>."""
    def kb(label):
        m = re.search(rf"^\s*{label}:\s+(\d+)", out, re.M)
        return round(int(m.group(1)) / 1024, 1) if m else None
    total = re.search(r"TOTAL PSS:\s+(\d+)", out) or re.search(r"^\s*TOTAL\s+(\d+)", out, re.M)
    wv = re.search(r"WebViews:\s+(\d+)", out)
    return {
        "pss_mb": round(int(total.group(1)) / 1024, 1) if total else None,
        "java_mb": kb("Java Heap"), "native_mb": kb("Native Heap"), "code_mb": kb("Code"),
        "graphics_mb": kb("Graphics"), "webviews": int(wv.group(1)) if wv else None,
    }


def parse_pss_mb(out):
    return parse_meminfo(out)["pss_mb"]


def meminfo_note(d):
    parts = [f"{k}={d[v]}" for k, v in (("java", "java_mb"), ("native", "native_mb"), ("code", "code_mb"),
                                         ("gfx", "graphics_mb"), ("webviews", "webviews")) if d.get(v) is not None]
    return ";".join(parts)


def parse_contention(log):
    """(count, longest ms) of 'Long monitor contention' lines in a logcat dump."""
    lines = [l for l in log.splitlines() if "Long monitor contention" in l]
    longest = 0
    for l in lines:
        m = re.search(r"for (\d+)ms", l)
        if m:
            longest = max(longest, int(m.group(1)))
    return len(lines), longest


def parse_frame_count(ffmpeg_out):
    """Frames written, from the last 'frame=  N' progress line of an ffmpeg run."""
    hits = re.findall(r"frame=\s*(\d+)", ffmpeg_out)
    return int(hits[-1]) if hits else None


def parse_nb_frames(ffprobe_out):
    m = re.search(r"(\d+)", ffprobe_out or "")
    return int(m.group(1)) if m else None


def identical_pct(total, kept):
    """Share of frames mpdecimate dropped as identical to the previous one."""
    if not total or kept is None:
        return None
    return round(100 * (total - kept) / total, 1)


def parse_black_seconds(ffmpeg_out):
    """Total seconds ffmpeg's blackdetect reported as black."""
    return round(sum(float(x) for x in re.findall(r"black_duration:([\d.]+)", ffmpeg_out or "")), 2)


GESTURE_RE = {
    "tap": re.compile(r"^input tap (0(?:\.\d+)?|1(?:\.0+)?) (0(?:\.\d+)?|1(?:\.0+)?)$"),
    "swipe": re.compile(r"^input swipe (0(?:\.\d+)?|1(?:\.0+)?) (0(?:\.\d+)?|1(?:\.0+)?) (0(?:\.\d+)?|1(?:\.0+)?) (0(?:\.\d+)?|1(?:\.0+)?)(?: (\d{2,4}))?$"),
    "back": re.compile(r"^input keyevent KEYCODE_BACK$"),
}


def render_gesture(cmd, w, h):
    """Turn a module gesture into an adb shell command. Only taps and swipes given as screen FRACTIONS (0..1)
    and KEYCODE_BACK are allowed, so a gesture written on one phone lands on the same spot on another and
    nothing else can run on a phone logged into a client account."""
    cmd = " ".join(str(cmd).split())
    m = GESTURE_RE["tap"].match(cmd)
    if m:
        return f"input tap {int(float(m.group(1)) * w)} {int(float(m.group(2)) * h)}"
    m = GESTURE_RE["swipe"].match(cmd)
    if m:
        x1, y1, x2, y2 = (int(float(m.group(i)) * (w if i % 2 else h)) for i in (1, 2, 3, 4))
        ms = m.group(5) or "120"
        return f"input swipe {x1} {y1} {x2} {y2} {ms}"
    if GESTURE_RE["back"].match(cmd):
        return cmd
    raise ValueError(f"gesture not allowed: '{cmd}'. Use 'input tap X Y', 'input swipe X1 Y1 X2 Y2 [ms]' with fractions 0..1, "
                     "or 'input keyevent KEYCODE_BACK'.")


def parse_screen_size(out):
    sizes = re.findall(r"size:\s*(\d+)x(\d+)", out)  # Override size (if any) comes after Physical size
    w, h = sizes[-1]
    return int(w), int(h)


def parse_launcher(out):
    lines = [l.strip() for l in out.splitlines() if "/" in l]
    return lines[-1] if lines else None


def parse_app_id(out):
    m = re.search(r"appId=(\d+)", out) or re.search(r"userId=(\d+)", out)
    return int(m.group(1)) if m else None


def parse_proc_ticks(stat_line):
    rest = stat_line.rsplit(")", 1)[1].split()
    return int(rest[11]) + int(rest[12])


def parse_netstats_bytes(out, uid):
    """rx + tx bytes for one UID (all sets, tag 0x0) from the 'UID stats' section of netstats detail."""
    total, in_uid_section, current = 0, False, False
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("UID stats:"):
            in_uid_section = True
        elif s.endswith("stats:"):
            in_uid_section = False
        elif in_uid_section and s.startswith("ident="):
            current = f" uid={uid} " in line and "tag=0x0" in line
        elif in_uid_section and current and s.startswith("st="):
            m = re.search(r"rb=(\d+).*?tb=(\d+)", s)
            if m:
                total += int(m.group(1)) + int(m.group(2))
    return total


def parse_uid_mah(out, app_id):
    m = re.search(rf"UID u0a{app_id - 10000}:\s*([\d.]+)", out)
    return float(m.group(1)) if m else None


def parse_temp_c(out):
    for name in ("SKIN", "BAT"):
        m = re.search(rf"Temperature\{{mValue=([\d.]+), mType=\d+, mName={name},", out)
        if m:
            return float(m.group(1))
    return None


def frame_stats(frames):
    """frames: [(ts_ns, dur_ns, jank_type)] for one app layer -> jank %, duration percentiles, FPS."""
    if not frames:
        return None
    frames = sorted(frames)
    durs = sorted(d / 1e6 for _, d, _ in frames)
    janky = sum(1 for _, _, j in frames if (j or "None") not in ("None", "Buffer Stuffing"))
    gaps = [(b[0] - a[0]) / 1e6 for a, b in zip(frames, frames[1:])]
    active = [g for g in gaps if g < 100]  # ignore idle gaps between flings
    pct = lambda p: durs[min(len(durs) - 1, int(round(p / 100 * (len(durs) - 1))))]
    return {
        "frames": len(frames),
        "jank_pct": round(100 * janky / len(frames), 2),
        "p50": round(pct(50), 1), "p90": round(pct(90), 1), "p99": round(pct(99), 1),
        "fps": round(1000 / statistics.mean(active), 1) if active else None,
    }


def idle_rate(frames, seconds):
    """Frames presented per second over an idle window (raw count, no gap filtering)."""
    return round(len(frames) / seconds, 1)


def detect_framework(names):
    names = set(n.rsplit("/", 1)[-1] for n in names)
    if "libflutter.so" in names:
        return "Flutter"
    if names & {"libreactnativejni.so", "libhermes.so", "libreactnative.so", "index.android.bundle"}:
        return "React Native"
    return "Native (Kotlin/Java)"


# ---------------------------------------------------------------- device actions

def launcher_component(adb, pkg):
    comp = parse_launcher(adb.sh(f"cmd package resolve-activity --brief -c android.intent.category.LAUNCHER {pkg}"))
    if not comp:
        sys.exit(f"Could not find the launcher activity for {pkg}. Is the app installed?")
    return comp


def ensure_screen_ready(adb):
    m = re.search(r"mWakefulness=(\w+)", adb.sh("dumpsys power"))
    focus = re.search(r"mCurrentFocus=(.*)", adb.sh("dumpsys window"))
    focus = focus.group(1) if focus else ""
    if (m and m.group(1) != "Awake") or any(k in focus for k in ("NotificationShade", "Keyguard", "Bouncer")):
        sys.exit("The phone is locked or its screen is off. Unlock it, set Developer options → Stay awake, and rerun.")


def cold_start_ms(adb, comp):
    return parse_total_time(adb.sh(f"am start -S -W -n {comp}"))


def meminfo(adb, pkg):
    return parse_meminfo(adb.sh(f"dumpsys meminfo {pkg}"))


def pss_mb(adb, pkg):
    return meminfo(adb, pkg)["pss_mb"]


def app_pid(adb, pkg):
    out = adb.sh(f"pidof -s {pkg}", check=False).strip()
    return int(out) if out.isdigit() else None


def contention(adb, pkg):
    pid = app_pid(adb, pkg)
    log = adb.sh(f"logcat -d --pid={pid}" if pid else "logcat -d", timeout=60, check=False)
    count, longest = parse_contention(log)
    return count, longest, ("" if pid else "logcat not filtered to the app (pid unknown)")


def fling(adb, w, h, fracs, down=True):
    xf, y_from, y_to = fracs
    x, top, bottom = int(w * xf), int(h * min(y_from, y_to)), int(h * max(y_from, y_to))
    y1, y2 = (bottom, top) if down else (top, bottom)
    adb.sh(f"input swipe {x} {y1} {x} {y2} 120")


def trace_frames(adb, pkg, duration_s, action, keep_as=None):
    """Run `action()` under a Perfetto FrameTimeline trace; return {layer: [(ts, dur, jank)]} for the app."""
    from perfetto.trace_processor import TraceProcessor

    proc = adb.start_perfetto(int(duration_s * 1000))
    time.sleep(2)
    action()
    proc.wait(timeout=duration_s + 120)
    with tempfile.TemporaryDirectory() as tmp:
        local = os.path.join(tmp, "trace.pftrace")
        adb.run("pull", REMOTE_TRACE, local)
        adb.sh(f"rm -f {REMOTE_TRACE}", check=False)
        if keep_as:
            keep_as.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(local, keep_as)
        tp = TraceProcessor(trace=local)
        try:
            rows = list(tp.query(
                "select a.ts, a.dur, a.jank_type, a.layer_name from actual_frame_timeline_slice a "
                f"join process p using(upid) where p.name = '{pkg}' or p.name like '{pkg}:%'"))
        finally:
            tp.close()
    by_layer = {}
    for r in rows:
        by_layer.setdefault(r.layer_name, []).append((r.ts, r.dur, r.jank_type))
    return by_layer


def main_layer(by_layer):
    if not by_layer:
        return None, []
    return max(by_layer.items(), key=lambda kv: len(kv[1]))


def scroll_test(adb, pkg, w, h, fracs, keep_as=None):
    def action():
        for i in range(FLINGS):
            fling(adb, w, h, fracs, down=i < FLINGS // 2)
            time.sleep(0.8)
    layer, frames = main_layer(trace_frames(adb, pkg, FLINGS + 6, action, keep_as))
    if not frames:
        return None
    stats = frame_stats(frames)
    stats["layer"] = layer
    return stats


def gesture_test(adb, pkg, gestures, w, h, keep_as=None):
    cmds = [render_gesture(g["cmd"], w, h) for g in gestures]
    swipe_ms = sum(int(c.split()[-1]) for c in cmds if c.startswith("input swipe")) / 1000
    def action():
        for c in cmds:
            adb.sh(c, check=False)
            time.sleep(1.5)
    layer, frames = main_layer(trace_frames(adb, pkg, len(gestures) * 2 + 6 + swipe_ms, action, keep_as))
    if not frames:
        return None
    stats = frame_stats(frames)
    stats["layer"] = layer
    stats["labels"] = ", ".join(g.get("label", "?") for g in gestures)
    return stats


def idle_test(adb, pkg, keep_as=None):
    by_layer = trace_frames(adb, pkg, IDLE_SECONDS + 2, lambda: time.sleep(IDLE_SECONDS), keep_as)
    layer, frames = main_layer(by_layer)
    if not frames:
        return None
    return {"fps": idle_rate(frames, IDLE_SECONDS + 2), "frames": len(frames), "layer": layer,
            "jank_pct": frame_stats(frames)["jank_pct"]}


def video_idle_test(adb, keep_as):
    """U5: screenrecord IDLE_SECONDS, then count frames mpdecimate drops as identical. Returns (pct, note)."""
    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ffmpeg:
        return None, "ffmpeg not installed (brew install ffmpeg)"
    adb.sh(f"screenrecord --time-limit {IDLE_SECONDS} {REMOTE_VIDEO}", timeout=IDLE_SECONDS + 60)
    keep_as.parent.mkdir(parents=True, exist_ok=True)
    try:
        adb.run("pull", REMOTE_VIDEO, str(keep_as), timeout=300)
    finally:
        adb.sh(f"rm -f {REMOTE_VIDEO}", check=False)  # never leave a client-account recording on the phone
    p = subprocess.run([ffmpeg, "-v", "info", "-i", str(keep_as), "-vf", "blackdetect=d=0.5:pic_th=0.98", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    if parse_black_seconds(p.stderr) >= 0.9 * IDLE_SECONDS:
        return None, "recording is black (FLAG_SECURE screen blocks capture); U5 not measurable on this app"
    total = None
    if ffprobe:
        p = subprocess.run([ffprobe, "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
                            "stream=nb_read_frames", "-of", "csv=p=0", str(keep_as)], capture_output=True, text=True)
        total = parse_nb_frames(p.stdout)
    if total is None:
        p = subprocess.run([ffmpeg, "-v", "info", "-i", str(keep_as), "-an", "-f", "null", "-"], capture_output=True, text=True)
        total = parse_frame_count(p.stderr)
    p = subprocess.run([ffmpeg, "-v", "info", "-i", str(keep_as), "-vf", "mpdecimate", "-an", "-f", "null", "-"],
                       capture_output=True, text=True)
    kept = parse_frame_count(p.stderr)
    pct = identical_pct(total, kept)
    return pct, f"{total} frames, {kept} kept by mpdecimate"


def app_pids(adb, pkg):
    pids = []
    for line in adb.sh("ps -A -o PID,NAME").splitlines()[1:]:
        parts = line.split()
        if len(parts) == 2 and (parts[1] == pkg or parts[1].startswith(pkg + ":")):
            pids.append(int(parts[0]))
    return pids


def cpu_ticks(adb, pids):
    out = adb.sh("cat " + " ".join(f"/proc/{p}/stat" for p in pids) + " 2>/dev/null", check=False)
    ticks = {}
    for line in out.splitlines():
        if ")" in line:
            ticks[int(line.split()[0])] = parse_proc_ticks(line)
    return ticks


def uid_bytes(adb, app_id):
    adb.sh("dumpsys netstats --poll", check=False)
    return parse_netstats_bytes(adb.sh("dumpsys netstats detail", timeout=180), app_id)


def live_session(adb, pkg, app_id, run, rec, screen, minutes=LIVE_SECONDS // 60):
    """C1–C4 over `minutes` on the module screen. Simulates unplugged so batterystats accrues.
    C2 and C4 are scaled to a 15-min equivalent so sessions of different length stay comparable."""
    if "USB powered: true" in adb.sh("dumpsys battery"):
        print("    ! Phone is charging over USB: C3 (temperature) will read high. Wireless debugging avoids this.")
    stay_on = adb.sh("settings get global stay_on_while_plugged_in").strip() or "0"
    clk = int(adb.sh("getconf CLK_TCK").strip() or 100)
    adb.sh("svc power stayon true")
    adb.sh("dumpsys battery unplug")
    try:
        adb.sh("dumpsys batterystats --reset")
        net0 = uid_bytes(adb, app_id)
        temp0 = parse_temp_c(adb.sh("dumpsys thermalservice"))
        pids = app_pids(adb, pkg)
        ticks0, t0 = cpu_ticks(adb, pids), time.time()
        mins = minutes
        scale = (LIVE_SECONDS / 60) / mins
        snote = f"scaled ×{scale:.2f} from {mins} min" if mins != LIVE_SECONDS // 60 else ""
        print(f"    Live session: {mins} min on {screen}. Don't touch the phone.")
        for k in range(mins):
            time.sleep(60)
            print(f"      {k + 1}/{mins} min", end="\r", flush=True)
        print()
        ticks1, elapsed = cpu_ticks(adb, pids), time.time() - t0
        common = ticks0.keys() & ticks1.keys()
        note = "" if common == set(ticks0) else "app process restarted during session"
        cpu = sum(ticks1[p] - ticks0[p] for p in common) / (clk * elapsed) * 100 if common else None
        rec("C1", run, round(cpu, 1) if cpu is not None else None, note)
        mah = parse_uid_mah(adb.sh("dumpsys batterystats", timeout=180), app_id)
        rec("C2", run, round(mah * scale, 2) if mah is not None else None, snote)
        temp1 = parse_temp_c(adb.sh("dumpsys thermalservice"))
        rec("C3", run, round(temp1 - temp0, 1) if None not in (temp0, temp1) else None, f"SKIN over {mins} min, not scaled")
        rec("C4", run, round((uid_bytes(adb, app_id) - net0) / 1048576 * scale, 2), snote)
    finally:
        adb.sh("dumpsys battery reset", check=False)
        adb.sh(f"settings put global stay_on_while_plugged_in {stay_on}", check=False)


def market_open(now=None):
    now = now or datetime.datetime.now()
    return now.weekday() < 5 and datetime.time(9, 15) <= now.time() <= datetime.time(15, 30)


def version_name(adb, pkg):
    m = re.search(r"versionName=(\S+)", adb.sh(f"dumpsys package {pkg}"))
    return m.group(1) if m else ""


def device_props(adb):
    g = lambda p: adb.sh(f"getprop {p}").strip()
    mem = re.search(r"MemTotal:\s+(\d+)", adb.sh("cat /proc/meminfo"))
    return {
        "model": f"{g('ro.product.manufacturer')} {g('ro.product.model')}".strip(),
        "android": g("ro.build.version.release"),
        "ram_gb": round(int(mem.group(1)) / 1024 / 1024, 1) if mem else "",
    }


def installed(adb, pkg):
    return bool(adb.sh(f"pm path {pkg}", check=False).strip())


def installed_apps(adb):
    """{app name: package} for every registry app present on the phone."""
    pkgs = set(l.split(":", 1)[1].strip() for l in adb.sh("pm list packages --user 0").splitlines() if ":" in l)
    return {name: v["package"] for name, v in B.load_apps().items() if v["package"] in pkgs}


# ---------------------------------------------------------------- config helpers

def resolve_app(app):
    return B.resolve_app(app)


def resolve_pkg(app, override):
    if override:
        return override
    pkg = B.load_apps().get(app, {}).get("package", "")
    if not pkg:
        sys.exit(f"No package saved for {app}. Run: python3 bench.py find \"{app}\" <keyword> --save  (or pass --pkg)")
    return pkg


def ask(msg):
    if not sys.stdin.isatty():
        sys.exit(f"bench.py needs your terminal for its prompts (next prompt: '{msg}'). "
                 "Run this exact command yourself in a Terminal, or type it in Claude Code with a leading '!'.")
    try:
        resp = input(f"  → {msg} [Enter = continue, q = stop] ").strip().lower()
    except EOFError:
        raise Abort()
    if resp == "q":
        raise Abort()


def artifact_path(module, app, metric, run, ext):
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return ARTIFACTS / module["name"] / f"{B.safe_name(app)}_{metric}_run{run}_{stamp}.{ext}"


# ---------------------------------------------------------------- commands

def cmd_devices(a):
    print(subprocess.run([find_adb(), "devices", "-l"], capture_output=True, text=True).stdout)


def cmd_find(a):
    adb = Adb(a.serial); adb.ensure_device()
    pkgs = sorted(l.split(":", 1)[1].strip() for l in adb.sh("pm list packages --user 0").splitlines() if ":" in l)
    hits = [p for p in pkgs if a.keyword.lower() in p.lower()]
    if not hits:
        sys.exit(f"No installed package contains '{a.keyword}'. Is {a.app} installed on this phone?")
    for p in hits:
        print(f"  {p}  ({version_name(adb, p)})")
    if a.save:
        if len(hits) != 1:
            sys.exit("More than one match; rerun with a more specific keyword, or set it with --pkg on each run.")
        apps = json.loads(B.APPS_FILE.read_text())
        entry = apps.get(a.app, {})
        if isinstance(entry, str):
            entry = {"package": entry, "ranked": True}
        entry["package"] = hits[0]
        entry.setdefault("ranked", True)
        apps[a.app] = entry
        B.APPS_FILE.write_text(json.dumps(apps, indent=2, ensure_ascii=False) + "\n")
        print(f"  Saved {a.app} = {hits[0]} in {B.APPS_FILE.name}")


def cmd_info(a):
    app = resolve_app(a.app)
    adb = Adb(a.serial); adb.ensure_device()
    pkg = resolve_pkg(app, a.pkg)
    if not installed(adb, pkg):
        sys.exit(f"{pkg} is not installed on this device.")
    d = device_props(adb)
    print(f"  App:       {app}\n  Package:   {pkg}\n  Version:   {version_name(adb, pkg)}\n"
          f"  Launcher:  {launcher_component(adb, pkg)}\n"
          f"  Device:    {d['model']} · Android {d['android']} · {d['ram_gb']} GB RAM")
    if a.framework:
        apks = [l.split(":", 1)[1].strip() for l in adb.sh(f"pm path {pkg}").splitlines() if ":" in l]
        names = []
        with tempfile.TemporaryDirectory() as tmp:
            for i, apk in enumerate(apks):
                local = os.path.join(tmp, f"{i}.apk")
                adb.run("pull", apk, local, timeout=600)
                with zipfile.ZipFile(local) as z:
                    names += z.namelist()
        print(f"  Framework: {detect_framework(names)}")


def cmd_installed(a):
    adb = Adb(a.serial); adb.ensure_device()
    found = installed_apps(adb)
    for name, pkg in found.items():
        print(f"  {name:<10} {pkg:<32} {version_name(adb, pkg)}")
    missing = [n for n in B.load_apps() if n not in found]
    if missing:
        print(f"  Not installed: {', '.join(missing)}")


def cmd_status(a):
    module = B.load_module(a.module)
    developer = B.get_developer(a.developer)
    if a.device_model:
        model = a.device_model
    else:
        adb = Adb(a.serial); adb.ensure_device()
        model = device_props(adb)["model"]
    folder = B.results_dir(module["name"], developer, model, a.results_dir)
    st = B.read_state(folder)
    print(f"  {folder}  (module version {module['version']})")
    apps = sorted(st["apps"]) or []
    if not apps:
        print("  No results yet.")
    for app in apps:
        gaps = B.missing(module, folder, app)
        if not gaps:
            print(f"  {app}: complete")
        else:
            short = ", ".join(f"{m} {d}/{n}" for m, (d, n) in sorted(gaps.items())[:12])
            more = "" if len(gaps) <= 12 else f" … +{len(gaps) - 12} more"
            print(f"  {app}: missing {short}{more}")


def cmd_run(a):
    app = resolve_app(a.app)
    module = B.load_module(a.module)
    is_app_scope = module["name"] == B.APP_SCOPE
    groups = (a.group or DEFAULT_GROUPS[B.APP_SCOPE if is_app_scope else "module"]).split(",")
    bad = set(groups) - set(GROUPS)
    if bad:
        sys.exit(f"--group accepts {', '.join(GROUPS)} (got {', '.join(sorted(bad))})")
    if is_app_scope and set(groups) - {"coldstart", "ram"}:
        sys.exit("Module _app only takes --group coldstart,ram (phone-scoped metrics).")
    if not 1 <= a.runs <= B.NRUNS:
        sys.exit(f"--runs must be 1–{B.NRUNS}")
    if set(groups) & {"scroll", "gesture", "idle"}:
        try:
            import perfetto  # noqa: F401
        except ImportError:
            sys.exit("Perfetto traces need the perfetto package: pip3 install --user perfetto")
    developer = B.get_developer(a.developer)

    adb = Adb(a.serial); adb.ensure_device()
    ensure_screen_ready(adb)
    pkg = resolve_pkg(app, a.pkg)
    if not installed(adb, pkg):
        sys.exit(f"{pkg} is not installed on this device.")
    comp = launcher_component(adb, pkg)
    app_id = parse_app_id(adb.sh(f"dumpsys package {pkg}"))
    w, h = parse_screen_size(adb.sh("wm size"))
    d = device_props(adb)
    meta = {"app": app, "developer": developer, "pkg": pkg, "version": version_name(adb, pkg),
            "model": d["model"], "android": d["android"], "ram_gb": d["ram_gb"]}
    folder = B.results_dir(module["name"], developer, d["model"], a.results_dir)
    screen = B.app_screen(module, app) if not is_app_scope else "home"
    if not is_app_scope and screen is None:
        sys.exit(f"{app} has no screen for module {module['name']} (N/A). Nothing to measure.")
    lst = module.get("rise", {}).get("list", "the list") if not is_app_scope else ""
    fracs = B.scroll_fracs(module, app) if not is_app_scope else (0.5, 0.75, 0.30)
    gestures = module.get("gestures", {}).get("per_app", {}).get(app, [])
    open_tap = module.get("open_tap", {}).get("per_app", {}).get(app)

    print(f"\n{app} {meta['version']} on {d['model']} (Android {d['android']}, {d['ram_gb']} GB) — module {module['name']} "
          f"[{module['version']}] · {a.runs} run(s) · {', '.join(groups)}{' + R3' if a.with_r3 else ''}")
    print(f"Results: {folder}")
    if not is_app_scope:
        print(f"Screen on {app}: {screen}")
    if set(groups) & {"ram", "scroll", "live", "idle", "gesture", "leak", "open"}:
        print("Use the MEDIUM test account. Keep the phone still, on Wi-Fi, with no other apps open.")
    if set(groups) & {"live", "idle"} and not market_open():
        print("! Market is closed right now (09:15–15:30 IST, Mon–Fri). Live-tick metrics should be taken during market hours.")
    if "live" in groups:
        print(f"Live session: {a.live_minutes} min per run, so about {a.runs * (a.live_minutes + 2)} min in total.")

    def applies(metric):
        return B.metric_applies(metric, module)[0]

    def group_ids(group):
        ids = [m for m in B.BENCH_GROUPS[group] if applies(m)]
        if group == "idle" and not a.with_video:
            ids = [m for m in ids if m != "U5"]
        if group == "ram" and a.with_r3 and applies("R3"):
            ids.append("R3")
        return ids

    def group_done(group, run):
        ids = group_ids(group)
        return all(run in B.runs_done(folder, app, m) for m in ids) if ids else True

    if a.redo:
        dropped = B.forget_runs(folder, app, [m for g in groups for m in group_ids(g)], a.redo)
        print(f"Redo run {a.redo}: {', '.join(dropped) or 'nothing was recorded for it'}")
    if gestures:
        try:
            rendered = [render_gesture(g["cmd"], w, h) for g in gestures]
        except ValueError as e:
            sys.exit(f"modules/{module['name']}.json gestures for {app}: {e}")
        if "gesture" in groups:
            print("Gestures that will be played on the phone (from the module file):")
            for g, c in zip(gestures, rendered):
                print(f"    {g.get('label', '?'):<24} {c}")
    if open_tap:
        try:
            open_tap = render_gesture(open_tap, w, h)
        except ValueError as e:
            sys.exit(f"modules/{module['name']}.json open_tap for {app}: {e}")

    rows = []

    def rec(metric, run, value, note="", artifact=""):
        if not applies(metric):
            why = B.metric_applies(metric, module)[1]
            print(f"    {metric}: not recorded ({why})")
            return
        if run in B.runs_done(folder, app, metric) or any(r["metric"] == metric and r["run"] == run for r in rows):
            print(f"    {metric}: run {run} already recorded, keeping the earlier value")
            return
        rows.append({"ts": B.now_iso(), "metric": metric, "run": run, "value": value, "note": note,
                     "artifact": str(artifact) if artifact else "", "source": "bench.py"})
        if value is None:
            print(f"    {metric}: no reading {note}")
        else:
            print(f"    {metric}: {value} {B.METRICS[metric]['unit']} {note}".rstrip())

    def flush():
        nonlocal rows
        if rows:
            B.append_rows(folder, rows, meta, module)
            rows = []

    try:
        for i in range(1, a.runs + 1):
            todo = [g for g in groups if not group_done(g, i)]
            if not todo:
                print(f"\n  Run {i}/{a.runs}: already recorded, skipping")
                continue
            print(f"\n  Run {i}/{a.runs}: {', '.join(todo)}")
            adb.sh("logcat -b main -b system -c", check=False)  # keep the crash buffer for A1/A2
            if "coldstart" in todo:
                rec("L1", i, cold_start_ms(adb, comp))
                time.sleep(5)
                count, longest, cnote = contention(adb, pkg)
                rec("X4", i, count, f"longest={longest}ms; 5 s after launch" + (f"; {cnote}" if cnote else ""))
            else:
                adb.sh(f"am start -S -n {comp}")

            need_home = set(todo) & {"ram", "open", "scroll", "gesture", "idle", "leak", "live"}
            if need_home:
                ask("Unlock / enter PIN. Press Enter when HOME is fully loaded.")
                if "ram" in todo and applies("R1"):
                    time.sleep(5)
                    mi = meminfo(adb, pkg)
                    rec("R1", i, mi["pss_mb"], meminfo_note(mi))

            on_screen = set(todo) & {"ram", "open", "scroll", "gesture", "idle", "leak", "live"} and not is_app_scope
            if on_screen:
                if "open" in todo:
                    net0 = uid_bytes(adb, app_id)
                    ask(f"Open {screen}. Press Enter the moment it is fully loaded.")
                    time.sleep(OPEN_SETTLE)
                    rec("L15", i, round((uid_bytes(adb, app_id) - net0) / 1024, 1), f"open + {OPEN_SETTLE} s")
                else:
                    ask(f"Open {screen}. Press Enter when {lst} is loaded.")
                if "ram" in todo:
                    time.sleep(5)
                    mi = meminfo(adb, pkg)
                    rec("R2", i, mi["pss_mb"], meminfo_note(mi))
                if "scroll" in todo:
                    print(f"    Scrolling {lst} ({FLINGS} flings) under a Perfetto trace, don't touch the phone…")
                    art = artifact_path(module, app, "S1", i, "pftrace")
                    g = scroll_test(adb, pkg, w, h, fracs, art)
                    if g is None:
                        note = f"no frames from the app; was {lst} on screen?"
                        for m in B.BENCH_GROUPS["scroll"]:
                            rec(m, i, None, note)
                    else:
                        note = f"({g['frames']} frames, layer {g['layer'][:60]})"
                        rec("S1", i, g["jank_pct"], note, art)
                        rec("S2", i, g["p50"]); rec("S3", i, g["p90"]); rec("S4", i, g["p99"])
                        rec("S5", i, g["fps"])
                if "gesture" in todo:
                    if not gestures:
                        rec("S7", i, None, f"no gestures defined for {app} in modules/{module['name']}.json; record manually")
                    else:
                        ask(f"Gestures listed above will be played on {screen}. Press Enter to play them (q to stop).")
                        print(f"    Playing {len(gestures)} gesture(s) under a Perfetto trace, don't touch the phone…")
                        art = artifact_path(module, app, "S7", i, "pftrace")
                        g = gesture_test(adb, pkg, gestures, w, h, art)
                        if g is None:
                            rec("S7", i, None, "no frames from the app during the gestures")
                        else:
                            rec("S7", i, g["jank_pct"], f"{g['labels']} ({g['frames']} frames, p99 {g['p99']} ms)", art)
                if "idle" in todo:
                    print(f"    Idle trace: {IDLE_SECONDS} s with no input, don't touch the phone…")
                    art = artifact_path(module, app, "U4", i, "pftrace")
                    g = idle_test(adb, pkg, art)
                    if g is None:
                        rec("U4", i, None, "no frames from the app while idle")
                    else:
                        rec("U4", i, g["fps"], f"{g['frames']} frames in {IDLE_SECONDS} s, jank {g['jank_pct']}%", art)
                    if a.with_video:
                        print(f"    Idle recording: {IDLE_SECONDS} s screenrecord, don't touch the phone…")
                        art = artifact_path(module, app, "U5", i, "mp4")
                        pct, note = video_idle_test(adb, art)
                        rec("U5", i, pct, note, art if pct is not None else "")
                if a.with_r3 and "ram" in todo:
                    print(f"    Soaking {SOAK_SECONDS // 60} min on {screen} with a scroll every minute…")
                    for k in range(SOAK_SECONDS // 60):
                        time.sleep(60)
                        fling(adb, w, h, fracs, down=k % 2 == 0)
                    mi = meminfo(adb, pkg)
                    rec("R3", i, mi["pss_mb"], meminfo_note(mi))
                if "leak" in todo:
                    ask(f"Go to the screen just BEFORE {screen} (the one you open it from). Press Enter when settled.")
                    time.sleep(2)
                    p0 = pss_mb(adb, pkg)
                    for k in range(1, LEAK_CYCLES + 1):
                        if open_tap:
                            adb.sh(open_tap, check=False); time.sleep(3)
                            adb.sh("input keyevent KEYCODE_BACK"); time.sleep(2)
                        else:
                            ask(f"Open {screen}, wait for it to load, then go back ({k}/{LEAK_CYCLES}).")
                    time.sleep(2)
                    mi = meminfo(adb, pkg)
                    rec("R9", i, round(mi["pss_mb"] - p0, 1),
                        f"{LEAK_CYCLES} cycles, {'scripted' if open_tap else 'manual'}; before={p0} after={mi['pss_mb']}; {meminfo_note(mi)}")
                if "live" in todo:
                    live_session(adb, pkg, app_id, i, rec, screen, a.live_minutes)

            flush()
            adb.sh(f"am force-stop {pkg}")
            time.sleep(3)
    except (Abort, KeyboardInterrupt):
        print("\n  Stopped early, saving what was collected.")
        flush()
        aborted = True
    except Exception:
        flush()
        raise
    else:
        aborted = False

    gaps = B.missing(module, folder, app)
    auto = {m: v for m, v in gaps.items() if m in B.AUTOMATED}
    manual = {m: v for m, v in gaps.items() if m not in B.AUTOMATED}
    print(f"\n  Saved to {folder / 'runs.csv'}")
    if auto:
        print("  Still missing (bench.py): " + ", ".join(f"{m} {d_}/{n}" for m, (d_, n) in sorted(auto.items())))
    if manual:
        print(f"  Manual metrics still missing: {len(manual)} (python3 record.py --module {module['name']} --app \"{app}\" --list)")
    if aborted:
        sys.exit(1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("-s", "--serial", help="device serial when more than one is connected")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("devices", help="list connected devices").set_defaults(fn=cmd_devices)
    sub.add_parser("installed", help="which registry apps are on this phone").set_defaults(fn=cmd_installed)

    f = sub.add_parser("find", help="find an app's package name on the phone")
    f.add_argument("app"); f.add_argument("keyword")
    f.add_argument("--save", action="store_true", help=f"remember it in {B.APPS_FILE.name}")
    f.set_defaults(fn=cmd_find)

    i = sub.add_parser("info", help="show version, launcher activity and (optionally) framework")
    i.add_argument("app"); i.add_argument("--pkg")
    i.add_argument("--framework", action="store_true", help="pull the APK(s) to detect Native / Flutter / React Native")
    i.set_defaults(fn=cmd_info)

    s = sub.add_parser("status", help="what is recorded and what is missing for a module")
    s.add_argument("--module", required=True); s.add_argument("--developer"); s.add_argument("--results-dir")
    s.add_argument("--device-model", help="skip adb and name the phone folder directly")
    s.set_defaults(fn=cmd_status)

    r = sub.add_parser("run", help="run a measurement session")
    r.add_argument("app"); r.add_argument("--pkg")
    r.add_argument("--module", required=True, help="module name from modules/ (or _app for phone-scoped metrics)")
    r.add_argument("--developer", help="your name (default: ~/.riise-benchmark/me.json)")
    r.add_argument("--results-dir", help="write under this folder instead of results/ (dry runs)")
    r.add_argument("--runs", type=int, default=5)
    r.add_argument("--group", help=f"comma list of {', '.join(GROUPS)} (default: {DEFAULT_GROUPS['module']}; _app: {DEFAULT_GROUPS[B.APP_SCOPE]})")
    r.add_argument("--with-r3", action="store_true", help="also take R3 (adds 5 min per run)")
    r.add_argument("--with-video", action="store_true", help="in --group idle, also record U5 (screenrecord + ffmpeg)")
    r.add_argument("--redo", type=int, metavar="N", help="measure run N again for the selected groups (replaces the earlier rows)")
    r.add_argument("--live-minutes", type=int, default=LIVE_SECONDS // 60,
                   help="live session length (default 15). C2 and C4 are scaled to a 15-min equivalent")
    r.set_defaults(fn=cmd_run)

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()

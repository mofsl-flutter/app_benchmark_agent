#!/usr/bin/env python3
"""Screen timings (L3–L8, L12, L14) from screen recordings. You tap; this script records and measures.

Replaces counting scrcpy frames by hand. For each test it records the screen while reading the
touchscreen, then works out:
  t0        the frame where your finger lands (Show taps draws a dot there)
  response  first large change on screen after t0 (kept in the note)
  settled   last large change before the screen goes quiet; regions still changing at the end of
            the clip (price tickers, animated banners) are masked out
The settled time (ms after t0) is the metric value. Clips stay on your Mac under
~/.riise-benchmark/artifacts/<module>/ and are referenced by file name.

  python3 timing.py RISE --module mf                    # L3,L5,L6,L4,L14,L7, runs 1..3 (module run counts)
  python3 timing.py RISE --module mf --tests L8 --runs 1
  python3 timing.py RISE --module mf --tests L12        # with Developer options → Network download rate limit set
  python3 timing.py --reanalyse clip.mp4 [...]          # re-run the analysis on saved clips

Read-only: the script never taps. Each test asks for ONE action (open a tab, open an item, pull,
tap the app icon). Never tap buy, invest, SIP, redeem, withdraw or add-money buttons.
"""
import argparse
import os
import re
import shutil
import subprocess
import sys
import time

import benchlib as B
import bench
from bench import Adb, Abort, ask

TESTS = {
    "L3": "{screen} first open (after a cold launch)",
    "L4": "{screen} re-open (coming back from another tab)",
    "L5": "{detail} open",
    "L6": "Pull-to-refresh on {screen}",
    "L7": "Resume after 30 s in background",
    "L8": "Resume after 5 min in background",
    "L12": "{screen} first open on a throttled network",
    "L14": "Tab / sub-section switch on {screen}",
}
DEFAULT_TESTS = "L3,L5,L6,L4,L14,L7"

REC_SECONDS = 12
FPS = 60
SCALE_W = 270            # analysis width (1080 → 4× smaller)
REMOTE = "/sdcard/bench_timing.mp4"
QUIET_S = 1.2            # settled = followed by this long with only small changes
LIVE_S = 3.0             # pixels changing in the clip's last 3 s count as live (tickers, animations)


def touch_device(adb):
    out = adb.sh("getevent -lp", check=False)
    dev, best = None, None
    for block in re.split(r"\nadd device \d+: ", "\n" + out):
        m = re.match(r"(/dev/input/event\d+)", block)
        mx = re.search(r"ABS_MT_POSITION_X\s*:.*?max (\d+)", block)
        my = re.search(r"ABS_MT_POSITION_Y\s*:.*?max (\d+)", block)
        if m and mx and my:
            dev, best = m.group(1), (int(mx.group(1)), int(my.group(1)))
            if "touchscreen" in block:
                break
    if not dev:
        sys.exit("No touchscreen found in getevent -lp.")
    return dev, best


def parse_touches(out, maxxy, size):
    """[(t_s, x_px, y_px)] for each finger-down in getevent -lt output."""
    touches, x, y, pending = [], None, None, None
    for line in out.splitlines():
        m = re.match(r"\[\s*([\d.]+)\]\s+(\S+)\s+(\S+)\s+(\S+)", line)
        if not m:
            continue
        t, code, val = float(m.group(1)), m.group(3), m.group(4)
        if code == "ABS_MT_POSITION_X":
            x = int(val, 16)
        elif code == "ABS_MT_POSITION_Y":
            y = int(val, 16)
        elif code == "BTN_TOUCH" and val == "DOWN":
            pending = t
        elif code == "SYN_REPORT" and pending is not None and x is not None and y is not None:
            touches.append((pending, x * size[0] / maxxy[0], y * size[1] / maxxy[1]))
            pending = None
    return touches


def load_frames(path):
    """Grey frames at a fixed FPS, SCALE_W wide, as a (n, h, w) uint8 array."""
    import numpy as np
    probe = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                            "stream=width,height", "-of", "csv=p=0", path], capture_output=True, text=True)
    w, h = (int(v) for v in probe.stdout.strip().split(",")[:2])
    sh = int(round(h * SCALE_W / w / 2)) * 2
    # screenrecord only writes a frame when the screen changes, so a static screen ends the file early:
    # pad with the last frame to the full clip length
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-vf",
                          f"fps={FPS},tpad=stop_mode=clone:stop_duration={REC_SECONDS},scale={SCALE_W}:{sh},format=gray",
                          "-frames:v", str(REC_SECONDS * FPS), "-f", "rawvideo", "-"], capture_output=True).stdout
    n = len(raw) // (SCALE_W * sh)
    return np.frombuffer(raw[: n * SCALE_W * sh], np.uint8).reshape(n, sh, SCALE_W), w / SCALE_W


def analyse(frames, factor, touches_xy):
    """(t0_idx, response_idx, settled_idx or None, how_t0_found)."""
    import numpy as np
    f = frames.astype(np.int16)
    diff = np.abs(f[1:] - f[:-1]) > 12                          # changed pixels, frame i+1 vs i
    diff[:, :int(diff.shape[1] * 0.05), :] = False               # ignore the status bar
    live = diff[-int(LIVE_S * FPS):].any(axis=0)                 # ticking / animating pixels
    live = np.maximum.reduce([np.roll(np.roll(live, dy, 0), dx, 1) for dy in (-2, 0, 2) for dx in (-2, 0, 2)])
    frac_all = diff.mean(axis=(1, 2))
    frac = (diff & ~live).mean(axis=(1, 2))                      # changes outside live regions
    dots = []
    for x, y in touches_xy or []:
        cx, cy, r = int(x / factor), int(y / factor), 10
        box = diff[:, max(cy - r, 0):cy + r, max(cx - r, 0):cx + r].mean(axis=(1, 2))
        hits = np.nonzero(box > 0.15)[0]
        if len(hits):
            dots.append(int(hits[0]) + 1)
    t0, how = None, "tap dot"
    if dots:
        big = np.nonzero(frac > 0.03)[0] + 1
        after = [b for b in big if b > min(dots)]
        resp0 = after[0] if after else None
        before = [d for d in dots if resp0 is None or d < resp0]
        t0 = max(before) if before else min(dots)                # the last tap before the screen responded
    if t0 is None:
        how = "first change (no tap dot found)"
        hits = np.nonzero(frac > 0.01)[0]
        if not len(hits):
            return None, None, None, "no change on screen"
        t0 = int(hits[0]) + 1
    big = np.nonzero(frac[t0 - 1:] > 0.03)[0]
    response = t0 + int(big[0]) if len(big) else None
    if np.any(frac_all[-int(LIVE_S * FPS):] > 0.15):
        return t0, response, None, how + "; big changes still happening at the end of the clip"
    moving = np.nonzero(frac[t0 - 1:] > 0.004)[0]               # 0.4 % of the non-live screen
    if not len(moving):
        return t0, response, t0, how
    last = t0 + int(moving[-1])
    settled = last if (len(frac) + 1 - last) / FPS >= QUIET_S else None
    return t0, response, settled, how


def problem_of(touches, t0, resp, settled):
    if not touches:
        return "no touch seen"
    if len(touches) > 1:
        return f"{len(touches)} touches (one action only)"
    if settled is None:
        return "did not settle in the clip (act sooner, or the screen kept changing)"
    if resp is not None and resp - t0 <= 2:
        return "tap dot not distinct from the screen change (light theme? use the app's dark mode)"
    return ""


def measure(adb, dev, maxxy, size, prompt, base):
    """Record REC_SECONDS while reading touches; the developer does one action after the prompt.
    Returns (settled_ms, response_ms, problem, how)."""
    adb.sh(f"rm -f {REMOTE}", check=False)
    ev = subprocess.Popen(adb.base + ["shell", f"timeout {REC_SECONDS + 2} getevent -lt {dev}"],
                          stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL, text=True)
    scr = subprocess.Popen(adb.base + ["shell", f"screenrecord --time-limit {REC_SECONDS} {REMOTE}"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    time.sleep(1.2)
    print(f"    ▶ {prompt}  (one action only, then hands off)")
    if shutil.which("say"):
        subprocess.Popen(["say", prompt.replace(" now", "").lower()], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    scr.wait(timeout=REC_SECONDS + 30)
    out, _ = ev.communicate(timeout=30)
    touches = parse_touches(out, maxxy, size)
    base.parent.mkdir(parents=True, exist_ok=True)
    video = f"{base}.mp4"
    adb.run("pull", REMOTE, video, check=False)
    with open(f"{base}.touches.txt", "w") as fh:
        fh.write(out)
    adb.sh(f"rm -f {REMOTE}", check=False)
    if not os.path.exists(video):
        return None, None, "recording failed", ""
    frames, factor = load_frames(video)
    if len(frames) < 2:
        return None, None, "recording has no frames", ""
    t0, resp, settled, how = analyse(frames, factor, [t[1:] for t in touches])
    if t0 is None:
        return None, None, how, how
    ms = lambda i: round((i - t0) * 1000 / FPS) if i is not None else None
    return ms(settled), ms(resp), problem_of(touches, t0, resp, settled), how


def reanalyse(paths, maxxy=(4095, 4095), size=(1080, 2340)):
    for v in paths:
        touches = parse_touches(open(v[:-4] + ".touches.txt").read(), maxxy, size)
        frames, factor = load_frames(v)
        t0, resp, settled, how = analyse(frames, factor, [t[1:] for t in touches])
        ms = lambda i: round((i - t0) * 1000 / FPS) if None not in (i, t0) else None
        print(f"{os.path.basename(v)}  touches={len(touches)}  response={ms(resp)}  settled={ms(settled)}  {how}")


def yes_no(q):
    while True:
        try:
            r = input(f"  ? {q} [y/n] ").strip().lower()
        except EOFError:
            raise Abort()
        if r in ("y", "n"):
            return "Yes" if r == "y" else "No"


def main():
    if len(sys.argv) > 2 and sys.argv[1] == "--reanalyse":
        return reanalyse(sys.argv[2:])
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("app")
    p.add_argument("--module", required=True)
    p.add_argument("--tests", default=DEFAULT_TESTS, help="order to run, from " + ",".join(TESTS))
    p.add_argument("--runs", type=int, help="measure runs 1..N that are still missing (default: the module's run count)")
    p.add_argument("-s", "--serial")
    p.add_argument("--developer")
    p.add_argument("--results-dir")
    p.add_argument("--pkg")
    a = p.parse_args()
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            sys.exit(f"{tool} is needed: brew install ffmpeg")
    try:
        import numpy  # noqa: F401
    except ImportError:
        sys.exit("numpy is needed: pip3 install --user numpy")

    app = bench.resolve_app(a.app)
    module = B.load_module(a.module)
    if module["name"] == B.APP_SCOPE:
        sys.exit("Screen timings belong to a module, not _app.")
    screen = B.app_screen(module, app)
    if screen is None:
        sys.exit(f"{app} has no screen for module {module['name']} (N/A).")
    tests = [t.strip().upper() for t in a.tests.split(",") if t.strip()]
    bad = [t for t in tests if t not in TESTS]
    if bad:
        sys.exit(f"Unknown test(s) {bad}. Choose from {', '.join(TESTS)}")
    skipped = [t for t in tests if not B.metric_applies(t, module)[0]]
    tests = [t for t in tests if t not in skipped]
    if skipped:
        print(f"  Not measured for module {module['name']}: {', '.join(skipped)}")
    words = {"screen": screen, "detail": module["rise"].get("detail", "the detail screen"),
             "list": module["rise"].get("list", "the list")}

    developer = B.get_developer(a.developer)
    adb = Adb(a.serial); adb.ensure_device(); bench.ensure_screen_ready(adb)
    pkg = bench.resolve_pkg(app, a.pkg)
    comp = bench.launcher_component(adb, pkg)
    dev, maxxy = touch_device(adb)
    size = bench.parse_screen_size(adb.sh("wm size"))
    d = bench.device_props(adb)
    meta = {"app": app, "developer": developer, "pkg": pkg, "version": bench.version_name(adb, pkg),
            "model": d["model"], "android": d["android"], "ram_gb": d["ram_gb"]}
    folder = B.results_dir(module["name"], developer, d["model"], a.results_dir)
    runs_for = lambda t: a.runs or B.expected(module).get(t, 3)
    facts = {r["metric"][2:] for r in B.read_runs(folder / "runs.csv") if r["app"] == app and r["metric"].startswith("F.")}
    no_ptr = any(r["app"] == app and r["metric"] == "F.pull_to_refresh" and r["value"] == "No"
                 for r in B.read_runs(folder / "runs.csv"))
    pending_facts = []
    if "L6" in tests and "pull_to_refresh" not in facts:
        ptr = yes_no(f"Does {screen} on {app} have pull-to-refresh? (check by looking, before starting)")
        pending_facts.append({"ts": B.now_iso(), "metric": "F.pull_to_refresh", "run": 1, "source": "timing.py",
                              "artifact": "", "value": ptr, "note": ""})
        no_ptr = ptr == "No"
    if no_ptr and "L6" in tests:
        tests.remove("L6")
        print(f"  {app} has no pull-to-refresh on {screen}: L6 is not measured.")

    touches_was = adb.sh("settings get system show_touches").strip() or "0"
    adb.sh("settings put system show_touches 1")
    print(f"\n{app} {meta['version']} · module {module['name']} · screen: {screen} · tests {', '.join(tests)}")
    print(f"Results: {folder}")
    print("Each test: wait for ▶, do ONE action, then don't touch the phone until the next prompt.")
    print("Read-only: never tap buy, invest, SIP, redeem, withdraw or add-money buttons.")
    if "L12" in tests:
        print("L12: set Developer options → Network download rate limit (about 1 Mbps) BEFORE starting, and reset it after.")

    rows = pending_facts

    def flush():
        nonlocal rows
        if rows:
            B.append_rows(folder, rows, meta, module)
            rows = []

    def run_test(t, i):
        """Set up and measure one test; returns 'redo' when the developer wants it repeated."""
        base = bench.artifact_path(module, app, t, i, "x")
        base = base.with_name(base.name[:-2])
        m = lambda prompt: measure(adb, dev, maxxy, size, prompt.format(**words), base)
        if t in ("L3", "L12"):
            adb.sh(f"am force-stop {pkg}"); time.sleep(1)
            adb.sh(f"am start -n {comp}")
            ask("Enter the PIN on the phone. Wait until the app's home is fully loaded (not on {screen}), then press Enter.".format(**words))
            res = m("Open {screen} now")
        elif t == "L4":
            ask("Open another tab of the app and let it load. Press Enter.")
            res = m("Open {screen} now")
        elif t == "L5":
            ask("Be on {screen}, with the {list} visible. Press Enter.".format(**words))
            res = m("Tap the FIRST item now")
            ask("Go back to {screen} (Back only). Press Enter.".format(**words))
        elif t == "L6":
            ask("Be at the top of {screen}. Press Enter.".format(**words))
            res = m("Pull down to refresh now")
        elif t == "L14":
            ask("Be on {screen}, on its first tab / section. Press Enter.".format(**words))
            res = m("Tap the NEXT tab or section now")
            ask("Go back to the first tab / section. Press Enter.")
        else:
            ask("Be on {screen}, with the app icon reachable from the home screen. Press Enter.\n"
                "    At ▶ tap the icon ONCE. If a PIN screen appears, don't enter it until the next prompt.".format(**words))
            wait = 30 if t == "L7" else 300
            adb.sh("input keyevent KEYCODE_HOME")
            for k in range(wait, 0, -1):
                print(f"      in background… {k:>3} s ", end="\r", flush=True)
                time.sleep(1)
            print()
            res = m("Tap the app ICON now")
        value, resp, problem, how = res
        clip = f"{base.name}.mp4"
        if problem:
            print(f"    ! {t}: {problem}")
            try:
                r = input("  → r + Enter = redo this test now, Enter = skip it (left blank) ").strip().lower()
            except EOFError:
                r = ""
            if r == "r":
                return "redo"
            print(f"    {t}: no reading ({problem})")
            return "done"
        note = f"timing.py: response {resp} ms; t0 from {how}"
        rows.append({"ts": B.now_iso(), "metric": t, "run": i, "value": value, "note": note,
                     "artifact": clip, "source": "timing.py"})
        print(f"    {t}: {value} ms  (first big change {resp} ms)")
        flush()
        return "done"

    try:
        for i in range(1, max(runs_for(t) for t in tests) + 1 if tests else 1):
            todo = [t for t in tests if i <= runs_for(t) and i not in B.runs_done(folder, app, t)]
            if not todo:
                continue
            print(f"\n  Run {i}")
            for t in todo:
                print(f"  {t}: {TESTS[t].format(**words)}")
                while run_test(t, i) == "redo":
                    print(f"  {t}: again")
        if "pin_on_resume" not in facts and ({"L7", "L8"} & set(tests)):
            rows.append({"ts": B.now_iso(), "metric": "F.pin_on_resume", "run": 1, "source": "timing.py", "artifact": "",
                         "value": yes_no("Did it ask for the PIN when resuming after 30 s?"), "note": ""})
    except (Abort, KeyboardInterrupt):
        print("\n  Stopped early, saving what was collected.")
    finally:
        flush()
        adb.sh(f"settings put system show_touches {touches_was}", check=False)
    gaps = {m: v for m, v in B.missing(module, folder, app).items() if m in TESTS}
    print(f"\n  Saved to {folder / 'runs.csv'}. Clips: {bench.ARTIFACTS / module['name']}")
    if gaps:
        print("  Timings still missing: " + ", ".join(f"{m} {d_}/{n}" for m, (d_, n) in sorted(gaps.items())))


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""drive.py — run bench.py without a human at the keyboard.

bench.py pauses with "Press Enter" prompts while someone works the phone. This script runs
bench.py inside a pseudo-terminal, watches for those prompts, does the phone work over adb
(open the module screen, type a query, go back) and presses Enter. It never types a PIN,
password or OTP: when it sees a login / PIN screen it waits for the developer to clear it.

    python3 drive.py run "RISE" --module _app --runs 5          # same arguments as bench.py run
    python3 drive.py run "Kite" --module search --runs 3
    python3 drive.py open "Kite" --module search                 # try the open steps alone, no measuring
    python3 drive.py find "Search"                               # list UI nodes matching a text

Prompts handled
    "Unlock / enter PIN. Press Enter when HOME is fully loaded."      wait for the app's home, Enter
    "Open <screen>. Press Enter ..."                                   run the open steps, Enter
    "Gestures listed above will be played ..."                         Enter
    "Go to the screen just BEFORE <screen> ..."                        run the back steps, Enter
    "Open <screen>, wait for it to load, then go back (k/N)."          open steps, back steps, Enter

Open / back steps come from the module file, key "auto_open" (not part of the module version):
    "auto_open": {
      "default": ["find:{screen}", "sleep:2", "text:{subject}", "sleep:4", "hide_keyboard"],
      "back":    ["hide_keyboard", "key:KEYCODE_BACK", "sleep:2"],
      "per_app": {"Kite": ["tap:0.5 0.08", "sleep:2", "text:{subject}", "sleep:4", "hide_keyboard"]}
    }
When the key is missing, the defaults shown above are used. Step forms:
    find:<text>        tap the first on-screen node whose text, content-desc or resource-id contains <text>
    tap:X Y            tap at screen fractions 0..1
    swipe:X1 Y1 X2 Y2 [ms]
    text:<string>      type with `input text`; {subject} = first module test_subject, {screen} = screen name
    key:<KEYCODE>      e.g. key:KEYCODE_BACK
    sleep:<seconds>
    hide_keyboard      BACK once if the soft keyboard is showing
Driver options (before the bench.py arguments): --settle S (default 8), --auth-wait S (default 300),
--log PATH, --dry (print what would be sent, do not run bench.py).
"""
import argparse
import datetime
import os
import pty
import re
import select
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

import benchlib as B

HERE = Path(__file__).resolve().parent
BENCH = HERE / "bench.py"
ART_DIR = Path(os.environ.get("RIISE_BENCH_HOME", Path.home() / ".riise-benchmark")) / "artifacts"

PROMPT_RE = re.compile(r"\[Enter = continue, q = stop\]\s*$")
AUTH_WORDS = re.compile(
    r"\b(m?pin|passcode|enter (your )?pin|log ?in|sign ?in|password|otp|one.time password|"
    r"fingerprint|biometric|verify (your )?identity|unlock)\b", re.I)
FOREIGN_WINDOWS = re.compile(r"(com\.emanuelef\.remote_capture|com\.android\.vpndialogs)")  # PCAPdroid consent / VPN dialog
AUTH_WINDOWS = re.compile(r"(pin|lock|login|auth|otp|passcode|biometric|accountpicker|chooseaccount|signin|sign_in)", re.I)
DEFAULT_OPEN = ["find:{screen}", "sleep:2", "text:{subject}", "sleep:4", "hide_keyboard"]
DEFAULT_BACK = ["hide_keyboard", "key:KEYCODE_BACK", "sleep:2"]
FIND_TRIES = 4


# ---------------------------------------------------------------- pure helpers (tested in tests/)

def classify_prompt(line):
    """Which bench.py prompt this is: home, open, gestures, before, cycle, consent, exercise, or other."""
    if "PCAPdroid" in line:
        return "consent"
    if line.lstrip("→ ").startswith("Exercise "):
        return "exercise"
    if "HOME is fully loaded" in line:
        return "home"
    if "Gestures listed above" in line:
        return "gestures"
    if "screen just BEFORE" in line:
        return "before"
    if re.search(r"then go back \(\d+/\d+\)", line):
        return "cycle"
    if line.lstrip("→ ").startswith("Open "):
        return "open"
    return "other"


def render_step(step, screen, subject, subject2=None):
    return (step.replace("{screen}", screen or "").replace("{subject2}", subject2 or subject or "")
            .replace("{subject}", subject or ""))


def parse_step(step):
    """('find', 'Search') / ('tap', [0.5, 0.08]) / ('swipe', [..]) / ('text', 'RELIANCE') / ('key', 'KEYCODE_BACK')
    / ('del', 8) (backspace N times, one by one) / ('sleep', 2.0) / ('hide_keyboard', None). ValueError on a bad step."""
    if step == "hide_keyboard":
        return "hide_keyboard", None
    if ":" not in step:
        raise ValueError(f"bad step {step!r}: expected kind:value")
    kind, _, val = step.partition(":")
    val = val.strip()
    if kind in ("find", "text", "key"):
        if not val:
            raise ValueError(f"bad step {step!r}: empty value")
        return kind, val
    if kind == "del":
        if not val.isdigit() or int(val) < 1:
            raise ValueError(f"bad step {step!r}: del needs a count")
        return kind, int(val)
    if kind == "sleep":
        return kind, float(val)
    if kind in ("tap", "swipe"):
        nums = [float(x) for x in val.split()]
        need = 2 if kind == "tap" else (4, 5)
        if (kind == "tap" and len(nums) != 2) or (kind == "swipe" and len(nums) not in need):
            raise ValueError(f"bad step {step!r}: wrong number of values")
        for f in nums[: 4 if kind == "swipe" else 2]:
            if not 0 <= f <= 1:
                raise ValueError(f"bad step {step!r}: fractions must be 0..1")
        return kind, nums
    raise ValueError(f"bad step {step!r}: unknown kind {kind!r}")


def auto_open_steps(module, app):
    cfg = (module or {}).get("auto_open") or {}
    per_app = cfg.get("per_app") or {}
    name = B.canonical_app(app) if B.is_rise(app) or B.is_unranked_rise(app) else app
    steps = per_app.get(app) or per_app.get(name) or cfg.get("default") or DEFAULT_OPEN
    return list(steps), list(cfg.get("back") or DEFAULT_BACK)


def exercise_steps(module, app):
    """Steps played on the screen during the net pass's 60 s window (auto_open.exercise: default / per_app).
    [] when the module defines none: the screen is then left idle."""
    cfg = ((module or {}).get("auto_open") or {}).get("exercise") or {}
    per_app = cfg.get("per_app") or {}
    name = B.canonical_app(app) if B.is_rise(app) or B.is_unranked_rise(app) else app
    return list(per_app.get(app) or per_app.get(name) or cfg.get("default") or [])


def parse_bounds(b):
    m = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", b or "")
    if not m:
        return None
    x1, y1, x2, y2 = map(int, m.groups())
    return (x1 + x2) // 2, (y1 + y2) // 2


def find_nodes(xml_text, text):
    """Nodes whose text / content-desc / resource-id contains `text` (case-insensitive), as dicts with
    center, clickable, and the matched attribute. Ranked: exact value match, then whole-word match, then
    substring ("Research" for "search" comes last); within a rank clickable nodes first, then nodes with a
    clickable ancestor (its center is used), then the rest. Empty list when nothing matches."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    needle = text.lower()
    word = re.compile(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])")
    parents = {c: p for p in root.iter() for c in p}
    out = []
    for n in root.iter("node"):
        for attr in ("text", "content-desc", "resource-id"):
            v = n.get(attr) or ""
            low = v.lower()
            if needle in low:
                tail = low.rsplit("/", 1)[-1]  # resource-id "com.x/search_bar" -> "search_bar"
                rank = 0 if low == needle or tail == needle else (1 if word.search(low.replace("_", " ")) else 2)
                clickable = n.get("clickable") == "true"
                target = n
                if not clickable:
                    p = parents.get(n)
                    while p is not None and p.get("clickable") != "true":
                        p = parents.get(p)
                    if p is not None:
                        target = p
                c = parse_bounds(target.get("bounds"))
                if c:
                    out.append({"center": c, "clickable": clickable, "via_parent": target is not n,
                                "attr": attr, "value": v, "class": n.get("class", ""), "rank": rank})
                break
    out.sort(key=lambda d: (d["rank"], 0 if d["clickable"] else (1 if d["via_parent"] else 2)))
    return out


def is_auth_screen(focus, texts):
    return bool(AUTH_WORDS.search(texts or "")) or bool(AUTH_WINDOWS.search(focus or ""))


def keyboard_shown(dump):
    m = re.search(r"mInputShown=(true|false)", dump or "")
    if m:
        return m.group(1) == "true"
    m = re.search(r"isInputViewShown=(true|false)", dump or "")
    return bool(m and m.group(1) == "true")


# ---------------------------------------------------------------- phone side

class Phone:
    def __init__(self, serial=None, log=print):
        self.base = ["adb"] + (["-s", serial] if serial else [])
        self.log = log
        self._size = None

    def sh(self, cmd, timeout=40):
        try:
            p = subprocess.run(self.base + ["shell", cmd], capture_output=True, text=True, timeout=timeout,
                               stdin=subprocess.DEVNULL)
            return p.stdout
        except subprocess.TimeoutExpired:
            return ""

    def size(self):
        if not self._size:
            m = re.search(r"(\d+)x(\d+)", self.sh("wm size"))
            self._size = (int(m.group(1)), int(m.group(2))) if m else (1080, 2340)
        return self._size

    def focus(self):
        out = self.sh("dumpsys window | grep -E 'mCurrentFocus|mFocusedApp'")
        return out.strip().splitlines()[0].strip() if out.strip() else ""

    def ui_xml(self):
        for attempt in range(2):
            self.sh("rm -f /sdcard/drive_ui.xml")
            out = self.sh("uiautomator dump /sdcard/drive_ui.xml", timeout=60)
            xml_text = self.sh("cat /sdcard/drive_ui.xml", timeout=30)
            if "<hierarchy" in xml_text:
                return xml_text
            if attempt == 0:
                self.log(f"uiautomator dump failed ({out.strip()[:80] or 'no output'}); screens that never "
                         "stop animating do this — use tap: steps for them")
            time.sleep(1)
        return ""

    def texts(self, xml_text=None):
        xml_text = xml_text if xml_text is not None else self.ui_xml()
        return " | ".join(v for v in re.findall(r'(?:text|content-desc)="([^"]+)"', xml_text) if v.strip())

    def keyboard(self):
        return keyboard_shown(self.sh("dumpsys input_method | grep -E 'mInputShown|isInputViewShown'"))

    def hide_keyboard(self):
        if self.keyboard():
            self.sh("input keyevent KEYCODE_BACK")
            time.sleep(1.5)
            return True
        return False

    def tap(self, x, y):
        self.sh(f"input tap {int(x)} {int(y)}")

    def in_app(self, pkg):
        return pkg in self.focus()

    def launch(self, pkg):
        self.sh(f"monkey -p {pkg} -c android.intent.category.LAUNCHER 1")

    def run_steps(self, steps, screen, subject, pkg, subject2=None):
        """Execute module steps. Returns a list of notes; raises RuntimeError when a find: step fails."""
        w, h = self.size()
        notes = []
        for raw in steps:
            step = render_step(raw, screen, subject, subject2)
            kind, val = parse_step(step)
            if kind == "sleep":
                time.sleep(val)
            elif kind == "del":
                for _ in range(val):
                    self.sh("input keyevent KEYCODE_DEL")
                    time.sleep(0.3)
                notes.append(f"deleted {val} chars one by one")
            elif kind == "tap":
                self.tap(val[0] * w, val[1] * h)
                notes.append(f"tap {val[0]:.2f},{val[1]:.2f}")
            elif kind == "swipe":
                ms = int(val[4]) if len(val) == 5 else 300
                self.sh(f"input swipe {int(val[0]*w)} {int(val[1]*h)} {int(val[2]*w)} {int(val[3]*h)} {ms}")
                notes.append("swipe")
            elif kind == "key":
                self.sh(f"input keyevent {val}")
                notes.append(val)
            elif kind == "text":
                if not val:
                    continue
                self.sh("input text " + val.replace(" ", "%s"))
                notes.append(f"typed {val}")
            elif kind == "hide_keyboard":
                if self.hide_keyboard():
                    notes.append("hid keyboard")
            elif kind == "find":
                hit = None
                for attempt in range(FIND_TRIES):
                    nodes = find_nodes(self.ui_xml(), val)
                    if nodes:
                        hit = nodes[0]
                        break
                    time.sleep(2)
                if not hit:
                    raise RuntimeError(f"find:{val}: no UI node matches on screen (focus: {self.focus()})")
                self.tap(*hit["center"])
                notes.append(f"tapped {hit['attr']}={hit['value']!r} at {hit['center']}")
                time.sleep(1.5)
            if pkg and not self.in_app(pkg):
                time.sleep(1.5)  # transitions briefly show no app window; look again before warning
                if not self.in_app(pkg):
                    notes.append(f"WARNING: focus left {pkg}: {self.focus()}")
        return notes


# ---------------------------------------------------------------- driver

class Driver:
    def __init__(self, a, bench_args):
        self.a = a
        self.bench_args = bench_args
        ns, _ = bench_run_parser().parse_known_args(bench_args)
        self.app = B.resolve_app(ns.app)
        self.module_name = ns.module
        self.module = None if ns.module == B.APP_SCOPE else B.load_module(ns.module)
        self.screen = (B.app_screen(self.module, self.app) if self.module else "") or ""
        subjects = (self.module or {}).get("test_subjects") or [""]
        self.subject = subjects[0]
        self.subject2 = subjects[1] if len(subjects) > 1 else subjects[0]
        self.pkg = ns.pkg or B.load_apps().get(self.app, {}).get("package", "")
        self.open_steps, self.back_steps = auto_open_steps(self.module, self.app) if self.module else ([], [])
        self.exercise = exercise_steps(self.module, self.app) if self.module else []
        ART_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        self.log_path = Path(a.log) if a.log else ART_DIR / f"drive-{ns.module}-{B.slug(self.app)}-{stamp}.log"
        self.log_file = open(self.log_path, "a", buffering=1)
        self.phone = Phone(ns.serial, self.say)
        self.prompts = 0

    def say(self, msg):
        line = f"\n[drive {time.strftime('%H:%M:%S')}] {msg}\n"
        self.log_file.write(line)
        sys.stdout.write(line)
        sys.stdout.flush()

    def echo(self, data):
        self.log_file.write(data)
        sys.stdout.write(data)
        sys.stdout.flush()

    # -- prompt handlers -------------------------------------------------------------------------
    def wait_not_auth(self):
        """Wait until the phone is not on a PIN / login screen. True when clear, False when timed out."""
        waited = 0
        while True:
            focus, texts = self.phone.focus(), self.phone.texts()
            if not is_auth_screen(focus, texts):
                return True
            if waited == 0:
                self.say(f"PIN / login screen showing ({focus}); waiting up to {self.a.auth_wait}s for the "
                         f"developer to clear it. I never type PINs. Seen: {texts[:160]}")
            if waited >= self.a.auth_wait:
                return False
            time.sleep(5)
            waited += 5

    def handle(self, kind, line):
        time.sleep(self.a.settle)
        if kind == "home":
            if not self.wait_not_auth():
                return "q", "still on a PIN / login screen"
            if self.pkg and not self.phone.in_app(self.pkg):
                self.say(f"app not in front ({self.phone.focus()}); launching {self.pkg}")
                self.phone.launch(self.pkg)
                time.sleep(self.a.settle)
                waited = 0
                while self.pkg and not self.phone.in_app(self.pkg) and waited < self.a.auth_wait:
                    if waited == 0:
                        self.say(f"another window is in front ({self.phone.focus()}); waiting up to "
                                 f"{self.a.auth_wait}s for the developer to dismiss it")
                    time.sleep(5)
                    waited += 5
                if self.pkg and not self.phone.in_app(self.pkg):
                    return "q", f"{self.pkg} never came to the front: {self.phone.focus()}"
            return "\n", f"home ready: {self.phone.focus()}"
        if kind in ("open", "cycle"):
            if not self.wait_not_auth():
                return "q", "still on a PIN / login screen"
            try:
                notes = self.phone.run_steps(self.open_steps, self.screen, self.subject, self.pkg)
            except (RuntimeError, ValueError) as e:
                return "q", f"could not open {self.screen}: {e}"
            if kind == "cycle":
                time.sleep(2)
                notes += self.phone.run_steps(self.back_steps, self.screen, self.subject, self.pkg)
            return "\n", f"{kind}: " + "; ".join(notes)
        if kind == "before":
            notes = self.phone.run_steps(self.back_steps, self.screen, self.subject, self.pkg)
            if self.pkg and not self.phone.in_app(self.pkg):
                self.phone.launch(self.pkg)
                time.sleep(3)
                notes.append("relaunched app")
            return "\n", "before: " + "; ".join(notes)
        if kind == "gestures":
            return "\n", "playing gestures"
        if kind == "exercise":
            if not self.exercise:
                return "\n", "no exercise steps for this app; leaving the screen idle"
            try:
                notes = self.phone.run_steps(self.exercise, self.screen, self.subject, self.pkg, self.subject2)
            except (RuntimeError, ValueError) as e:
                return "\n", f"exercise stopped: {e}"
            return "\n", "exercise: " + "; ".join(notes)
        if kind == "consent":
            waited = 0
            while FOREIGN_WINDOWS.search(self.phone.focus() or ""):
                if waited == 0:
                    self.say(f"PCAPdroid / VPN dialog showing ({self.phone.focus()}); waiting up to {self.a.auth_wait}s "
                             "for the developer to tap Allow / OK")
                if waited >= self.a.auth_wait:
                    return "q", "PCAPdroid consent dialog was not answered"
                time.sleep(5)
                waited += 5
            return "\n", f"consent dialog gone: {self.phone.focus()}"
        return "\n", "unknown prompt, pressing Enter"

    # -- main loop -------------------------------------------------------------------------------
    def run(self):
        cmd = [sys.executable, str(BENCH), "run"] + self.bench_args
        self.say(f"log {self.log_path}")
        self.say(f"app={self.app} pkg={self.pkg} module={self.module_name} screen={self.screen!r} "
                 f"subject={self.subject!r}")
        if self.module:
            self.say(f"open steps: {self.open_steps}  back steps: {self.back_steps}")
            self.say(f"exercise steps: {self.exercise or 'none (screen left idle in the net pass)'}")
        if self.a.dry:
            self.say(f"dry run; would start: {' '.join(cmd)}")
            return 0
        master, slave = pty.openpty()
        proc = subprocess.Popen(cmd, stdin=slave, stdout=slave, stderr=slave, close_fds=True, cwd=str(HERE))
        os.close(slave)
        buf = ""
        try:
            while True:
                r, _, _ = select.select([master], [], [], 1.0)
                if r:
                    try:
                        data = os.read(master, 4096).decode(errors="replace")
                    except OSError:
                        break
                    if not data:
                        break
                    self.echo(data)
                    buf = (buf + data)[-3000:]
                    if PROMPT_RE.search(buf):
                        line = buf.strip().splitlines()[-1].strip()
                        kind = classify_prompt(line)
                        self.prompts += 1
                        self.say(f"prompt {self.prompts} ({kind}): {line}")
                        answer, note = self.handle(kind, line)
                        self.say(("pressing Enter — " if answer == "\n" else "STOPPING (q) — ") + note)
                        os.write(master, b"\n" if answer == "\n" else (answer + "\n").encode())  # input() needs Enter
                        buf = ""
                if proc.poll() is not None:
                    while True:
                        r, _, _ = select.select([master], [], [], 0.5)
                        if not r:
                            break
                        try:
                            data = os.read(master, 4096).decode(errors="replace")
                        except OSError:
                            break
                        if not data:
                            break
                        self.echo(data)
                    break
        except KeyboardInterrupt:
            os.write(master, b"q\n")
            proc.wait(timeout=30)
        rc = proc.wait()
        self.say(f"bench.py exited with code {rc} after {self.prompts} prompt(s)")
        return rc


def bench_run_parser():
    p = argparse.ArgumentParser(add_help=False)
    p.add_argument("app")
    p.add_argument("--module", required=True)
    p.add_argument("--pkg")
    p.add_argument("-s", "--serial")
    return p


def mode_open(a, rest):
    d = Driver(a, rest)
    if not d.module:
        sys.exit("open needs a module (not _app)")
    d.say(f"launching {d.pkg} and running the open steps for {d.screen!r}")
    d.phone.launch(d.pkg)
    time.sleep(max(a.settle, 5))
    if not d.wait_not_auth():
        sys.exit("still on a PIN / login screen")
    try:
        notes = d.phone.run_steps(d.open_steps, d.screen, d.subject, d.pkg)
    except (RuntimeError, ValueError) as e:
        sys.exit(f"open failed: {e}")
    d.say("open: " + "; ".join(notes))
    d.say(f"focus now: {d.phone.focus()}  keyboard: {d.phone.keyboard()}")
    d.say("texts on screen: " + d.phone.texts()[:400])
    return 0


def mode_find(a, rest):
    text = rest[0] if rest else sys.exit("find needs a text")
    ph = Phone(None)
    nodes = find_nodes(ph.ui_xml(), text)
    w, h = ph.size()
    print(f"focus: {ph.focus()}   screen {w}x{h}   keyboard shown: {ph.keyboard()}")
    if not nodes:
        print(f"no node matches {text!r}")
        return 1
    for n in nodes:
        x, y = n["center"]
        how = "clickable" if n["clickable"] else ("via clickable parent" if n["via_parent"] else "not clickable")
        print(f"  {n['attr']}={n['value']!r:40.40} {n['class']:40.40} center=({x},{y}) "
              f"frac=({x/w:.2f},{y/h:.2f}) {how}")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("mode", choices=["run", "open", "find"])
    p.add_argument("--settle", type=float, default=8, help="seconds to wait after a prompt before acting")
    p.add_argument("--auth-wait", type=int, default=300, help="seconds to wait for the developer at a PIN screen")
    p.add_argument("--log", help="log file (default: ~/.riise-benchmark/artifacts/drive-<module>-<app>-<stamp>.log)")
    p.add_argument("--dry", action="store_true", help="show the plan, do not run bench.py")
    a, rest = p.parse_known_args()
    if a.mode == "find":
        sys.exit(mode_find(a, rest))
    if a.mode == "open":
        sys.exit(mode_open(a, rest))
    sys.exit(Driver(a, rest).run())


if __name__ == "__main__":
    main()

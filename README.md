# RISE benchmark — shared harness

Performance benchmark of the RISE app against Kite (+ Coin for MF), Groww, Angel One, INDmoney,
Kotak Neo, SAHI and Dhan, one **module** at a time (Portfolio, Home, Stocks, F&O, MF, Commodity,
Research, US Stocks, StratX, Watchlist, Quote, Search). Several developers work in parallel, each
on their assigned module and their own Android phone, through one Claude Code agent that follows
the same protocol for everyone. Results combine by folder; no spreadsheet is edited by hand.

| File | What |
|---|---|
| `.claude/agents/benchmark-runner.md` | The agent. `/benchmark <module>`, `/benchmark-report`, `/benchmark-module <name>` |
| `PROTOCOL.md` | How every run is done (pre-flight, order, run counts, market hours, safety) |
| `METRICS.md` | The 50 metrics: method, tool, unit, expected runs. Generated from `benchlib.py` |
| `modules/<name>.json` | One file per module: RISE screen, list, detail, competitor screens, scroll/gesture scripts, offline and data items |
| `apps.json` | App registry (package names, ranked or not). `RISE UAT` is never ranked |
| `weights.json` | Scorecard category weights (lead's sign-off) |
| `bench.py` | adb collector: cold start, lock contention, RAM, bytes per open, Perfetto scroll/gesture/idle, leak check, live session |
| `preflight.py` | Pre-run checks; writes `env.csv` |
| `record.py` | Records a manual metric or an offline/data item |
| `build_report.py` | Per-module workbook, combined workbook + scorecard, `METRICS.md` |
| `build_benchmark.py` | Workbook layout (imported by `build_report.py`) |
| `results/<module>/<developer>_<device>/` | `runs.csv`, `env.csv`, `state.json` — your folder only |
| `reports/` | Generated workbooks and scorecards, dated |
| `docs/` | The benchmark plan, the design, and example reports |
| `archive/` | The original Portfolio workbook, CSVs and context, for reference only |

## Setup (once per developer)

**Mac**

```bash
brew install android-platform-tools scrcpy ffmpeg
pip3 install --user openpyxl perfetto
adb devices            # your phone must show as "device"
```

**Phone** (Developer options): USB debugging on, Stay awake on, Show taps on, animation scales
1.0, Power saving off, Motion smoothness Adaptive, Private DNS Automatic. Install PCAPdroid and
LibChecker from the Play Store for the manual network and SDK metrics. Log in to every app you
will measure with the Medium test account.

**Identity**

```bash
python3 record.py --me "Your Name"     # stored in ~/.riise-benchmark/me.json
```

## Running a module

Open Claude Code in this folder and type `/benchmark <module>` (for example `/benchmark fno`).
The agent checks your tools and phone, confirms the module's screens with you, runs the
pre-flight, measures the phone-scoped metrics once, then drives `bench.py` and `record.py` app by
app. Stop any time; `/benchmark <module>` again resumes at the first missing run.

`bench.py run` prompts you to work the phone, so it must run in your own terminal; in Claude
Code, type it with a leading `!` (`! python3 bench.py run RISE --module fno`). By hand, the same
steps are:

```bash
python3 preflight.py --module fno
python3 bench.py run RISE --module _app              # once per phone: L1, X4, R1
python3 bench.py run RISE --module fno               # ram, open, scroll (5 runs)
python3 bench.py run RISE --module fno --group gesture,leak --runs 1
python3 bench.py run RISE --module fno --group idle --with-video --runs 3   # market hours
python3 bench.py run RISE --module fno --group live --runs 3 --live-minutes 10
python3 record.py --module fno --app RISE --list     # manual metrics still missing
python3 record.py --module fno --app RISE L14 --value 310 --note "Overview → Technicals"
python3 build_report.py --module fno
```

`/benchmark-report` (or `python3 build_report.py --combined`) rebuilds the combined workbook and
scorecard from every developer's results.

## Sharing (git)

Repo: `https://github.com/mofsl-flutter/app_benchmark_agent.git`. Each developer works on their
own branch (`results/<module>-<name>`), writes only inside `results/<module>/<their-name>_<phone>/`,
and opens a pull request with their `runs.csv`, `env.csv` and `state.json`. Nothing collides by
design. Generated `reports/` and the `archive/` are git-ignored; run `python3 build_report.py
--combined` after a `git pull` to rebuild the scorecard from everyone's results. Traces and
recordings stay on your Mac under `~/.riise-benchmark/artifacts/` and are referenced by file name;
they may show client-account screens and must never be committed (`*.pftrace` and `*.mp4` are
ignored).

## Comparing across phones

Within a module every app was measured on one phone, so the ranks are fair. Across modules the
phones differ: the combined scorecard compares RISE's **rank** and **0–100 score** per module and
never raw milliseconds.

## History

Decisions carried over from the Portfolio work (21–22 Oct 2026, `archive/CONTEXT.md`):

- FPS from a Perfetto FrameTimeline trace for all apps, because gfxinfo can't see Flutter frames.
  Janky = jank_type other than None or Buffer Stuffing.
- Battery (C2) from per-app `dumpsys batterystats` mAh with a simulated unplug; temperature (C3)
  from the SKIN sensor in `dumpsys thermalservice`, because `battery unplug` freezes the battery
  temperature. Live sessions may run 10 min; C2 and C4 are scaled to a 15-min equivalent.
- Throttling (L12) via Developer options → Network download rate limit = 1 Mbps.
- Scorecard: each metric 0–100 (best = 100, worst = 0), averaged per category, weighted by
  `weights.json`.
- Display: Motion smoothness Adaptive (120 Hz), kept fixed; Power saving off.
- 22 Oct 2026: the Portfolio run on the Galaxy S23 found Power saving on and a C3 bug (fixed);
  round-1 C3 values were invalid. That data is archived and Portfolio is re-run through the agent.

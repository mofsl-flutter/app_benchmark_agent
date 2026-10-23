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
| `apps.json` | App registry (package names, ranked or not, `own_domains` for X3). `RISE UAT` is never ranked |
| `weights.json` | Scorecard category weights (lead's sign-off) |
| `bench.py` | adb collector: cold start, lock contention, RAM, bytes per open, Perfetto scroll/gesture/idle, leak check, live session, PCAPdroid network pass, the app's API log |
| `apilog.py` | Parses the API lines RISE writes to logcat (method, path, status, duration, cache) into `api_calls.csv`; no bodies, no query strings |
| `netcap.py` | Reads a PCAPdroid capture (no scapy): connections, hosts (SNI / DNS), bytes, first-response time, into `net_calls.csv` |
| `preflight.py` | Pre-run checks; writes `env.csv` |
| `record.py` | Records a manual metric or an offline/data item |
| `build_report.py` | Per-module workbook, combined workbook + scorecard, `METRICS.md` |
| `build_benchmark.py` | Workbook layout (imported by `build_report.py`) |
| `results/<module>/<developer>_<device>/` | `runs.csv`, `env.csv`, `state.json`, plus `api_calls.csv` (RISE API calls per run) and `net_calls.csv` (connections per run) — your folder only |
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

**Identity and the PCAPdroid key**

```bash
python3 record.py --me "Your Name"            # stored in ~/.riise-benchmark/me.json
python3 record.py --pcapdroid-key <key>       # PCAPdroid → Settings → Control permissions → ⋮ → API key
```

The key lets `bench.py --group net` start and stop PCAPdroid captures over adb without a tap on
Allow each time. It stays in `me.json` on your Mac; never put it in notes or the repo.

## The agent: what it is and how to use it

The agent is a Claude Code agent definition in this repo. When you open Claude Code inside the
cloned folder, it is picked up automatically together with its three slash commands.

| File | What it is | Review it for |
|---|---|---|
| `.claude/agents/benchmark-runner.md` | The agent itself: hard rules (no PINs, no orders, write only in your own results folder), the step list for a run, how it combines reports, how it defines a module | Missing steps, wrong commands, anything that would make your module's run unfair or unsafe |
| `.claude/commands/benchmark.md` | `/benchmark <module>` — run or resume your module | Wording of the prompt |
| `.claude/commands/benchmark-report.md` | `/benchmark-report` — combine everyone's results into one scorecard | — |
| `.claude/commands/benchmark-module.md` | `/benchmark-module <name>` — define or edit a module (screens per app, list, gestures, items) | The questions it asks |
| `PROTOCOL.md` | The measurement rules the agent enforces | Steps that do not match how you actually measure |
| `METRICS.md` | Every metric with its method (generated from `benchlib.py`) | Unclear or wrong methods |
| `modules/<your-module>.json` | Your module's screens, list, gestures, offline and data items | Wrong screen names, missing competitor screens, items that do not fit |

### Using it, step by step

1. **Clone and set up** (section above), then `python3 record.py --me "<your name>"` once.
2. **Start Claude Code in the repo folder** and type `/benchmark <module>` with the module you were
   assigned (`portfolio`, `home`, `stocks`, `fno`, `mf`, `commodity`, `research`, `us_stocks`,
   `stratx`, `watchlist`, `quote`, `search`). Type `/benchmark` alone and it asks.
3. The agent then, in order: checks your Mac tools and that exactly one phone is on adb; loads
   your module and asks you to confirm its screens if it is still a seeded skeleton; lists which
   competitor apps are installed and shows the plan table; runs `preflight.py` (it stops on a hard
   failure such as private DNS fixed or battery under 50 %); measures the phone-scoped metrics
   (`_app`) once; then goes app by app.
4. **The agent runs `bench.py` itself** through `drive.py`, which answers the "Press Enter"
   prompts after doing the phone work over adb (open the screen, type the test symbol, go back).
   Keep the phone unlocked and nearby: when an app shows a PIN or login screen the driver waits
   up to five minutes for you to clear it (it never types a PIN), then gives up on that run. If
   it cannot reach a screen, the agent asks you to run the printed `bench.py run …` command in a
   separate Terminal window instead.
5. **Manual metrics** (scrcpy timings, offline items, data items, Exodus, Play Store, storage): the
   agent shows the method for one metric at a time and records your value with `record.py`.
6. **Stop any time.** `/benchmark <module>` again resumes at the first missing run.
7. When the module is complete, the agent builds `reports/<module>/…xlsx` and prints RISE's rank
   per category on your phone. Commit your results folder on a branch and open a pull request
   (see Sharing below).
8. Anyone can run `/benchmark-report` after `git pull` to rebuild the combined scorecard.

### Reviewing the agent and giving input

Please read `.claude/agents/benchmark-runner.md`, `PROTOCOL.md`, `METRICS.md` and your
`modules/<module>.json` before your first run. If a step is wrong, missing, unsafe, or does not
fit your module:

- small fixes (a screen name, a metric method, a missing competitor screen): edit the file on a
  branch named `agent/<topic>` and open a pull request, with one line on what changed and why;
- bigger questions (a metric that should be added or dropped, a change to the run protocol, a
  scorecard weight): open a GitHub issue on this repo titled `agent: <topic>` so the lead can
  decide before anyone's results depend on it.

Module files carry a version hash on every result row, so a change to a module after results
exist is flagged in the combined report rather than silently mixing old and new definitions.

## Running a module

Open Claude Code in this folder and type `/benchmark <module>` (for example `/benchmark fno`).
The agent checks your tools and phone, confirms the module's screens with you, runs the
pre-flight, measures the phone-scoped metrics once, then drives `bench.py` and `record.py` app by
app. Stop any time; `/benchmark <module>` again resumes at the first missing run.

`bench.py run` prompts for someone to work the phone. The agent runs it through
`python3 drive.py run RISE --module fno` (same arguments), which does the phone work over adb and
answers the prompts; `drive.py open RISE --module fno` tries the screen-opening steps alone and
`drive.py find "Search"` lists matching UI nodes to write `auto_open` steps for a module. Run
`bench.py` directly only in a real terminal (the Claude Code `!` prefix has no TTY). By hand, the
same steps are:

```bash
python3 preflight.py --module fno
python3 bench.py run RISE --module _app              # once per phone: L1, X4, R1
python3 bench.py run RISE --module fno               # ram, open, scroll (5 runs)
python3 bench.py run RISE --module fno --group gesture,leak --runs 1
python3 bench.py run RISE --module fno --group idle --with-video --runs 3   # market hours
python3 bench.py run RISE --module fno --group live --runs 3 --live-minutes 10
python3 bench.py run RISE --module fno --group net --runs 5     # last, alone: PCAPdroid pass (L11, X3, net_calls.csv)
python3 record.py --module fno --app RISE --list     # manual metrics still missing
python3 record.py --module fno --app RISE L14 --value 310 --note "Overview → Technicals"
python3 build_report.py --module fno
```

`/benchmark-report` (or `python3 build_report.py --combined`) rebuilds the combined workbook and
scorecard from every developer's results.

## API and network details

What can be seen per app, and where it ends up:

| App | What is captured | How | Where |
|---|---|---|---|
| RISE | Every API call: method, host, path, status, duration, CDN cache state, size when logged | RISE's production build logs each call to logcat as JSON; `bench.py` reads it in the `open` window and on `_app` cold starts | `api_calls.csv`, a summary in the L15 / R1 note, sheet `10 API & Network calls` |
| Every app | Connections opened, hosts (TLS SNI or DNS), bytes in/out, time to the first server byte | PCAPdroid capture per run, driven over adb by `bench.py --group net` | `net_calls.csv`, L11 (and X3 when `own_domains` is set), sheet 10 |

Competitor request paths and bodies are not readable: their release builds log nothing and Android
ignores user-installed certificates (TLS pinning). Response bodies are not captured for RISE either;
they appear only in the UAT build's debug log. Query strings are dropped and id-like path segments
are masked before anything is written to the shared results folder.

## Sharing (git)

Repo: `https://github.com/mofsl-flutter/app_benchmark_agent.git`. Each developer works on their
own branch (`results/<module>-<name>`), writes only inside `results/<module>/<their-name>_<phone>/`,
and opens a pull request with their `runs.csv`, `env.csv`, `state.json`, `api_calls.csv` and `net_calls.csv`. Nothing collides by
design. Generated `reports/` and the `archive/` are git-ignored; run `python3 build_report.py
--combined` after a `git pull` to rebuild the scorecard from everyone's results. Traces and
recordings stay on your Mac under `~/.riise-benchmark/artifacts/` and are referenced by file name;
they may show client-account screens and must never be committed (`*.pftrace`, `*.mp4` and
`*.pcap` are ignored).

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

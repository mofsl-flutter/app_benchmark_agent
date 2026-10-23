# Multi-developer RISE benchmark agent — design

Date: 2026-10-22
Status: approved 22 Oct 2026; Phase 1 built the same day (see README.md)
Author: Claude, from a conversation with Vivek Dubey

## 1. Intent and why

The RISE performance benchmark (RISE vs Kite, Groww, Angel One, INDmoney, Kotak Neo, SAHI, Dhan)
is too big for one person. One developer has already finished the **Portfolio** module in this
folder: a 14-tab workbook, `bench.py` (adb + Perfetto collector), and CSV results. The next
modules (Explore's tabs, Watchlist, Quote, Search, and whatever else gets assigned) will be done
by **several developers in parallel, each on their own phone**.

Without a shared method, each developer will measure slightly differently, name things
differently, and produce a spreadsheet nobody can combine. The design below gives every
developer the **same Claude Code agent**, which runs the **same protocol and metric catalogue**
for whichever module they are given, and writes results in a shape that **merges by file copy**
into one RISE-vs-competitors report.

Source material: `docs/RISE Benchmark Plan.md` (21 Oct, method and protocol; copied into this
folder), `docs/examples/groww-quote-page-benchmark.md` (another developer's finished Groww
Quote-page report, 22 Oct, the reference for what a per-app write-up must contain; see §6b), this folder's `CONTEXT.md`, `bench.py`, `build_benchmark.py`, and the Portfolio
workbook. The Portfolio work is a harness and workbook with partial data, not a finished
module: Vivek decided it is re-run fresh through the agent (see §8).

## 2. Goals, non-goals, anti-goals

**Goals**

- One agent, invoked as `/benchmark <module>`, that walks any developer through the full
  benchmark of one module on the phone they have, with no decisions left to taste.
- Identical metric IDs, units, run counts and protocol across modules, so a Portfolio number
  and an F&O number were produced the same way.
- Results from N developers combine without anyone editing a shared spreadsheet.
- The existing Portfolio harness and workbook layout are reused; its partial data is archived, not migrated.
- A developer can stop mid-way and resume later without redoing finished runs.

**Non-goals**

- Instrumenting RISE's source or competitor apps. Everything stays black-box (adb, Perfetto,
  scrcpy, PCAPdroid, Exodus/LibChecker), as both plans already require.
- Comparing absolute milliseconds across modules measured on different phones (see §9).
- A CI or server. This is a folder of scripts and markdown that runs on a developer's Mac.
- Git. Vivek chose a plain shared folder; the design never depends on a VCS.

**Anti-goals** (would make this a failure even if it "works")

- Two developers overwriting each other's results or workbook.
- A module whose numbers cannot be traced back to a run, device and date.
- A metric that silently means something different on two modules (for example "list" meaning
  holdings on Portfolio and an indices strip on Home without that being recorded).
- PINs, account numbers, or recordings leaving the shared folder's intended audience.

## 3. Constraints Vivek decided

| Decision | Choice |
|---|---|
| Who runs it | Several developers, each assigned a module at run time. The module list is not fixed in advance. |
| Phones | Each developer uses their own phone. |
| Results | Per-module CSV files; the workbook and scorecard are **generated** from them. |
| Location | This standalone folder (`riise-benchmark/`), shared as a plain folder, no git. |
| Competitor set | Union of both plans: Kite (+ Coin for MF), Groww, Angel One, INDmoney, Kotak Neo, SAHI, Dhan. The agent detects which are installed on the phone and marks the rest N/A. RISE UAT is measured optionally and never ranked, as in the Plan. |
| Metric catalogue | The workbook's 43 metrics, plus the seven added in §6b from the Groww report (L1–L13, S1–S6, U1–U3, O1, D1, X1–X3, R1–R8, C1–C4, A1–A4), generalised per module. `bench.py` keeps filling the 13 it already automates. The Plan's "Build and stack" facts (renderer, Flutter version, min Android) are an **unscored** info block on the App Info sheet, filled once per phone from the installed APKs. |
| Device tier | Dropped. No Budget/Flagship axis; every row carries the exact phone model, RAM and Android version. |
| Portfolio data | Not migrated. `results/*.csv` and the workbooks move to `archive/`; the Portfolio developer re-runs `/benchmark portfolio`. |

## 4. The developer's experience

1. Developer opens Claude Code in the shared folder and types `/benchmark fno` (or just
   `/benchmark`, and the agent asks which module).
2. The agent checks the Mac (adb, scrcpy, ffmpeg, Python packages), the phone (exactly one
   device, USB debugging), and asks the developer's name once, storing it on the Mac.
3. It loads `modules/fno.yaml`. If the module does not exist yet, it creates it interactively:
   which RISE screen, the matching screen on each competitor (or N/A), which list to scroll,
   whether the screen shows live prices, whether it depends on account size.
4. It reads the phone's installed packages against `apps.json` and shows a plan table: app ×
   screen, with N/A where the app is not installed or has no matching screen. It also asks,
   per app, whether the phone is logged in with holdings or a watchlist, since installed is
   not the same as usable. The developer confirms.
5. It runs the pre-flight checklist from the Plan (private DNS automatic, power saving off,
   refresh rate noted, battery above 50 %, show taps on, animation scales 1.0, Wi-Fi and speed
   test noted) and refuses to continue if a hard check fails. It writes one Env row.
6. If this developer has not yet measured the **phone-scoped** metrics on this phone (cold
   start L1, PIN-to-home L2, RAM after cold start R1, storage R4–R8, SDKs X1–X2, Play Store
   facts A3–A4, Build and stack), it does those first, once, under the pseudo-module `_app`.
   They are reused by every module this developer runs on this phone and are never counted
   again per module.
7. For each installed app, in rotated order, it runs the automated groups through `bench.py`
   (RAM on screen, scroll trace, and the live session when the market is open) and then walks
   the developer through the module's manual metrics one at a time, asking for each value with
   the method on screen, and records it.
8. Progress is saved after every run. `/benchmark fno` again resumes where it stopped.
9. When the module is complete the agent builds that module's workbook and prints RISE's rank
   per category on this phone.
10. Anyone can run `/benchmark-report` to rebuild the combined workbook and the one-page
   scorecard from every result file in the folder.

## 5. Folder layout

```
riise-benchmark/
  .claude/
    agents/benchmark-runner.md      the agent (protocol, metric catalogue, behaviour)
    commands/benchmark.md           /benchmark <module>        run or resume a module
    commands/benchmark-report.md    /benchmark-report          combine everything
    commands/benchmark-module.md    /benchmark-module <name>   define or edit a module
  README.md                         developer setup: Mac tools, phone settings, first run
  PROTOCOL.md                       the run protocol, lifted from the Plan and CONTEXT.md
  METRICS.md                        catalogue of the 50 metrics with the module placeholders (generated)
  docs/examples/groww-quote-page-benchmark.md   the report the seven metrics came from
  apps.json                         app registry (see §7)
  weights.yaml                      scorecard category weights, the only place they are edited
  modules/
    _app.yaml                       the phone-scoped metric set (§4 step 6)
    portfolio.yaml                  seeded from the existing work
    home.yaml, stocks.yaml, fno.yaml, mf.yaml, commodity.yaml, research.yaml,
    us_stocks.yaml, stratx.yaml, watchlist.yaml, quote.yaml, search.yaml   seeded skeletons
  bench.py                          collector, generalised (see §10)
  preflight.py                      the checklist, exits non-zero on a hard failure
  record.py                         appends a manual metric row to the developer's CSV
  build_report.py                   per-module workbook and the combined workbook + scorecard
  build_benchmark.py                kept; becomes a library build_report.py imports
  results/
    <module>/<developer>_<device-model>/
      env.csv                       pre-flight values, one row per session
      runs.csv                      every metric value, one row each (schema in §8)
      state.json                    what is done, for resume
    _app/<developer>_<device-model>/  phone-scoped metrics, same files
  reports/
    <module>/<module>_<developer>_<device>_<date>.xlsx
    combined/combined_<date>.xlsx
    combined/scorecard_<date>.md
  archive/                          the original portfolio workbook, backups and CSVs, untouched
```

Perfetto traces and scrcpy recordings are **not** placed in the shared folder. They are large
and show client-account screens. They stay on the developer's Mac under
`~/.riise-benchmark/artifacts/<module>/`, and each `runs.csv` row names its file, so a reviewer
can ask the developer for it. Update 22 Oct: after the build, Vivek decided to publish the folder
as the git repo `mofsl-flutter/app_benchmark_agent`; developers commit their own results folder
on a branch. The report builder still reads only files named exactly `runs.csv` / `env.csv` and
ignores anything containing "conflict" or "copy", and `state.json` is per developer.

The developer's identity lives in `~/.riise-benchmark/me.json` on their Mac, not in the shared
folder, so a shared folder never carries a half-written identity file.

## 6. Module definitions

A module is a YAML file. It is the only thing that differs between developers' runs.

```yaml
name: fno
title: F&O
rise:
  screen: "Explore > F&O tab"
  list: "F&O movers list"          # what the scroll test scrolls
  detail: "contract detail"        # what L5 opens
  live_ticks: true                 # U1–U3 and C1–C4 apply
  account_sensitive: false         # L9, L10, S6 apply only if true
apps:
  Kite:       {screen: null}                      # N/A: not on the Plan's list for Kite
  Groww:      {screen: "Explore > F&O section"}
  Angel One:  {screen: "F&O tab"}
  INDmoney:   {screen: "F&O tab"}
  Kotak Neo:  {screen: "F&O tab"}
  SAHI:       {screen: "F&O tab"}
  Dhan:       {screen: "F&O tab"}
scroll:
  x: 540            # swipe column, as a fraction of width is safer; builder's call
  y_from: 1800
  y_to: 600
  per_app: {}       # overrides when an app's list sits elsewhere
skip: []            # metric IDs that do not apply to this module
coldstart: true     # optional; false leaves cold start (L1, X4) out of this module (runner asks each session)
offline_items:      # the O1 checklist for this module, each answered Yes/Partial/No per app
  - "Last known prices shown"
  - "Stale-data label"
  - "Error state instead of blank"
data_items:         # the D1 checklist, same scoring
  - "Indices strip"
  - "Most traded"
notes: ""
```

O1 and D1 are computed, not typed: `record.py` stores one row per item (metric id
`O1.<item-slug>`, value Yes/Partial/No) and `build_report.py` derives the percentage. The
per-item answers stay in `runs.csv`, which keeps the traceability the anti-goals require.

Every `runs.csv` row carries `module_version`, a short hash of the YAML's `rise`, `apps`,
`scroll`, `offline_items` and `data_items` blocks. `/benchmark-module` may edit a seeded or
existing YAML; the report then flags rows whose version differs from the current definition,
and the agent warns the developer before resuming on a changed definition.

Metric descriptions in `METRICS.md` and in the generated workbook are templates:
"`{screen}` → `{list}` fully rendered" renders as "F&O tab → F&O movers list fully rendered".
`live_ticks: false` auto-skips U1–U3 and C1–C4. `account_sensitive: false` auto-skips L9, L10,
S6. `skip` adds anything else. Skipped metrics appear in the workbook as N/A, never as 0.

`portfolio.yaml` is written so that the current workbook's wording comes out unchanged. On
`mf`, Coin is a separate row that stands in for Kite; Kite itself is N/A there.

The seeded Explore tab modules carry the Plan's screen mapping (for instance Kite has no
screen tests; INDmoney has Stocks and F&O only; Groww's Explore is one screen compared section
by section). Screens, lists and coordinates are placeholders that the first developer to run
that module confirms through `/benchmark-module`.

## 6b. Metrics added from the Groww Quote-page report

`docs/examples/groww-quote-page-benchmark.md` was produced by another developer for one app and
one screen. Vivek's decision (22 Oct): take **only its seven measurable parameters** into the
catalogue; its qualitative checklist, narrative report template and protocol changes are not
part of this build.

| ID | Category | Metric | Unit | Tool | Runs |
|---|---|---|---|---|---|
| L14 | Loading Time | In-screen tab or sub-section switch, tap to content | ms | scrcpy (manual) | 5 |
| L15 | API / Network | Data per screen open, received + sent, open plus 8 s | KB | `bench.py --group open` (netstats UID delta) | 5 |
| S7 | Scroll & Gesture | Gesture jank on non-list interactions (chart range, scrub, tab swipe) | % janky | `bench.py --group gesture` (Perfetto, module `gestures`) | 5 |
| U4 | Screen Updation | Idle redraw rate: frames per second over 60 s with no input | fps | `bench.py --group idle` (Perfetto) | 3 |
| U5 | Screen Updation | Wasted redraws: share of idle frames identical to the previous one | % | `bench.py --group idle --with-video` (screenrecord + ffmpeg mpdecimate) | 3 |
| R9 | RAM | Leak check: PSS growth over 10 open/close cycles | MB | `bench.py --group leak` (meminfo; scripted with `open_tap` or by hand) | 1 |
| X4 | External SDKs | Start-up lock contention: count and longest `Long monitor contention` | count (longest ms in note) | `bench.py --group coldstart` (logcat), under `_app` | 5 |

RAM rows (R1–R3, R9) also carry the meminfo split (Java heap, native heap, code, graphics,
WebView count) in the note, because that split is where the explanation lives.

## 7. App registry and detection

`apps.json` becomes:

```json
{
  "RISE":        {"package": "com.mosl.mobile",        "ranked": true},
  "RISE UAT":    {"package": "com.mosl.mobile.uat",    "ranked": false},
  "Kite":        {"package": "com.zerodha.kite3",      "ranked": true},
  "Coin":        {"package": "com.zerodha.coin",       "ranked": true, "stands_in_for": "Kite", "modules": ["mf"]},
  "Groww":       {"package": "com.nextbillion.groww",  "ranked": true},
  "Angel One":   {"package": "com.msf.angelmobile",    "ranked": true},
  "INDmoney":    {"package": "in.indwealth",           "ranked": true},
  "Kotak Neo":   {"package": "com.kotak.neo",          "ranked": true},
  "SAHI":        {"package": "com.aaritya.sahi_trade_app", "ranked": true},
  "Dhan":        {"package": "com.dhan.live",          "ranked": true}
}
```

At the start of a run the agent reads `adb shell pm list packages` and `dumpsys package` for
version names. Apps not installed are N/A for that developer. The app's version, the phone
model, Android version and refresh-rate mode go into `env.csv`, so every row is traceable.
"Riise" in the existing CSVs is read as "RISE" by the report builder.

## 8. Result rows

`runs.csv` keeps the existing columns and adds a few:

```
timestamp, module, module_version, developer, app, device_model, device_ram_gb, android,
package, version, metric, run, value, unit, source, artifact, note
```

`source` is `bench.py`, `manual`, or `video` (for Phase 2). `artifact` is the local trace or
recording filename, if any. `device_model` replaces the old Budget/Flagship column. The old
Portfolio CSVs and workbooks are moved to `archive/` and not read by the report builder.

**Run counts.** Five runs for timing, scroll and RAM metrics; three runs of ten minutes for
the live C1–C4 session (scaled to a 15-minute equivalent, as CONTEXT.md records); one run for
storage, SDK and Play Store facts. These expected counts live in `METRICS.md` and drive both
the workbook's five Run columns and the completeness report. When five runs spread more than
20 %, the agent asks for a sixth; it **replaces** the outlier, which moves to `note`, so the
workbook layout never changes.

Each developer writes only inside their own `results/<module>/<developer>_<device>/` folder.
Nothing in the design writes to another developer's folder, which is the whole collision rule
for a git-less shared folder. Report files carry a date, so rebuilding never overwrites someone
else's report.

## 9. Scoring across different phones

Within one module, every app was measured on the same phone by the same developer, so ranks
and the 0–100 category scores from the Portfolio workbook (best = 100, worst = 0, weighted)
are fair.

Across modules the phones differ, so raw values are **not** comparable. The combined scorecard
therefore shows, per module: RISE's rank, RISE's 0–100 score per category, the gap to the best
app in that module's own units, and the phone it was measured on. The headline "RISE overall"
is the average of RISE's per-module ranks and scores, which are unit-free. Raw numbers stay in
the per-module sheets with the device in the header. The Plan's "Build and stack" criterion is
device-independent and is filled once from the installed APKs.

If two developers benchmark the same module on different phones, both appear as separate rows
and the scorecard takes the later one by default, naming the other in a note.

Phone-scoped metrics (`_app`) are scored once per developer/phone in their own block of the
combined scorecard and are not folded into any module's rank. Category weights live in
`weights.yaml` (seeded with the current workbook's values) and are read by `build_report.py`;
the Scorecard sheet shows them read-only with a note saying where to change them. The lead's
sign-off is on that file.

## 10. Harness changes

**`bench.py`**

- New required flags `--module` and `--developer` (defaulting from `me.json`); `--device`
  becomes the detected model.
- The prompts "Open PORTFOLIO… holdings…" come from the module YAML.
- Swipe coordinates come from the module YAML, with per-app override.
- Writes `runs.csv` and `state.json` in the developer's folder; stops writing to any workbook.
- Live session only when `live_ticks: true`; the agent warns outside 09:15–15:30 IST (commodity
  evening session is a module note).
- Keeps the fixes recorded in CONTEXT.md (skin temperature from thermalservice, 10-minute
  live scaling).
- `--results-dir` override, used by the dry run so nothing lands in a real developer folder.

**`preflight.py`** — new. The Plan's checklist as commands: `settings get global
private_dns_mode`, `low_power`, `refresh_rate_mode`, `show_touches`, the three animation
scales, `dumpsys battery` level, `dumpsys wifi` link speed and RSSI. Hard failures (private DNS
fixed hostname, battery below 50 %, more than one device) exit non-zero. Soft findings are
recorded. A speed test value and holdings count are asked for and written to `env.csv`.

**`record.py`** — new. `record.py --module fno L3 --app Groww --run 2 --value 1840 --note "…"`
appends one row and updates `state.json`. The agent calls it for every manual metric.

**`build_report.py`** — new, importing the layout and metric catalogue from
`build_benchmark.py`. `--module fno --developer x` builds that module's workbook with the Run
cells filled from `runs.csv` and the Env sheet from `env.csv`. `--combined` reads every
`results/**/runs.csv` and writes the combined workbook plus `scorecard_<date>.md`. The workbook
stays an output; nobody types into it.

## 11. The agent

`benchmark-runner.md` holds, in this order: the protocol (from PROTOCOL.md), the metric
catalogue summary, the step list of §4, the exact commands it runs, and these rules:

- Never type or store a PIN; the developer types it on the phone, as the Plan requires.
- Never place an order or change holdings; phones are logged into real or client accounts.
- Never write outside the developer's own results folder, except reports (dated) and a new
  module YAML (only if it does not exist yet).
- Record the method with every manual value, so a reviewer can repeat it.
- Rotate app order on each repeat; five runs per metric; flag runs that spread more than 20 %
  and ask for a sixth.
- Stop and tell the developer when a check fails rather than skipping it.
- On `/benchmark-report`, also list modules with fewer than five runs or missing manual
  metrics, so the lead sees what is incomplete.

The three commands are thin: they pass the module name and the mode (run, report, module)
to the agent.

## 12. Phases

**Phase 1 (this build)**: everything in §5 except video automation. Includes archiving the
old Portfolio files, seeding the module YAMLs, README, PROTOCOL, METRICS, `weights.yaml`, the
agent and the three commands. Acceptance: (a) `build_report.py` on a synthetic `runs.csv`
produces a Portfolio workbook whose sheet layout and Summary formulas match the archived one;
(b) `/benchmark portfolio` on Vivek's S23 runs pre-flight, detection, one `bench.py --only
coldstart` app, one manual metric and one O1 item into a `_dryrun` developer folder, then
resumes correctly after an interruption; (c) `/benchmark-report` combines that folder with
nothing else and lists it as incomplete.

**Phase 2 (after the first two modules have run)**: `video_timing.py` from the Plan's method
(scrcpy recording with show-taps, ffmpeg `freezedetect` on a cropped region) to automate L2–L8,
L13 and U3; PCAPdroid CSV import for L11 and X3; the Plan's section-by-section scroll capture
for Explore-style tabs.

## 13. Calls I made (Vivek to check)

- Identity in `~/.riise-benchmark/me.json`, folder named `<developer>_<device-model>`.
- Rank and 0–100 score are the only numbers combined across phones.
- `build_benchmark.py` becomes a library; the workbook is output-only from now on.
- RISE UAT included in `apps.json`, unranked, optional per run.
- Explore tab modules are seeded as skeletons with the Plan's app mapping, not finalised.
- Python 3.11+, `openpyxl`, `perfetto`, `pyyaml`; adb, scrcpy, ffmpeg via Homebrew.
- Added from the Groww report (§6b): seven metrics L14, L15, S7, U4, U5, R9, X4, nothing else.
- Module definitions and weights are JSON, not YAML (no `pyyaml` dependency for developers).
- Added after the builder check: phone-scoped metrics measured once under `_app`; Build and
  stack is an unscored info block; O1/D1 recorded per item from lists in the module YAML;
  run counts 5 / 3×10 min / 1 with a sixth run replacing an outlier; weights in
  `weights.yaml`; traces and recordings local, referenced by filename; sync-conflict files
  ignored; `module_version` hash on every row with a changed-definition warning; Coin as its
  own row on `mf`; the plan table asks whether each app is logged in with data.

## 14. Left to the builder

- Exact YAML schema details and validation messages.
- How `state.json` encodes partial runs and how the resume prompt reads.
- Workbook cell mapping when a module has skipped metrics.
- The scorecard markdown layout, as long as it matches the table shape described in §9.

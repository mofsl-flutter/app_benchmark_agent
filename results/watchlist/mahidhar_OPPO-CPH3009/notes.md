# Watchlist module — measurement notes (mahidhar / OPPO CPH3009)

Module version `150bfb98`. Automated groups `ram,open,scroll` measured 2026-10-22, 5 runs per app,
app order rotated per repeat. Market was closed (after 15:30 IST), so the watchlist showed static
prices for all apps.

## S1–S5 not measurable for Kite, Kotak Neo, SAHI (SurfaceView rendering)

`bench.py` recorded S1–S5 as **empty** for these three apps, with the note "no frames from the
app". Investigated 2026-10-22:

- The apps were on the correct screen — Kite was verified sitting on **Bench 20** with all 20
  symbols loaded when the trace was taken, so this is not a navigation or fling-coordinate fault.
- Their process names match their package names, so `bench.py`'s
  `process.name = <pkg>` filter is correct.
- In their traces, `actual_frame_timeline_slice` contains **zero** rows for the app process; every
  frame is attributed to `/system/bin/surfaceflinger` with a null layer name.
- `dumpsys gfxinfo <pkg>` also reports `Total frames rendered: 0`, confirming they never draw
  through Android's HWUI pipeline.
- All three ship `libflutter.so` and render to a **FlutterSurfaceView**, which bypasses
  ViewRootImpl. RISE is *also* Flutter but composites through
  `VRI-com.mosl.mobile/MainActivity`, so its frames are visible; Groww, Angel One and INDmoney
  are native.

| App | Renderer | S1–S5 |
|---|---|---|
| RISE | Flutter via ViewRootImpl | measured |
| Groww, Angel One, INDmoney | native | measured |
| Kite, Kotak Neo, SAHI | Flutter via SurfaceView | **N/A — not measurable** |

**Decision:** report S1–S5 for the four measurable apps and mark the other three N/A with this
cause. A SurfaceFlinger-level fallback was tested and does produce frames for all seven, but it is
not comparable with the app-level figures — on the same RISE fling it reads 2.68 % jank / p50
12.0 ms versus 1.30 % / 6.7 ms app-side — so mixing the two sources across apps would bias the
ranking. Switching every app to the display-level source would need a change to the shared
`bench.py` and would break comparison with modules other developers have already measured; raise
with the team rather than doing it in this module.

**Read S1–S5 as a four-app comparison, not a seven-app one.**

## Spread-check outcomes

Accepted without redo, because the variability is a property of the metric rather than a bad run:

- **L15 (data per screen open)** — fails on all 7 apps (spread 0.32–7.09). Network byte counts
  vary with caching, token refresh and background sync. Run 1 is the highest reading in 5 of 7
  apps, consistent with a cold cache on first open. Use the median and treat L15 as indicative.
- **S1 (janky frames)** — fails on all 4 measurable apps, but the absolute values are 0.2–2.3 %.
  A 20 % relative threshold is meaningless this close to zero; every app scrolls cleanly.

Redone (genuine single-run outliers): R2 Angel One run 4 (0.413 → 0.188), scroll INDmoney run 5
(S3 0.473 → 0.115), scroll Groww run 1 (S3 0.320 → 0.041, S4 0.284 → 0.116).

**RISE R2 is bimodal — accepted, not redone.** Runs read 340.9, 433.3, 443.1, 354.5, 361.2 MB:
two runs cluster near 438 MB and three near 352 MB, an ~85 MB gap with nothing between. Run 3 was
redone and returned 443.1 MB, essentially unchanged from the 444.3 MB it replaced, so the high
readings are reproducible rather than noise. Spread stays at 0.283. Replacing a single run would
leave the other high run in place and misstate the app. Worth investigating separately: RISE's
watchlist appears to settle into one of two memory states on load.

## Deferred — needs market hours

The module sets `live_ticks: true`, so the `idle` (U4, U5) and `live` (C1–C4) groups require a
weekday 09:15–15:30 IST session. Not measured on 2026-10-22; RISE has a single U4/U5 run from an
earlier session.

## X3 (third-party domains on Bench 20) — method

Measured 2026-10-22 evening (market closed), one 60 s PCAPdroid capture per app:

- The app was already open on Bench 20; the capture (filtered to the app) was started and confirmed
  running (VPN up) before the app was brought to the front, then left untouched for 60 s.
- Domains were read from PCAPdroid's Connections list (UI tree) with their first-seen time; a domain
  counts only if first seen inside the 60 s window. Some stops were delayed by PCAPdroid's
  "control request" consent prompt (allowed by the developer); the time filter keeps every app at 60 s.
- Counted: unique hostnames not owned by the app's company. Not counted: the company's own domains,
  generic cloud hosting (amazonaws.com, cloudfront.net) and bare IP addresses with no hostname.
- Connections already open before the capture are not seen, so X3 reflects what the screen contacts
  while open, not what the app contacts at launch. A first RISE pass that included launch and
  navigation saw ~17 third-party domains (also Datadog, NotifyVisitors, ipinfo.io, Value Research);
  it was discarded for consistency.

| App | X3 | Third-party companies in the 60 s |
|---|---|---|
| RISE | 9 | Plotline, VWO, Google Firebase, CleverTap, MoEngage, Protectt.ai, AppsFlyer |
| Angel One | 5 | CleverTap, AppsFlyer, Google Firebase |
| INDmoney | 4 | Google (Firebase, time.google.com), Mixpanel |
| Kotak Neo | 4 | CleverTap, Protectt.ai, Mixpanel, Google (Dynatrace at +3 s) |
| Groww | 3 | AppsFlyer, Google Firebase |
| Kite | 2 | Google Firebase |
| SAHI | 1 | AppsFlyer (MoEngage at +1 s, New Relic at +4 s) |

## D1 (data pointers / features) — method

Checked 2026-10-22 evening on Bench 20 in each app: the rows as shown, a tap on a stock name, a
long-press on a row (RISE), the stock page header/menu, and the app's theme setting. Buy/Sell,
order, 1-Tap and alert-submit controls were never tapped.

Rules used for every app: **Yes** = available on the watchlist itself (row or a sheet over the
list); **Partial** = one step away on the stock page; **No** = not found on the row, sheet or
stock page. Dark mode = the app has a dark theme (followed system dark mode, or an in-app switch).

Scores (Yes 1, Partial 0.5, No 0): Groww 94.4, Kite 88.9, Angel One 83.3, Kotak Neo 83.3,
SAHI 77.8, **RISE 72.2**, INDmoney 72.2.

RISE has no sparkline and puts depth, alerts and Buy/Sell on the quote page rather than in a sheet
over the watchlist; it is the only app that shows holdings qty and unrealised P&L on watchlist rows.

## R3 (RAM after 5 min) and R9 (leak check) — results

One run per app, 2026-10-22 evening (market closed, static prices), `bench.py --group ram --with-r3`
and `--group leak` (10 open/close cycles of Bench 20).

| App | R3 RAM after 5 min (MB) | R9 PSS growth over 10 cycles (MB) |
|---|---|---|
| **RISE** | **380.5** (highest) | **+60.0** (highest) |
| INDmoney | 324.3 | +7.6 |
| SAHI | 280.5 | +11.8 |
| Groww | 260.9 | −0.1 |
| Kotak Neo | 245.1 | +7.0 |
| Angel One | 244.1 | +9.3 |
| Kite | 206.3 | +19.9 |

**RISE grows 60 MB over 10 opens of its watchlist, 3× the next app (Kite, +19.9) and 6–8× the
rest.** Together with the bimodal R2 (~352 vs ~438 MB on load), this points to watchlist memory
not being released when the screen is closed — worth profiling by the RISE team. Market was
closed, so live-tick load was absent; growth may be larger during market hours.

## S7 (gesture jank: watchlist tab switching) — method and results

Measured 2026-10-22 evening. Gesture = switch from Bench 20 to the neighbouring list tab and back,
3 times (6 taps, 1.5 s apart), under a Perfetto FrameTimeline trace, 5 runs per app. Run with
`bench.gesture_test()` directly (same trace, jank rule and fraction-only gestures as
`bench.py --group gesture`); the gestures are kept **out of `modules/watchlist.json`** so the module
version (150bfb98) of the 270 rows already recorded does not change. Traces are in
`~/.riise-benchmark/artifacts/watchlist/*_S7_*.pftrace`.

Tab rows in Groww and RISE re-centre on the selected tab, so the tap positions were learned by
label first and replayed as a fixed cycle that returns to the same layout (checked before every
run); INDmoney's chip row drifts ~4 px per tap, so it was swiped back to its start before each run.

| App | Gestures (fractions of 1080×2354) | Runs (janky %) | Median |
|---|---|---|---|
| **RISE** | margin 0.217,0.324 ↔ Bench 20 0.718,0.324 | 1.91, 1.20, 1.62, 2.02, 0.56 | **1.62** |
| Angel One | mywatchlist 0.339,0.240 ↔ Bench 20 0.593,0.240 | 6.54, 5.71, 5.75, 5.81, 6.82 | 5.81 |
| INDmoney | Watchlist 1 0.541,0.261 ↔ Bench 20 0.794,0.261 | 8.71, 7.37, 7.61, 7.51, 7.98 | 7.61 |
| Groww | My Watchlist 0.234,0.219 ↔ Bench 20 0.855,0.219 | 10.27, 9.63, 9.04, 12.43, 10.22 | 10.22 |
| Kite, Kotak Neo, SAHI | — | N/A: SurfaceView rendering, same cause as S1–S5 | — |

Spread check: Angel One runs 1 and 5 redone (7.51 → 6.54, 4.55 → 6.82); Groww run 4 redone
(14.44 → 12.43) and still high, so Groww's spread (0.33) is accepted as real variability; RISE's
relative spread is large but all values are 0.6–2 %, where a 20 % relative rule is not meaningful.

**RISE switches watchlist tabs the most smoothly of the four measurable apps (1.6 % janky frames vs
5.8–10.2 %).**

## S5 (FPS) depends on the refresh rate ColorOS gave each app — read with care

Checked 2026-10-23 from the saved scroll traces (SurfaceFlinger display-frame interval, median per
trace). The phone's 120 Hz setting is a cap; ColorOS chose a different rate per app:

| App | Display refresh during scroll | S5 median FPS | FPS ÷ refresh |
|---|---|---|---|
| **RISE** | **120 Hz** (all 5 traces) | **75.3** | **63 %** |
| INDmoney | 120–121 Hz | 120.3 | ~100 % |
| Groww | 90 Hz | 90.1 | ~100 % |
| Angel One | 90 Hz | 87.9 | 98 % |

Raw S5 makes INDmoney look best and RISE worst, but Groww and Angel One were capped at 90 Hz by the
OS, so their FPS cannot exceed 90. Normalised to the refresh rate actually granted, Groww, Angel
One and INDmoney deliver essentially every frame, while **RISE delivers only ~63 % of the frames the
120 Hz display offered** — RISE is the one app not keeping up with the display while scrolling,
even though its S1 (janky frames) is low. Raw S5 is kept as recorded; the scorecard rank on S5 should
be read alongside this table. The per-app refresh policy is a ColorOS behaviour, not something the
apps control.

## C1–C4 live-session length (developer decision, 2026-10-23)

Round 1 (run 1) of the live session ran **10 min** per app (PROTOCOL allows 10, scaled to 15).
Rounds 2 and 3 (runs 2–3) run **2 min** per app (changed from a planned 3 min before round 2 started), the same for every app, to fit all three rounds into
one market session. Consequences:

- **C1 (CPU %)**: an average over the session; comparable across 2 and 10 min.
- **C2 (battery mAh) and C4 (data MB)**: scaled to a 15-min equivalent (×1.5 for 10 min, ×7.5 for
  2 min), so runs 2–3 carry 5× the relative noise of run 1. Indicative.
- **C3 (temperature rise)**: not scaled, and 2 min is too short to warm the phone, so runs 2–3 read
  near zero. **Use the run-1 (10-min) C3 value**; the 3-run median of C3 understates it.

All apps get the same 10 + 2 + 2 mix, so the comparison between apps stays like-for-like.

## U4/U5 idle and C1–C4 live session — results (2026-10-23 market hours)

Three runs per app on Bench 20 (run 1 = 10-min session, runs 2–3 = 2 min; app order rotated per round;
phone unplugged, 88 % → , pre-flight OK). Median of 3 (C3: use run 1, see the section above).

| App | U4 idle fps | U5 wasted redraws | C1 CPU | C2 mAh/15 min | C3 °C (run 1) | C4 MB/15 min |
|---|---|---|---|---|---|---|
| **RISE** | **39.6** | 49.5 % | **185.5 %** (110.5, 185.5, 188.7) | 76.5 | −0.7 | 2.43 |
| Groww | 90.2 | 92.6 % | 155.4 % | 79.65 | +0.1 | 2.86 |
| SAHI | N/A | 92.9 % | 133.7 % | 66.68 | −0.1 | 6.82 |
| Angel One | 33.4 | 28.9 % | 67.9 % | 74.18 | −1.1 | 3.10 |
| INDmoney | 5.5 | 56.9 % | 41.8 % | 62.77 | −0.5 | 4.13 |
| Kotak Neo | N/A | 24.7 % | 26.0 % | 62.4 | −0.2 | 2.19 |
| Kite | N/A | 1.6 % | 22.4 % | 70.88 | −1.3 | 0.79 |

U4 is N/A for Kite, Kotak Neo and SAHI (SurfaceView: no app-level frames, as for S1–S5); U5 comes from
a screen recording and is measured for all seven.

**RISE uses the most CPU of all seven apps while simply showing the watchlist: median 185 % (almost two
full cores), 8× Kite (22 %), and rising from 110 % in the first session to ~187 % in the next two.**
RISE also redraws ~40 times a second with no input, about half of those frames identical to the previous
one (INDmoney: 5.5 fps). Groww and SAHI redraw almost every idle frame needlessly (U5 ≈ 93 %).

**C2 caveat:** battery estimates sit in a narrow 62–80 mAh band although CPU differs 8×; the per-UID
batterystats estimate appears dominated by screen power attributed to the foreground app. Treat C2 as
not discriminating between apps until checked.

## U1 (LTP updates per minute) — method and run count (developer decision, 2026-10-23)

U1 = changes of RELIANCE's last traded price on Bench 20 per minute, from a 2-min `screenrecord`
of the watchlist with RELIANCE visible: the price box is cropped, sampled at 10 fps, and a change is
counted when >25 pixels differ strongly from the previous sample (debounced 0.3 s). Spot-checked on
Kite: every counted change was a new price value. Videos are in
`~/.riise-benchmark/artifacts/watchlist/*_U1_run1.mp4`.

**One run per app** (PROTOCOL asks for 5) — developer decision to fit the market session. Each app is
measured at a different time of day, so tick-rate differences partly reflect market activity at
that moment; read U1 as indicative. RISE blocks screen recording (FLAG_SECURE); its U1/U3 need a
second phone filming the screen.

U1 results (2026-10-23, 12:45–13:13, one 2-min run per app; Kite has 2): INDmoney 42.9/min, SAHI 39.5,
Kite 31.9 / 38.5, Kotak Neo 33.5, Angel One 32.0 (a first attempt read the wrong row after the list
auto-scrolled and was replaced), Groww 22.0 (fewest — appears to batch/throttle updates). Every run's
first and last cropped frame was checked to show RELIANCE's price; INDmoney and Kite were spot-checked
change by change (each counted change was a new price). RISE (filmed with the MacBook camera, 13:38, values read by eye every 0.5 s): **17.0/min, the lowest** — a minimum count; its changes land almost exactly on whole seconds, suggesting a ~1 s UI refresh rather than per-tick updates.

## U3 (live updates resume after 1 min in background) — method and results (2026-10-23)

One run per app (developer decision, as U1). App on Bench 20 with RELIANCE visible → Home key →
60 s → relaunch from the launcher while `screenrecord` runs → time from relaunch to the first change of
RELIANCE's price box (20 fps). The "app is back" frame is checked against a reference crop taken before
going to the background; the back/tick frames were checked by eye for every app. Includes the wait for
the next market tick (U1 shows ~1.5–3 s between ticks), so differences under ~1 s are not meaningful.

| App | First tick after return |
|---|---|
| Angel One | 0.55 s |
| INDmoney | 0.80 s |
| SAHI | 1.25 s |
| Groww | 2.05 s |
| Kotak Neo | 2.05 s (price visible again at 1.20 s) |
| Kite | 3.40 s (price visible again at 0.85 s) |
| RISE | 1.0 s **after reappearing** (MacBook camera; reappears with stale prices; relaunch-to-visible ~2–3 s, not exactly timeable) |

## Wi-Fi network check (2026-10-23)

After airplane-mode cycles the phone sometimes auto-joins a second saved network, "MAHI BCM STAIRS",
instead of the test network "Mahi_work" (this is also why wireless adb dropped: Android asks
"Allow wireless debugging on this network?"). The phone's Wi-Fi connection history shows Mahi_work for
every connection from 08:43 to 13:43, so all idle/live (U4/U5, C1–C4), U1 and U3 measurements ran on
Mahi_work; the only switches were 13:43:27–13:43:49 and 13:44:26–13:44:34, during the O1
auto-refresh check (network-independent). Before further airplane-mode tests, turn off auto-connect for
"MAHI BCM STAIRS" (or forget it) so the phone stays on Mahi_work.

## O1 (offline) — method and results (2026-10-23)

Each app on Bench 20; a script **on the phone** toggled airplane mode (so the run continued while
wireless adb was down): Part A = 30 s offline then 30 s back online, screenshots at 0/3/10/30 s and
5/15/30 s; Part B = force-stop, airplane on, cold launch (developer unlocks), screenshots, tap the first
row only if the watchlist is on screen, airplane off. Apps that cold-start on another tab got an extra
offline run that tapped Watchlist → Bench 20 → first row. RISE (screenshots blocked) was judged from its
UI-tree text at each step plus a MacBook-camera video of the phone screen. All runs in market hours
(08:42–14:52, auto-refresh judged on moving prices). No Back key was used after Kite showed a logout
prompt on Back from its offline login screen (nothing was confirmed).

| App | Score | Offline start shows cached list | Data stays when network drops | Clear offline message | Auto-refresh on reconnect | Notes |
|---|---|---|---|---|---|---|
| Groww | 61.1 | No ("Oops! Something went wrong", stays until TRY AGAIN) | Yes | Yes ("Low internet" banner) | Yes | |
| Angel One | 61.1 | **Yes** (only app) | Yes | No | Yes | stock sheet offline: cached price, depth spinner (Partial) |
| INDmoney | 61.1 | No (server-error dialog, blank list; stays until Ok) | Yes | Yes ("No internet connection!" bar) | Yes | |
| Kotak Neo | 55.6 | No (full-screen no-internet page) | **No** (list replaced after ~3 s) | Yes | Yes | hides prices offline |
| SAHI | 55.6 | No (stuck on splash) | **No** (list replaced at once) | Yes | Yes | hides prices offline |
| **RISE** | **44.4** | No (mPIN screen + "Oops, something went wrong!") | Yes | **No** | Yes | stale prices look live |
| Kite | 44.4 | No (own login screen) | Yes | **No** | Yes | stale prices look live |

**RISE ties for last on offline handling:** it keeps prices on screen when the network drops but gives
no sign that they are stale (no banner, no timestamp), and an offline start lands on the mPIN screen
with a generic "Oops, something went wrong!" instead of a cached watchlist. Only Angel One opens a
cached watchlist offline; no app shows a "last updated" time.

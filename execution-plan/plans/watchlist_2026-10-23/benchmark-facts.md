# Benchmark facts: RISE watchlist (Bench 20), OPPO CPH3009

Sources (all values copied, not estimated):

- `reports/watchlist/watchlist_mahidhar_OPPO-CPH3009_2026-10-23.xlsx` (data tabs; the Summary and Scorecard tabs hold formulas that openpyxl reads as empty, so medians were taken from the run columns)
- `results/watchlist/mahidhar_OPPO-CPH3009/notes.md`
- `results/_app/mahidhar_OPPO-CPH3009/notes.md`
- `results/watchlist/mahidhar_OPPO-CPH3009/creation_summary.md`

Device: OPPO CPH3009 (OPPO K14 Plus 5G), Android 17, 120 Hz setting (ColorOS picks the rate per app), 2.4 GHz Wi-Fi.
App: RISE 6.2.09 (`com.mosl.mobile`). Module version `150bfb98`. Automated groups measured 2026-10-22 (market closed);
idle/live/U1/U3/O1 measured 2026-10-23 in market hours.

"Best other" is for my own reasoning only and does not go into plan files.

## Loading / open time

| ID | Metric | RISE | Unit | Best other | RISE rank | Notes |
|---|---|---|---|---|---|---|
| L1 | Cold start (OS launch time) | 710 (runs 842, 750, 678, 710, 654) | ms | 512 | 5 of 7 | run-1 penalty +19 %, accepted |
| L2–L14 | PIN to home, screen open timings | not measured | | | | Loading Time category not measured yet |
| L15 | Data per Watchlist > Bench 20 open (+8 s) | 75.7 (115.1, 75.7, 71.6, 71.7, 94.5) | KB | 5.7 | 4 of 7 | indicative, spread fails on all apps |

## Tab or segment switch

| ID | Metric | RISE | Unit | Best other | Rank | Notes |
|---|---|---|---|---|---|---|
| S7 | Gesture jank, Bench 20 <-> neighbour list tab x3 | 1.62 (1.91, 1.2, 1.62, 2.02, 0.56) | % janky | 1.62 | 1 of 4 measurable | RISE is smoothest here. Not a weak factor. |

## Scroll FPS and janky frames (4 measurable apps)

| ID | Metric | RISE | Unit | Best other | Rank |
|---|---|---|---|---|---|
| S1 | Janky frames while scrolling | 0.34 | % | 0.21 | 2 of 4 |
| S2 | Frame duration p50 | 6.3 | ms | 5.3 | 2 of 4 |
| S3 | Frame duration p90 | 9.7 | ms | 8.6 | 2 of 4 |
| S4 | Frame duration p99 | 15 | ms | 15 (RISE best) | 1 of 4 |
| S5 | Average FPS while scrolling | 75.3 (74.4, 76.7, 74.6, 75.3, 76.1) | fps | 120.3 | 4 of 4 |

Notes: RISE ran at 120 Hz in all 5 traces; 75.3 fps is ~63 % of the frames the display offered, while the
other measurable apps delivered ~98–100 % of their granted rate. RISE renders through
`VRI-com.mosl.mobile/MainActivity` (ViewRootImpl), not a SurfaceView. Kite, Kotak Neo and SAHI are N/A.

## Gesture / chart smoothness

Only S7 (above). No chart metric in this module.

## Idle redraw, CPU and network (market hours, 3 runs)

| ID | Metric | RISE | Unit | Best other | Rank | Notes |
|---|---|---|---|---|---|---|
| U4 | Idle redraw, 60 s no input | 39.6 (39.1, 41.7, 39.6) | fps | 5.5 | 3 of 4 measurable | |
| U5 | Idle frames identical to previous | 49.5 (63.7, 49.5, 48.5) | % | 1.6 | 4 of 7 | |
| C1 | Average CPU on Bench 20, live | 185.5 (110.5, 185.5, 188.7) | % of one core | 22.4 | 7 of 7 | 8x the lowest; rises from session 1 to 2–3 |
| C2 | Battery, 15-min equivalent | 76.5 | mAh | 62.4 | 6 of 7 | not discriminating (62–80 band), do not plan on it |
| C3 | Temperature rise (run 1) | −0.7 | °C | | | 2-min runs too short |
| C4 | Data, 15-min equivalent | 2.43 | MB | 0.79 | 3 of 7 | indicative |
| U1 | LTP changes/min, RELIANCE | 17.0 | /min | 42.9 | 7 of 7 | one run, MacBook camera, minimum count; changes land on whole seconds |
| U3 | Live updates resume after 1 min in background | 1000 | ms | 550 | 3 of 7 | one run; RISE reappears with stale prices; relaunch-to-visible ~2–3 s, not exactly timeable |

## Data per open

L15 above (75.7 KB). X3 third-party domains in 60 s on the screen: 9 (Plotline, VWO, Google Firebase,
CleverTap, MoEngage, Protectt.ai, AppsFlyer); best other 1; rank 7 of 7. Exodus trackers 5, permissions 34.

## RAM, leaks and storage

| ID | Metric | RISE | Unit | Best other | Rank | Notes |
|---|---|---|---|---|---|---|
| R1 | PSS after cold start | 432.9 | MB | 211.1 | 7 of 7 | webviews=1 in every run |
| R2 | PSS on Bench 20 | 361.2 (340.9, 433.3, 443.1, 354.5, 361.2) | MB | 218.1 | 7 of 7 | bimodal ~352 / ~438; Java heap ~25 MB in low runs vs ~94–102 MB in high runs |
| R3 | PSS after 5 min on Bench 20 | 380.5 | MB | 206.3 | 7 of 7 | one run, market closed |
| R9 | PSS growth over 10 open/close cycles | +60.0 (418.0 -> 478.0) | MB | −0.1 | 7 of 7 | one run, manual, market closed |
| R4 | Installed size | 207 | MB | 43.1 | | |
| R6 | User data | 14.1 | MB | | | |
| R7 | Cache | 9.4 | MB | | | |
| A4 (proxy) | Installed APK size | 123.6 | MB | 17.3 | 7 of 7 | |

## Chart

No chart on the watchlist. D1 notes: no sparkline.

## Offline and reconnect (O1 = 44.4, joint last)

| Item | RISE |
|---|---|
| OF1 offline cold launch shows cached list | No: mPIN screen with "Oops, something went wrong! Please try again later." |
| OF2 last-updated / stale marker | No |
| OF3 data stays when network drops | Yes (prices visible 30 s) |
| OF4 clear offline message | No, only the system airplane icon |
| OF5 auto-refresh on reconnect | Yes, ~7 s after reconnect |
| OF6 no forced re-login after reconnect | Yes |
| OF7 quote page offline | No |
| OF8 cached values clearly not live | No |
| OF9 no crash/ANR | Yes |

## Stability

0 crashes, 0 ANRs during testing. No stability weakness measured.

## Features (D1 = 72.2, joint last)

DP2 sparkline No; DP3 depth from watchlist Partial; DP7 alerts from watchlist Partial; DP8 quick buy/sell
Partial (swipe exists, no sheet). RISE is the only app showing holdings qty and unrealised P&L on rows.

## Creation flow (creation_summary.md)

- Name field prefilled "WatchList 9", must be cleared before typing.
- No visible confirmation when a stock is added.
- List-menu (kebab) icon and per-result add icon have no accessibility label.
- Release build logcat: client code and CleverTap `add_to_watchlist` event, doubled API URL
  `https://tradingapi.mofsl.nethttps://tradingapi.mofsl.net/...`, "API Failed" on a 200 response,
  repeated orientation events.
- Add API `POST Watchlist/Scrip` 200 in ~106 ms.

## UX observations from the developer brief

- Header banner rotation ("MO Wealth" <-> "External Wealth") shifts the list layout.

## Weakest factors (drive the plan)

1. Idle CPU and redraw: C1 185.5 % (last), U4 39.6 fps, U5 49.5 %.
2. Memory: R9 +60 MB (last), R3 380.5 MB (last), R2 bimodal, R1 432.9 MB (last).
3. Scroll frame delivery: S5 75.3 fps at 120 Hz (last of 4; ~63 % of offered frames).
4. Offline: O1 44.4 (joint last), stale prices look live.
5. Live data cadence and resume: U1 17/min (last), U3 stale on return.
6. Features: D1 72.2 (joint last).
7. Third-party SDKs: X3 9 (last).
8. Release logging and small UX gaps (creation flow, accessibility).

Not weak: S7 tab switch (best), S1–S4 (near best), stability (0 crashes).
Not measured: Loading time L2–L14, R5, A4 Play Store size (proxy only).

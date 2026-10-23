# Metric catalogue

Generated from `benchlib.py` by `python3 build_report.py --metrics-md`; do not edit by hand.
Placeholders `{screen}`, `{list}` and `{detail}` are filled from each module's definition. **Phone** = measured once per developer and phone under module `_app`. **Applies** = only when the module sets that flag.

| ID | Category | Metric | Unit | Better | Runs | Tool | Scope |
|---|---|---|---|---|---|---|---|
| L1 | Loading Time | Cold start (OS-reported launch time) | ms | Lower | 5 | ADB (bench.py) | phone |
| L2 | Loading Time | PIN/biometric submit → home fully rendered | ms | Lower | 5 | scrcpy | phone |
| L3 | Loading Time | {screen} → {list} fully rendered (first open, Medium account) | ms | Lower | 5 | scrcpy | module |
| L4 | Loading Time | {screen} re-open (second visit in same session) | ms | Lower | 5 | scrcpy | module |
| L5 | Loading Time | {detail} open | ms | Lower | 5 | scrcpy | module |
| L6 | Loading Time | Pull-to-refresh complete on {screen} | ms | Lower | 5 | scrcpy | module |
| L7 | Loading Time | Warm resume after 30 s in background (on {screen}) | ms | Lower | 5 | scrcpy | module |
| L8 | Loading Time | Resume after 5 min in background (on {screen}) | ms | Lower | 5 | scrcpy | module |
| L9 | User-wise | {screen} load – Small account | ms | Lower | 5 | scrcpy | if account_sensitive |
| L10 | User-wise | {screen} load – Large account | ms | Lower | 5 | scrcpy | if account_sensitive |
| L11 | API / Network | Network connections during {screen} load | count | Lower | 5 | PCAPdroid | module |
| L12 | API / Network | {screen} load on throttled network (~1 Mbps) | ms | Lower | 5 | Developer options | module |
| L13 | Offline | Recovery after reconnect → fresh data shown on {screen} | ms | Lower | 5 | scrcpy | module |
| L14 | Loading Time | In-screen tab / sub-section switch on {screen}, tap to content | ms | Lower | 5 | scrcpy | module |
| L15 | API / Network | Data per {screen} open (received + sent, open + 8 s) | KB | Lower | 5 | ADB netstats (bench.py) | module |
| L16 | Loading Time | {detail2} open from {screen} | ms | Lower | 5 | timing.py | if detail2 |
| S1 | Scroll & Gesture | Janky frames while scrolling {list} (Medium account) | % | Lower | 5 | Perfetto (bench.py) | module |
| S2 | Scroll & Gesture | Frame duration – 50th percentile | ms | Lower | 5 | Perfetto (bench.py) | module |
| S3 | Scroll & Gesture | Frame duration – 90th percentile | ms | Lower | 5 | Perfetto (bench.py) | module |
| S4 | Scroll & Gesture | Frame duration – 99th percentile | ms | Lower | 5 | Perfetto (bench.py) | module |
| S5 | Scroll & Gesture | Average FPS while scrolling {list} | fps | Higher | 5 | Perfetto (bench.py) | module |
| S6 | User-wise | Janky frames – Large account | % | Lower | 5 | Perfetto (bench.py) | if account_sensitive |
| S7 | Scroll & Gesture | Gesture jank on non-list interactions of {screen} (chart range, scrub, tab swipe) | % | Lower | 5 | Perfetto (bench.py) | module |
| U1 | Screen Updation | LTP updates per minute on {screen} (same symbol, market hours) | /min | Higher | 5 | scrcpy | if live_ticks |
| U2 | Screen Updation | Tick lag vs reference feed | ms | Lower | 5 | Camera / scrcpy | if live_ticks |
| U3 | Screen Updation | Live updates resume after 1 min in background | ms | Lower | 5 | scrcpy | if live_ticks |
| U4 | Screen Updation | Idle redraw rate on {screen} (frames per second, 60 s, no input) | fps | Lower | 3 | Perfetto (bench.py) | if live_ticks |
| U5 | Screen Updation | Wasted redraws on {screen}: idle frames identical to the previous frame | % | Lower | 3 | screenrecord + ffmpeg (bench.py) | if live_ticks |
| O1 | Offline | Offline caching score | % | Higher | 1 | Manual (record.py --item) | module |
| D1 | Data Pointers | Data pointer / feature coverage | % | Higher | 1 | Manual (record.py --item) | module |
| X1 | External SDKs | Trackers detected (Exodus) | count | Lower | 1 | Exodus Privacy | phone |
| X2 | External SDKs | Permissions requested (Exodus) | count | Lower | 1 | Exodus Privacy | phone |
| X3 | External SDKs | Third-party domains contacted on {screen} | count | Lower | 1 | PCAPdroid | module |
| X4 | External SDKs | Start-up lock contention: 'Long monitor contention' events before home | count | Lower | 5 | ADB logcat (bench.py) | phone |
| R1 | RAM | RAM (Total PSS) after cold start | MB | Lower | 5 | ADB meminfo (bench.py) | phone |
| R2 | RAM | RAM (Total PSS) on {screen} | MB | Lower | 5 | ADB meminfo (bench.py) | module |
| R3 | RAM | RAM (Total PSS) after 5 min on {screen} | MB | Lower | 1 | ADB meminfo (bench.py --group ram --with-r3) | module |
| R4 | Storage | App size (installed) | MB | Lower | 1 | Settings / ADB diskstats | phone |
| R5 | Storage | User data – fresh install (before login) | MB | Lower | 1 | Settings | phone |
| R6 | Storage | User data – after login + first screen open | MB | Lower | 1 | Settings | phone |
| R7 | Storage | Cache – after login + first screen open | MB | Lower | 1 | Settings | phone |
| R8 | Storage | Total storage after 1 day of use | MB | Lower | 1 | Settings | phone |
| R9 | RAM | Leak check: PSS growth over 10 open/close cycles of {screen} | MB | Lower | 1 | ADB meminfo (bench.py) | module |
| C1 | CPU / Battery / Data | Average CPU on {screen} (live ticks, 15 min equivalent) | % | Lower | 3 | ADB (bench.py --group live) | if live_ticks |
| C2 | CPU / Battery / Data | Battery drain – 15 min on {screen} | mAh | Lower | 3 | ADB (bench.py --group live) | if live_ticks |
| C3 | CPU / Battery / Data | Device temperature rise – session on {screen} | °C | Lower | 3 | ADB (bench.py --group live) | if live_ticks |
| C4 | CPU / Battery / Data | Data used – 15 min on {screen} | MB | Lower | 3 | ADB (bench.py --group live) | if live_ticks |
| A1 | Stability | Crashes during all testing | count | Lower | 1 | ADB logcat | module |
| A2 | Stability | ANRs during all testing | count | Lower | 1 | ADB logcat | module |
| A3 | Stability | Play Store rating | ★ | Higher | 1 | Play Store | phone |
| A4 | Stability | Play Store download size | MB | Lower | 1 | Play Store | phone |

## How to measure

### L1 — Cold start (OS-reported launch time)

*Loading Time · ms · Lower is better · 5 run(s) · automated by bench.py*

adb shell am force-stop <pkg>, then adb shell am start -W -n <pkg>/<activity> and read TotalTime. bench.py --group coldstart does this.

### L2 — PIN/biometric submit → home fully rendered

*Loading Time · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

Record with scrcpy --record. Count frames from the PIN-submit frame to the frame where home stops changing, then divide by the recording fps.

### L3 — {screen} → {list} fully rendered (first open, Medium account)

*Loading Time · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

Same frame-count method. 'Fully rendered' means every value in {list} is visible with no loader or shimmer.

### L4 — {screen} re-open (second visit in same session)

*Loading Time · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

Leave {screen} for another tab, come back, and measure until fully rendered. Shows in-memory caching.

### L5 — {detail} open

*Loading Time · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

Tap the first item in {list} and measure until {detail} is fully rendered.

### L6 — Pull-to-refresh complete on {screen}

*Loading Time · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

Measure from release of the pull gesture until the refresh indicator disappears and values update.

### L7 — Warm resume after 30 s in background (on {screen})

*Loading Time · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

On {screen}, press Home, wait 30 s, reopen from Recents. Measure until {screen} is interactive with fresh data. Note if it asks for the PIN again.

### L8 — Resume after 5 min in background (on {screen})

*Loading Time · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

Same as L7 with a 5-minute wait. Note if it asks for the PIN again or reloads fully.

### L9 — {screen} load – Small account

*User-wise · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

L3 method on the Small test account.

### L10 — {screen} load – Large account

*User-wise · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

L3 method on the Large test account.

### L11 — Network connections during {screen} load

*API / Network · count · Lower is better · 5 run(s) · manual, recorded with record.py*

In PCAPdroid, filter to the app and start capture. Open {screen} cold and count the connections opened in the first 10 s.

### L12 — {screen} load on throttled network (~1 Mbps)

*API / Network · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

Phone: Developer options → Network download rate limit = 1 Mbps (note the value in env.csv). L3 method.

### L13 — Recovery after reconnect → fresh data shown on {screen}

*Offline · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

On {screen}, turn airplane mode on for 30 s, then off. Measure from Wi-Fi reconnect (status bar icon) to updated values.

### L14 — In-screen tab / sub-section switch on {screen}, tap to content

*Loading Time · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

On {screen}, tap a sibling tab or sub-section (e.g. Overview → Technicals). Frame-count from the tap to the new content fully drawn. Note which tab in the note.

### L15 — Data per {screen} open (received + sent, open + 8 s)

*API / Network · KB · Lower is better · 5 run(s) · automated by bench.py*

bench.py --group open: the app's UID byte counter from dumpsys netstats before the tap that opens {screen} and 8 s after it is loaded.

### L16 — {detail2} open from {screen}

*Loading Time · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

On {screen}, tap the entry for {detail2} and measure until it is fully drawn (timing.py --tests L16). Open and go Back only; submit nothing.

### S1 — Janky frames while scrolling {list} (Medium account)

*Scroll & Gesture · % · Lower is better · 5 run(s) · automated by bench.py*

bench.py --group scroll records a Perfetto FrameTimeline trace during 10 identical scripted flings on {list}. Janky = frames with a jank type other than None / Buffer Stuffing. Same for Native and Flutter apps.

### S2 — Frame duration – 50th percentile

*Scroll & Gesture · ms · Lower is better · 5 run(s) · automated by bench.py*

Same trace: time from the app starting a frame to that frame being on screen.

### S3 — Frame duration – 90th percentile

*Scroll & Gesture · ms · Lower is better · 5 run(s) · automated by bench.py*

Same trace, 90th percentile.

### S4 — Frame duration – 99th percentile

*Scroll & Gesture · ms · Lower is better · 5 run(s) · automated by bench.py*

Same trace, 99th percentile.

### S5 — Average FPS while scrolling {list}

*Scroll & Gesture · fps · Higher is better · 5 run(s) · automated by bench.py*

Same trace: 1000 ÷ average gap between frames, ignoring idle gaps over 100 ms. Capped by the display refresh rate (recorded in env.csv).

### S6 — Janky frames – Large account

*User-wise · % · Lower is better · 5 run(s) · manual, recorded with record.py*

S1 method with the Large account logged in.

### S7 — Gesture jank on non-list interactions of {screen} (chart range, scrub, tab swipe)

*Scroll & Gesture · % · Lower is better · 5 run(s) · automated by bench.py*

bench.py --group gesture plays the module's scripted gestures for this app under a Perfetto trace and reports janky %. If the module defines no gestures for the app, record it by hand: dumpsys gfxinfo reset, perform the gestures, dumpsys gfxinfo (native apps only).

### U1 — LTP updates per minute on {screen} (same symbol, market hours)

*Screen Updation · /min · Higher is better · 5 run(s) · manual, recorded with record.py*

During market hours, record 2 min on a liquid symbol present on every app. Count visible LTP changes and divide by 2.

### U2 — Tick lag vs reference feed

*Screen Updation · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

Optional. Film the app next to a reference terminal in one frame. Lag = time from the reference tick to the same price in the app.

### U3 — Live updates resume after 1 min in background

*Screen Updation · ms · Lower is better · 5 run(s) · manual, recorded with record.py*

Background for 1 min, then return to {screen}. Measure until the first LTP tick is visible.

### U4 — Idle redraw rate on {screen} (frames per second, 60 s, no input)

*Screen Updation · fps · Lower is better · 3 run(s) · automated by bench.py*

bench.py --group idle: a 60 s Perfetto FrameTimeline trace on {screen} with no touch. Value = app frames ÷ 60. A high rate with few visible changes means the screen redraws on every socket message.

### U5 — Wasted redraws on {screen}: idle frames identical to the previous frame

*Screen Updation · % · Lower is better · 3 run(s) · automated by bench.py*

bench.py --group idle --with-video: a separate 60 s screenrecord on {screen}, then ffmpeg mpdecimate counts frames that are pixel-identical to the previous one. Value = identical ÷ total × 100.

### O1 — Offline caching score

*Offline · % · Higher is better · 1 run(s) · manual, recorded with record.py*

Answer every offline item in the module (Yes = 2, Partial = 1, No = 0, N/A excluded). The score is computed on tab '4 Offline'.

### D1 — Data pointer / feature coverage

*Data Pointers · % · Higher is better · 1 run(s) · manual, recorded with record.py*

Answer every data item in the module (Yes = 1, Partial = 0.5, No = 0, N/A excluded). The score is computed on tab '5 Data Pointers'.

### X1 — Trackers detected (Exodus)

*External SDKs · count · Lower is better · 1 run(s) · manual, recorded with record.py*

Search the app on exodus-privacy.eu.org and use the latest report for the Play Store version.

### X2 — Permissions requested (Exodus)

*External SDKs · count · Lower is better · 1 run(s) · manual, recorded with record.py*

Same Exodus report: permissions count.

### X3 — Third-party domains contacted on {screen}

*External SDKs · count · Lower is better · 1 run(s) · manual, recorded with record.py*

PCAPdroid capture for 60 s on {screen}. Count unique domains that don't belong to the app's own company.

### X4 — Start-up lock contention: 'Long monitor contention' events before home

*External SDKs · count · Lower is better · 5 run(s) · automated by bench.py*

bench.py --group coldstart clears logcat, cold-starts the app and counts 'Long monitor contention' lines from the app's process until home is up. The longest wait in ms goes in the note.

### R1 — RAM (Total PSS) after cold start

*RAM · MB · Lower is better · 5 run(s) · automated by bench.py*

adb shell dumpsys meminfo <pkg>, TOTAL PSS (KB) ÷ 1024, taken 5 s after the home screen renders. The note carries the Java/native/code/graphics split.

### R2 — RAM (Total PSS) on {screen}

*RAM · MB · Lower is better · 5 run(s) · automated by bench.py*

Same command 5 s after {screen} is fully rendered.

### R3 — RAM (Total PSS) after 5 min on {screen}

*RAM · MB · Lower is better · 1 run(s) · automated by bench.py*

Same command after 5 min on {screen} with live ticks and a scroll every minute. A big rise from R2 suggests a leak. One soak per app.

### R4 — App size (installed)

*Storage · MB · Lower is better · 1 run(s) · manual, recorded with record.py*

Settings → Apps → <app> → Storage → App size (or adb shell dumpsys diskstats). One reading.

### R5 — User data – fresh install (before login)

*Storage · MB · Lower is better · 1 run(s) · manual, recorded with record.py*

Storage → User data right after install and first open, before login. One reading.

### R6 — User data – after login + first screen open

*Storage · MB · Lower is better · 1 run(s) · manual, recorded with record.py*

Storage → User data after login and opening the app's main screen once. One reading.

### R7 — Cache – after login + first screen open

*Storage · MB · Lower is better · 1 run(s) · manual, recorded with record.py*

Storage → Cache at the same point as R6. One reading.

### R8 — Total storage after 1 day of use

*Storage · MB · Lower is better · 1 run(s) · manual, recorded with record.py*

Storage → Total after a day of normal use. One reading.

### R9 — Leak check: PSS growth over 10 open/close cycles of {screen}

*RAM · MB · Lower is better · 1 run(s) · automated by bench.py*

bench.py --group leak: PSS on the screen before {screen}, then open and close {screen} ten times (scripted when the module has open_tap, otherwise by hand), 2 s settle, PSS again. Value = growth in MB.

### C1 — Average CPU on {screen} (live ticks, 15 min equivalent)

*CPU / Battery / Data · % · Lower is better · 3 run(s) · automated by bench.py*

CPU time used by the app's processes (/proc/<pid>/stat) ÷ session length. 100% = one full core.

### C2 — Battery drain – 15 min on {screen}

*CPU / Battery / Data · mAh · Lower is better · 3 run(s) · automated by bench.py*

Resets batterystats, simulates unplugged, then reads the app's estimated power use (mAh), scaled to 15 min.

### C3 — Device temperature rise – session on {screen}

*CPU / Battery / Data · °C · Lower is better · 3 run(s) · automated by bench.py*

SKIN temperature from dumpsys thermalservice at start and end. Not scaled. Use wireless debugging if possible, because USB charging heats the phone.

### C4 — Data used – 15 min on {screen}

*CPU / Battery / Data · MB · Lower is better · 3 run(s) · automated by bench.py*

The app's received + sent bytes from dumpsys netstats (forced poll) at start and end, scaled to 15 min.

### A1 — Crashes during all testing

*Stability · count · Lower is better · 1 run(s) · manual, recorded with record.py*

adb logcat -b crash kept running during every session. Count FATAL EXCEPTION entries for the package.

### A2 — ANRs during all testing

*Stability · count · Lower is better · 1 run(s) · manual, recorded with record.py*

Count 'ANR in <pkg>' entries in adb logcat over all sessions.

### A3 — Play Store rating

*Stability · ★ · Higher is better · 1 run(s) · manual, recorded with record.py*

Rating shown on the Play Store listing on the test date.

### A4 — Play Store download size

*Stability · MB · Lower is better · 1 run(s) · manual, recorded with record.py*

Size shown on the Play Store install button or in 'About this app' on the test device.

## Groups in bench.py

- `--group coldstart`: L1, X4
- `--group ram`: R1, R2
- `--group open`: L15
- `--group scroll`: S1, S2, S3, S4, S5
- `--group gesture`: S7
- `--group idle`: U4, U5
- `--group leak`: R9
- `--group live`: C1, C2, C3, C4

Added on 22 Oct 2026 from the Groww Quote-page report: L14, L15, S7, U4, U5, R9, X4.

# Run protocol

The same steps for every app and every developer, so differences in the numbers come from the
apps and not from the way we tested. Lifted from `docs/RISE Benchmark Plan.md` ("How every run is
done") and the Portfolio decisions in `archive/CONTEXT.md`.

## Principles

- **Black box, like for like.** Every app, RISE included, is the installed Play Store release
  build, measured from outside with adb, Perfetto, screen recordings and PCAPdroid. Competitor
  API timing is not available (TLS pinning); what the user feels is measured instead. RISE's own
  API log (every call, as JSON in logcat) is parsed into `api_calls.csv` as a diagnostic for RISE
  only; for every app a PCAPdroid pass gives hosts, connections and bytes (`net_calls.csv`).
- **One phone per module.** Each developer measures every app for their module on the same
  phone, same Wi-Fi, same session block. Ranks and 0–100 scores are comparable across modules;
  raw milliseconds are not, because phones differ.
- **Phone-scoped metrics once.** Cold start (L1), PIN→home (L2), RAM after cold start (R1),
  storage (R4–R8), SDK facts (X1, X2, X4) and Play Store facts (A3, A4) are measured once per
  developer and phone under module `_app`, then reused by every module they run.
- **Medium account by default.** Small and Large accounts only for L9, L10, S6 on modules
  marked `account_sensitive`.
- **RISE UAT last, never ranked.** If measured, it runs in its own pass after the ranked apps,
  back to back with a fresh RISE run, and is shown as a difference, not a rank.

## Before each block of runs

`python3 preflight.py --module <module>` checks and records these. Hard checks stop the run.

| Check | Rule | Hard? |
|---|---|---|
| Private DNS | Automatic or off, never a fixed hostname (a DNS filter broke RISE's Datadog upload in the first look) | yes |
| Power saving | Off (it resets Motion smoothness) | yes |
| Battery | Above 50 % | yes |
| Devices | Exactly one phone on adb, or pass `-s <serial>` | yes |
| Show taps | On, so the tap frame is visible in recordings (`--fix` turns it on) | soft |
| Animation scales | Window, transition and animator at 1.0 | soft |
| Charging | Prefer wireless debugging, unplugged; USB charging warms the phone and skews C3 | soft |
| Thermal status | 0 or 1; let the phone cool otherwise | soft |
| Display | Motion smoothness Adaptive (120 Hz) kept fixed for the whole benchmark; the rate in force is recorded from `dumpsys display` | recorded |
| Wi-Fi | Same 5 GHz network; RSSI and link speed recorded; a speed test noted with `--speedtest` | recorded |
| Accounts | Holdings / watchlist size per app noted with `--holdings` | recorded |
| Other | Brightness fixed, Do Not Disturb on, other apps closed, Developer options → Stay awake on, `adb logcat -b crash` streaming to a file for A1/A2 | manual |

## Each run, in order

1. **Cold run:** `bench.py` force-stops the app and starts it with `am start -S -W`. Warm runs
   (L7, L8) leave it in the background for the stated time.
2. The developer unlocks and **types the PIN on the phone**. PINs never go into scripts or notes.
3. The developer opens the module screen when prompted and presses Enter when it is fully loaded.
4. `bench.py` takes its readings (RAM, bytes, the app's API log, Perfetto trace, flings, gestures,
   idle window, leak cycles, live session) without anyone touching the phone, then force-stops the app.
   The PCAPdroid pass (`--group net`) is its own block, last and alone, because the VPN adds
   overhead: capture filtered to the app, launch, open the screen, 8 s settle (L11 window = the L15
   window), 60 s on the screen in run 1 for X3.
5. Every value is one row in `runs.csv` with the run number, source, artifact file and note.
6. **Rotate the app order** on each repeat (run 1: A B C, run 2: B C A, …) to cancel time-of-day
   and server load.
7. Manual metrics (scrcpy timings, offline grid, data pointers, Exodus, Play Store, storage) are
   entered through `record.py`, one value per call, with the method in the note.

## Run counts

| Metrics | Runs | Why |
|---|---|---|
| Timing, scroll, RAM, screen-update, network per open (L*, S*, U1–U3, R2, R3, L15) | 5 | The workbook reports the median; one bad run does not skew it |
| Idle redraw (U4, U5) and live session (C1–C4) | 3 | Market-hours time is scarce; live sessions run 10 min and are scaled to 15 |
| Storage, SDK, Play Store facts, leak check, crashes (R4–R8, X1–X3, A1–A4, R9, O1/D1 items) | 1 | Facts, not samples |
| Start-up contention (X4) | 5 | Taken with each cold start under `_app` |

If five runs spread more than 20 % ((max − min) ÷ median), take a sixth and replace the outlier
(`bench.py … --redo N`, or `record.py … --run N`); the replaced value goes in the note and the
newest row for a run wins. The workbook keeps five Run columns. R3 (5-minute soak) is one run
per app.

## Market hours

U1–U5 and C1–C4 only while the market is open: equity 09:15–15:30 IST, Mon–Fri; commodity
modules may use the evening session to 23:30 IST. `bench.py` warns outside these windows.

## Scroll and gesture tests

- Flings: ten `input swipe` gestures at the module's `scroll` fractions (default x = ½ width,
  75 % → 30 % height, 120 ms), five down then five up, under a Perfetto FrameTimeline trace.
  Perfetto is used for every app, Flutter and native alike; `dumpsys gfxinfo` does not see
  Flutter frames.
- Gestures (S7): the module's `gestures.per_app[<app>]` list, played with 1.5 s gaps under one
  trace. Gestures are written as screen fractions (`input tap 0.42 0.55`), never pixels, so they
  land on the same spot on every phone; bench.py prints them and asks before playing. Injected gestures lack a finger's pressure curve; they are identical for every app, so
  they compare apps and do not describe the feel of scrolling by hand.
- Idle (U4): 60 s on the screen with no input under a trace. Wasted redraws (U5): a separate
  60 s `screenrecord`, because recording itself costs frames.

## Offline tests

Airplane mode on for 30 s on the module screen, then off; cold relaunch in airplane mode for the
O1 items. Score Yes / Partial / No / N/A per item; N/A never counts as zero.

## Safety

- Phones may be logged into client accounts. Keep recordings and traces on your Mac
  (`~/.riise-benchmark/artifacts/`); never copy them into the shared folder.
- Never place orders or change holdings or watchlists while measuring.
- Record only what was measured. A missing value is better than a guessed one.
- `api_calls.csv` carries no query strings and masks id-like path segments; `net_calls.csv` holds
  hosts and byte counts only. Raw logs and `.pcap` captures stay in `~/.riise-benchmark/artifacts/`.

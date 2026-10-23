# Phone-scoped (`_app`) measurement notes — mahidhar / OPPO CPH3009

## L1 run-1 cold-start penalty (accepted spread failure, RISE)

Measured 2026-10-22. Run 1 is the slowest L1 reading in 6 of the 7 ranked apps:

| App | run 1 (ms) | median (ms) | run 1 vs median |
|---|---|---|---|
| Angel One | 712 | 666 | +7 % |
| Groww | 665 | 651 | +2 % |
| INDmoney | 561 | 512 | +10 % |
| Kite | 597 | 604 | −1 % |
| Kotak Neo | 911 | 809 | +13 % |
| RISE | 842 | 710 | +19 % |
| SAHI | 794 | 727 | +9 % |

RISE L1 spread is **0.265**, above the 0.2 threshold in PROTOCOL step 9. Run 1 was redone once
(`--group coldstart --redo 1`); the replacement came back higher (793 → 842 ms), confirming the
effect is systematic rather than a single bad sample.

**Decision:** keep the values as measured. The penalty is a property of the first cold start on
this phone and affects every app; redoing run 1 only for RISE — the app being ranked — would bias
the comparison. RISE shows the largest gap (+19 %) because it is the heaviest app, which is itself
a result rather than noise.

Angel One R1 run 4 was redone the same day for a genuine spread failure (0.411 → 0.163); that one
was a single outlier, not a pattern.

## R5 not measured (deliberate)

R5 is "user data on a fresh install, before login". All seven apps were already logged in, each
holding a hand-built Bench 20 watchlist that the whole `watchlist` module depends on. Measuring
R5 would require uninstalling and reinstalling every app and reading the value before logging
back in, destroying that state.

**Decision (2026-10-22):** leave R5 missing rather than estimate it. A developer running a fresh
phone can supply it; the combined report will show it as missing for this device, not as zero.

## A4 not measured (deliberate) — SUPERSEDED, see "A4 (Play Store download size) — proxy used" below

_Later the same evening the developer chose to record a proxy instead of leaving A4 missing; the
values in runs.csv are the proxy. The `du` figures below are a different measure (APK directory incl.
extracted libs/oat) and are not the recorded values._

A4 is the Play Store download size. The Play Store shows it only on the install button, i.e.
before an app is installed; all seven apps are installed on this phone, so every listing shows
Uninstall/Open instead. The "About this app" detail page does not carry it either (checked on the
device, 2026-10-22).

**Decision:** leave A4 missing rather than substitute a different number. On-device APK directory
sizes were measured with `du` while diagnosing (RISE 191.8, Kite 42.7, Groww 95.6, Angel One
103.1, INDmoney 101.1, Kotak Neo 199.7, SAHI 144.9 MB) but these are installed footprints, not
Play Store download sizes, so they are **not** recorded as A4. A developer whose phone does not
have these apps installed can read all seven in one pass.

## A3 method

Play Store listing opened per package via `market://details?id=…` on the test device and read
with `uiautomator dump`; the rating is the value under the "Ratings and reviews" heading. Only
read — no Install/Uninstall/Open control was ever tapped.

## R4 / R6 / R7 method

Read from Settings → Apps → <app> → Storage usage via `uiautomator dump`, with the on-screen
version string checked against `bench.py installed` so a failed navigation cannot silently
re-read the previous app's numbers.

`adb shell dumpsys diskstats` was tried first and **rejected**: it listed only 491 of 498
packages, omitted 5 of the 7 apps entirely, reported 0 MB of data and cache for Groww (which is
logged in), and disagreed with Settings on RISE (216.7/18.7/6.3 vs 207/14.1/9.4). METRICS.md
allows either source; Settings is the one used here for all seven apps.

## Environment

2.4 GHz Wi-Fi "Mahi_work" (deviation from PROTOCOL's 5 GHz), PCAPdroid off, DND on, 120 Hz,
private DNS off, power saving off, battery 77 % on battery. One device over wireless adb.

## A4 (Play Store download size) — proxy used

The Play Store on this phone shows the download size only on the Install button of apps that are
not installed; for installed apps "About this app → App info" lists version, update date,
downloads, required OS and release date, but no size. All seven apps are installed, so the
METRICS.md source is unavailable.

**Decision (developer, 22 Oct 2026):** A4 = installed APK size, the sum of the base and split APK
files returned by `pm path <pkg>`, measured the same way for all seven. The Play Store download is
compressed, so A4 here reads higher than a Play Store download size would; the ranking is
like-for-like. Kite ships as 11 split APKs (17.3 MB total), far smaller than the others (81–124 MB).
RISE is the largest at 123.6 MB.

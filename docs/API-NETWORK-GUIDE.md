# Capturing API calls and network traffic with the benchmark agent

A developer's guide to the API / network part of the RISE benchmark: what it records, how to set
your phone up once, how the agent runs it, and how to read the results. Read `README.md` first for
the general setup; this page only covers the network part.

## 1. What you get, per app

| App | What is captured | How | Where it lands |
|---|---|---|---|
| RISE | Every API call during a screen open and during launch: method, host, path, status, duration, response size, CDN cache state, repeats | RISE's production build writes each call to logcat; `bench.py` reads it inside the `open` runs and the `_app` cold starts. No app change, no proxy. | `api_calls.csv` next to `runs.csv`; a one-line summary in the L15 / R1 note |
| Every app, RISE included | Connections opened, host names, bytes in / out, time to first byte, third-party hosts | A PCAPdroid capture filtered to the app, started and stopped over adb by `bench.py --group net` | `net_calls.csv`; metrics L11 and X3 in `runs.csv` |

What you do **not** get: competitor request paths or bodies (their release builds log nothing and
pin TLS), and RISE response bodies (only the UAT build logs those). Query strings are dropped and
id-like path segments are masked before anything is written, so `api_calls.csv` is safe to commit.

## 2. One-time setup on your phone and Mac

1. Install **PCAPdroid** from the Play Store (the free version is enough).
2. Open PCAPdroid → Settings → **Control permissions** → ⋮ menu → **API key**. Copy the key.
3. On your Mac, inside the repo:

   ```bash
   python3 record.py --pcapdroid-key <key>
   ```

   The key goes to `~/.riise-benchmark/me.json`, outside the repo. It lets the agent start and
   stop captures without a tap on "Allow" each run. Never paste it into notes or results.
4. Keep the phone **unlocked, screen on** (Developer options → Stay awake) and Private DNS on
   Automatic, as for every run. The first capture on a phone shows Android's **VPN request**: tap OK
   once; Android remembers it.

Nothing else changes: `adb`, Python, `perfetto` and the rest are as in `README.md`.

## 3. Running it

### The API log needs nothing from you

Run your module as usual with `/benchmark <module>`. During every `open` run (L15) and every
`_app` cold start, `bench.py` reads the app's log. For RISE you will see a line like

```
api: 4 calls, 3 endpoints, 1 repeats, net 3.20 s, longest GET /wms/v2/api/Search/Dashboard 503 ms, 41 KB → api_calls.csv
```

For a competitor you will see `api log: no API lines from the app (expected for competitor apps)`.
That is normal, not an error.

### The network pass runs last, alone

After every other group for an app, the agent runs

```bash
python3 drive.py run "<app>" --module <module> --group net --runs 5
```

`net` cannot be combined with other groups: PCAPdroid's VPN adds overhead, so it never runs under
scroll or timing measurements. One run looks like this on the phone:

1. PCAPdroid starts a capture filtered to the app (the consent dialog shows only when no API key
   is saved; tap **Allow**).
2. The app is cold-started. Approve its **biometric / PIN** prompt by hand, as always; the driver
   waits up to five minutes and never types a PIN.
3. The driver opens the module screen with the module's `auto_open` steps.
4. **Run 1 only:** the driver plays the module's `exercise` steps for 60 seconds (see below), then
   the capture is stopped, pulled and parsed. Runs 2 to 5 stop 8 seconds after the screen loads.

Each run takes under a minute, run 1 about two. Re-running the same command resumes at the first
missing run; `--redo 1` takes run 1 (and X3) again.

### Tell the driver how to exercise the screen

X3 (third-party hosts) is taken while the screen is used, not idle. Each module carries the steps
under `auto_open.exercise` in `modules/<module>.json`:

```json
"exercise": {
  "default": ["del:8", "sleep:2", "text:{subject2}", "sleep:4", "hide_keyboard", "sleep:2"],
  "per_app": {
    "Angel One": ["tap:0.50 0.083", "sleep:1", "del:8", "sleep:2", "text:{subject2}", "sleep:4",
                  "hide_keyboard", "sleep:1", "tap:0.31 0.15", "sleep:3", "tap:0.51 0.15", "sleep:3",
                  "tap:0.71 0.15", "sleep:3", "tap:0.13 0.15", "sleep:3"]
  }
}
```

Step forms: `tap:X Y` and `swipe:X1 Y1 X2 Y2 [ms]` with screen **fractions** 0 to 1, `find:<text>`,
`text:<string>`, `del:N` (backspace N times, one by one), `key:<KEYCODE>`, `sleep:<s>`,
`hide_keyboard`. `{subject}` and `{subject2}` are the first two `test_subjects` of the module.

To get fractions for an app: open the screen once by hand, take a screenshot
(`adb exec-out screencap -p > s.png`) and divide the pixel position by the width or height, or run
`python3 drive.py find "<text>"` for screens that hold still. Apps whose home animates live prices
(most of them) need `tap:` steps, because the UI dump never settles. `exercise` and `auto_open`
are not part of the module version, so adding them does not flag earlier results.

### Name the company's own domains

X3 counts hosts that are not the app's own. `apps.json` holds them:

```json
"Kite": {"package": "com.zerodha.kite3", "ranked": true, "own_domains": ["zerodha.com", "zerodha.net", "kite.trade"]}
```

A host counts as own when it equals or ends with one of these. To claim a CDN distribution (for
example a CloudFront host that serves the app's own images), add the full host name. When an app
has no `own_domains`, bench.py prints the hosts it saw and X3 stays a manual entry.

## 4. Reading the results

- **`api_calls.csv`** (RISE): one row per call with `run`, `phase` (`open` or `launch`), `seq`,
  `t_rel_ms` from the first call, `method`, `host`, `path`, `status`, `duration_ms`, `size_bytes`,
  `cache`, `repeat_of` (the `seq` of an earlier identical call in the same open).
- **`net_calls.csv`** (every app): one row per connection with `phase` (`launch`, `open`,
  `screen`), `host` (TLS SNI, else DNS answer, else the IP), `proto` (`tcp`, `quic`, `udp`),
  `first_response_ms`, `bytes_in`, `bytes_out`, `pkts`, `third_party`.
- **Sheet `10 API & Network calls`** in the module workbook (`python3 build_report.py --module
  <module>`): an app-by-app comparison, "Where RISE's API calls need optimisation" (rule-based
  pointers: repeats, calls over 300 ms, cache misses, launch connection fan-out, connection reuse,
  analytics during the open, non-production hosts), per-run tables and the full listings.
  Add `--html` for the same content as a standalone page, `<workbook>_api.html`, to share
  without Excel.
- **Diagnostic, not scored.** None of this feeds the category scores or the RISE rank, because
  competitors have no API log to compare against.

Things to keep in mind when reading:

- Modern apps reuse connections. Typing and tapping tabs may add no new connection while moving
  hundreds of KB over an existing one; the per-window byte counts in the note show that traffic.
- One 60-second run is a small sample for third-party hosts. Treat X3 as indicative.
- CDN distributions show as third-party until named in `own_domains`.
- The L11 window is the same as L15's (open prompt to loaded + 8 s), so the two sit side by side.

## 5. Privacy and what to commit

- Raw logcat dumps and `.pcap` captures stay on your Mac under
  `~/.riise-benchmark/artifacts/<module>/` and are git-ignored. They can carry identifiers; never
  copy them into the repo.
- Commit `api_calls.csv` and `net_calls.csv` with your results folder on your
  `results/<module>-<name>` branch, like `runs.csv`.
- The PCAPdroid API key lives only in `~/.riise-benchmark/me.json`.

## 6. Troubleshooting

| Message or symptom | Meaning | Do |
|---|---|---|
| `--group net runs alone` | You combined `net` with another group | Run `net` by itself, after the others |
| `PCAPdroid is not installed on this phone` | PCAPdroid missing | Install it from the Play Store |
| `No PCAPdroid API key saved` | Key not stored | Step 2 above; or tap Allow on each run |
| `PCAPdroid did not start` | Consent or VPN request denied, or PCAPdroid stuck | Tap Allow / OK, check PCAPdroid shows no error, rerun with `--redo N` |
| `PCAPdroid wrote no capture` / `capture unreadable: pcapng` | The capture file is empty or in pcapng | In PCAPdroid settings keep the dump format PCAP, not PCAPNG |
| `The phone is locked or its screen is off` | Pre-flight stop | Unlock, Stay awake on, rerun |
| `uiautomator dump failed` | The screen never stops animating | Use `tap:` steps instead of `find:` |
| `api log: no API lines from the app` on RISE | Logcat was cleared or the app is the UAT / Pilot package | Check `bench.py` targeted `com.mosl.mobile`; rerun |
| `X3 stays manual (no own_domains …)` | `apps.json` lacks the app's domains | Add `own_domains`, rerun run 1 with `--redo 1` |

Questions or a step that does not fit your module: open a GitHub issue titled `agent: <topic>`
as described in `README.md`.

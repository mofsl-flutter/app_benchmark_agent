# Groww — Stock Quote Page Benchmark

| | |
|---|---|
| **App** | Groww `com.nextbillion.groww` v18.21.1 (build 126001072), targetSdk 36 |
| **Screen under test** | Stock Quote page (`genesys.stocks.activities.StocksActivity`) — Reliance, TCS, Infosys, HDFC Bank, Wipro |
| **Device** | Samsung SM-E146B, Android 14 (API 34), arm64, 5.6 GB RAM, 1080×2408 @ 60 Hz |
| **Network** | Wi-Fi (unmetered) |
| **Session** | 22 Oct 2026, 11:04 – 11:52 IST (live NSE market hours) |
| **Tooling** | `adb` (am start -W, dumpsys gfxinfo / meminfo / netstats / diskstats, screenrecord, logcat, per-app firewall), ffmpeg frame analysis, APK static analysis |

---

## 1. Executive summary

| Parameter | Result | Verdict |
|---|---|---|
| Load time — repeat open (in-app) | Activity displayed **~250 ms**; price + chart visible **~0.18 s** after tap | Excellent |
| Load time — first open of a stock | **1.2 – 1.5 s** full-screen spinner before content | Average |
| Load time — cold start | Launch → PIN **~0.9 s**; PIN → price/chart **~0.69 s**; PIN → full Overview **~1.54 s** | Good |
| Scroll FPS (60 Hz panel) | 1–3 % janky frames, P50 13 ms, P90 22 ms | Good |
| Chart gestures | 12–14 % janky (timeframe switch / scrub) | Needs work |
| Screen updates | Price ~1 tick/s, market depth ~2.5 updates/s | Good |
| Idle rendering | **~32 fps continuous redraw on Overview, 97 % of frames visually identical**; ~70 % of one CPU core while idle | Poor (battery cost) |
| Offline caching | **No offline support** — no quote cache, no chart cache, no "offline" banner, cold start blocked | Poor |
| Network reconnect | First tick ~9 s, steady stream ~30–35 s; chart needs manual retry | Poor |
| RAM (PSS) | Fresh 183 MB → Home 280 MB → Quote **368 MB** → after full scroll 385 MB | Heavy |
| Storage | Install 125 MB; Fresh total 130 MB → after login 136 MB → after ~1 h use 145 MB | Lean data footprint |
| External SDKs | ~25 third-party SDKs; live feed over **NATS**; Firebase, Sentry, AppsFlyer, Freshchat, HyperVerge, Digio, Razorpay, RootBeer… | Heavy but standard |

**Headline:** Groww optimises for perceived speed on repeat opens — the page renders instantly from in-memory data and then refreshes the price. Its weak spots are idle rendering cost and the complete lack of offline resilience.

---

## 2. Loading time — per screen and API calls

### 2.1 How it was measured
- **Activity time:** `ActivityTaskManager: Displayed …StocksActivity +Xms` (first frame).
- **Content-ready time:** the screen was recorded with `screenrecord` and analysed frame by frame. "Header ready" = logo, LTP and chart drawn; "Overview complete" = last Overview widget (AI Insights card) settled. Resolution is about ±17–33 ms.
- **Network per open:** `dumpsys netstats` UID byte delta (Groww UID 10333) across the open plus 8 s on screen.

### 2.2 Cold start (process killed → deep link `groww.in/stocks/reliance-industries-ltd`)

Flow: `LoginActivity` (router) → `TwoFactorActivity` (**PIN, mandatory**) → `MainNativeActivity` → `StocksActivity`

| Run | Launch → PIN screen | PIN submit → Quote displayed | PIN submit → price + chart | PIN submit → Overview complete |
|---|---|---|---|---|
| 1 | 950 ms | 857 ms | 0.76 s | 1.34 s |
| 2 | 882 ms | 891 ms | 0.64 s | 1.75 s |
| 3 | 846 ms | 845 ms | 0.66 s | 1.52 s |
| **Avg** | **893 ms** | **864 ms** | **0.69 s** | **1.54 s** |

Visual sequence after PIN: full-screen spinner (~0.6 s) → header + chart → Market Depth renders → **layout shift** (Market Depth collapses, AI Insights card pushed in, ~0.4 s later).

![Cold load after PIN](assets/01-cold-load-after-pin.png)

### 2.3 In-app open (Search → tap stock → Quote)

| Scenario | Runs | Activity displayed | Tap → price/chart visible | Data received / sent |
|---|---|---|---|---|
| First open after **fresh login** (empty cache) | 1 | 308 ms | **1.17 s** (spinner) | **434 KB** / 65 KB |
| First open of stock in session (Infosys) | 1 | 249 ms | **1.49 s** (spinner) | 74 KB / 79 KB |
| First open of stock in session (TCS) | 2 | 181–331 ms | 0.18–0.19 s | 59–70 KB / 55–70 KB |
| Repeat opens (TCS / INFY / RELIANCE) | 8 | 222–290 ms (avg **252 ms**) | **0.15–0.21 s** | 12–50 KB / 10–66 KB |

Behaviour notes:
- **Optimistic render:** on repeat opens the header shows the last-known price at once (for example ₹2,503.30), and the live price replaces it about 0.5 s later (₹2,502.40). There is no spinner and no skeleton.
- The **chart** finishes about 0.3–0.5 s after the header on repeat opens.
- External deep links **always** go through the PIN screen, even when the process is warm, so a warm "deep-link to quote" time can't be measured without PIN entry.

| First open — spinner (~1.5 s) | Repeat open — instant (~0.2 s) |
|---|---|
| ![](assets/02-first-open-spinner.png) | ![](assets/03-repeat-open-instant.png) |

### 2.4 Tab switches and chart timeframes (all on the same Quote screen)

| Interaction | Latency | Network |
|---|---|---|
| Overview → Technicals / F&O / News / Events | < 150 ms, no spinner (content prefetched) | Technicals ~129 KB incl. scroll; F&O ~29 KB; News ~22–39 KB |
| Chart 1D → 1W → 1M → 3M → 6M → 1Y → 5Y → All → 1D | 40–190 ms from button highlight to new chart, plus ~150 ms animation | 26 KB rx / 48 KB tx for all 8 switches (small per-timeframe fetch) |
| Line ↔ Candle toggle | Instant | — |

### 2.5 API-level visibility
Groww's REST traffic uses OkHttp over TLS, with Conscrypt and security native libs. The live feed uses a **NATS** client (`io.nats.client`, thread `nats:2`). The phone isn't rooted, and MITM is blocked by pinning or anti-tamper, so **individual API URLs and timings could not be captured**. The data volumes above stand in for that. Domains found in the APK include `mapi.groww.in`, `app-assets.groww.in`, `prod-cp-static-assets.groww.in`, `telemetry-app.groww.in`, `client-pixel.groww.in` and `storage.googleapis.com`.

---

## 3. Scrolling behaviour and gestures — FPS

Panel at 60 Hz, so the frame budget is 16.6 ms. Measured with `dumpsys gfxinfo` (reset before each gesture).

| Gesture | Frames | Janky | P50 | P90 | P95 | P99 |
|---|---|---|---|---|---|---|
| Overview — fling **down** to bottom (9 flings) | 672 | **2.98 %** | 13 ms | 22 ms | 22 ms | 31 ms |
| Overview — fling **up** to top (9 flings) | 856 | **1.17 %** | 13 ms | 22 ms | 23 ms | 61 ms |
| Technicals — slow drag, full tab | 1,802 | 3.11 % | 15 ms | 19 ms | — | 28 ms |
| News — slow drag, full tab | 758 | 3.03 % | 10 ms | 15 ms | — | 22 ms |
| F&O — drag | 143 | 4.20 % | 12 ms | 17 ms | — | 27 ms |
| Chart timeframe switching (8 taps) | 149 | **12.75 %** | 17 ms | 28 ms | — | 38 ms |
| Chart touch-scrub (long-press + drag, ×3) | 244 | **13.93 %** | 13 ms | 17 ms | — | 23 ms |

Observations:
- List scrolling is smooth. Sticky elements work well: a collapsed header (name + LTP + change), sticky tabs, and a sticky bottom CTA (SIP / Sell / Buy).
- Most chart jank comes from the redraw animation on timeframe change. The scrub figure is partly inflated because `adb` injects touch events at an uneven rate.
- Cold run 1 logged **"Skipped 32 frames"** on the main thread during start-up, alongside a Freshchat `RemoteConfig` lock contention.
- The Overview page is about 14 screen-heights tall (about 8,400 px); Technicals is about 4.

---

## 4. Screen updation (live data)

Measured over 60 s windows with no touch input, using frame-diff analysis of the screen recording plus gfxinfo and netstats.

| State | Frames / 60 s | Visible price updates | Network / 60 s (rx / tx) | App CPU (idle) |
|---|---|---|---|---|
| Overview, top (header + chart) | 2,002 (~33 fps) | **48 / min (~1 per s)** | 105 KB / 49 KB | — |
| Overview, market depth visible | 2,126 (~35 fps) | price ~1/s; **depth rows ~2.5 updates/s** | **163 KB / 67 KB** | **69.5 % of one core** (8.7 % of device) |
| News tab | 26 | 19 / min (~1 per 3 s) | 10 KB / 25 KB | 35.1 % of one core |
| Offline (network blocked) | **0** | 0 | 0 | — |

Key findings:
1. **Wasted redraws.** On Overview, **1,864 of 1,925 frames (97 %) were pixel-identical** to the previous frame. The view is invalidated about 32 times a second although only about one visible change per second happens. RenderThread was the top thread at 17.8 % CPU. Redraw drops to 0 when the network is cut, so every incoming socket message triggers a redraw whether or not a value changed.
2. **Subscription scoping works.** Data volume falls about 16× when leaving Overview (163 KB → 10 KB per minute), so the market-depth stream is unsubscribed when not visible.
3. Live elements: LTP and change in the header (also in the sticky header), the chart's last-point "pulse" dot, market depth (5 levels plus buy/sell %), Similar-stocks prices, and F&O futures and options prices.
4. Delivery-volume data on Technicals showed **16 Oct 2026** on 22 Oct, so that section is updated end-of-day with a lag.

---

## 5. Caching behaviour in offline mode

Method: per-app firewall (`cmd connectivity set-package-networking-enabled false com.nextbillion.groww`) blocks only Groww, so ADB keeps working.

| Scenario | Behaviour |
|---|---|
| Quote page open when network drops | **No offline banner or stale-data indicator.** Price silently freezes. Rendering drops to 0 fps. |
| Switch chart timeframe offline | "We are having trouble fetching the graph / retry". **Even 1D, which was already loaded, is gone**, so chart data isn't cached even in memory. |
| Switch to Technicals offline | Blank loader |
| Switch to F&O offline | Section titles render (Open Interest, View option chain) without values |
| Search offline — query searched earlier (TCS) | Cached results shown |
| Search offline — new query (WIPRO) | "No result for 'WIPRO'", which is **misleading** (should say offline). Trending searches are cached. |
| Open a stock viewed minutes earlier (TCS) | **Full-page "Something went wrong / TRY AGAIN"**, so there's no persistent Quote cache |
| Cold start while offline | "Oops! Something went wrong" **before the PIN screen**, so the app is unusable offline |
| Network restored on an open Quote page | First price update after **~9 s**; steady ticks after **~30–35 s**; chart stays in error until the user taps *retry*; F&O values don't refill |

| Offline Quote: chart error, Technicals and F&O empty | Offline Search and stock open |
|---|---|
| ![](assets/13-offline-quote.png) | ![](assets/14-offline-search-open.png) |

**Conclusion:** the fast repeat opens come from an in-memory and network-first strategy, not a disk cache. Search results are the only Quote-adjacent data persisted (in MMKV).

---

## 6. Data pointers and user-wise behaviour

### 6.1 Data points on the Quote page

**Header and chart (always visible)**
- Logo, Symbol · Exchange with an **NSE ⇄ BSE switch**, company name, LTP, absolute and % change, period label (1D)
- **Chain** shortcut (Option Chain)
- Chart: line by default; ranges 1D / 1W / 1M / 3M / 6M / 1Y / 5Y / All; **candle toggle with volume bars**; full-screen; touch-scrub crosshair showing **Open, High, Low, Close, Volume** and timestamp
- App bar: back, **price alert**, **watchlist bookmark**, search
- Sticky compact header on scroll: name, LTP, change

**Tabs: Overview · Technicals · F&O · News · Events** (the tab bar scrolls horizontally)

| Tab | Sections and fields |
|---|---|
| **Overview** | **AI Insights** (collapsible) · **Market depth**: buy % vs sell % bar, 5 bid and 5 ask levels with qty, bid and ask totals · **Performance**: today's low/high slider, 52-week low/high slider, open, previous close, volume, lower and upper circuit · **Fundamentals** (10): market cap, ROE, P/E (TTM), EPS (TTM), P/B, dividend yield, industry P/E, book value, debt-to-equity, face value · **Financial performance**: quarterly/yearly toggle, revenue and profit bars (5 periods), growth 1Y (TTM) and 3Y CAGR, *All Financials* · **About company** (collapsed) · **Shareholding pattern**: 5 quarters; promoters, DIIs, FIIs, public; *Shareholder details* · **Top mutual funds invested** (collapsed) · **Similar stocks**: 7 peers with live price and change; market-price toggle · **Recently viewed** |
| **Technicals** | **Summary** gauge ("Slightly bearish": 7 bearish, 2 neutral, 4 bullish) · **Indicators**: RSI(14), MACD(12,26,9), beta with verdicts · **Support and resistance**: R1–R3, pivot, S1–S3 with live price marker · **Moving averages**: 10/20/50/100/200-day MA and EMA · **Delivery volume %**: daily/weekly/monthly, total traded vs delivery volume, 5-period chart |
| **F&O** | Open interest (total put OI, put:call ratio, total call OI) · Top futures (2 expiries, live) · Top options by volume (All / Call / Put, live) · *View option chain* |
| **News** | Aggregated headlines: source (BSE, ET, Moneycontrol, Financial Express, Hindu BusinessLine, ScoutQuest…), relative time, 2–3 line summary; text only, no images |
| **Events** | Quarterly and annual results ("Groww summary available"), dividends (ex-date, ₹ per share, announced), filters, *Events calendar* |

| Overview (1/3) | Overview (2/3) | Overview (3/3) |
|---|---|---|
| ![](assets/04-overview-1.png) | ![](assets/05-overview-2.png) | ![](assets/06-overview-3.png) |

| Technicals | F&O | News | Events |
|---|---|---|---|
| ![](assets/07-technicals.png) | ![](assets/08-fno.png) | ![](assets/09-news.png) | ![](assets/10-events.png) |

| Candle mode | Touch-scrub (OHLC + volume) |
|---|---|
| ![](assets/11-candle.png) | ![](assets/12-scrub.png) |

### 6.2 User-specific behaviour
- **Account-state gating:** an inactive or blocked account shows a sticky banner ("You cannot place orders as your account is blocked due to inactivity"). **Sell and Buy are disabled**; SIP stays enabled. Home shows a re-KYC "Re-activate now" card.
- **Recently viewed** is per user and updates in real time (Infosys, TCS and HDFC Bank appeared right after viewing).
- **Watchlist bookmark** and **price-alert** state is per user in the app bar.
- **Personalised PIN screen** ("Hi, <user name>"). PIN is required on cold start, on every external deep link, and after the app has been in the background (a short grace window was seen).
- **Engagement prompts:** an in-app rating card ("How is your experience with Groww?") appeared on home right after login.
- Search history is cached per user and shown offline.

---

## 7. External SDK behaviour

### 7.1 SDKs found in the APK

| Category | SDKs |
|---|---|
| Analytics / attribution | Firebase Analytics, Firebase Performance, Firebase A/B Testing, AppsFlyer (+ OAID, LVL, share), Google Install Referrer |
| Crash / monitoring | Sentry (Android, Compose, profiling), Firebase Crashlytics, Firebase Sessions, HyperVerge CrashGuard |
| Config / messaging | Firebase Remote Config, Firebase Cloud Messaging, Firebase Installations, App Check, Firebase Auth, Firebase Storage |
| Real-time data | **NATS client** (`io.nats.client`): live quote and market-depth feed; RxJava |
| Networking | OkHttp3, Cronet (`org.chromium.net`), Volley, Conscrypt (TLS), Moshi, Gson, Wire / Protobuf |
| Images / animation | Facebook Fresco (image pipeline, animated GIF/WebP), Coil 2 and 3, Picasso, Lottie, **Rive**, Facebook Shimmer, Robinhood Ticker (animated price digits) and Spark (sparklines), MPAndroidChart |
| Storage | **Tencent MMKV**, AndroidX DataStore |
| KYC / payments / support | HyperVerge (HyperSnap, face detection, doc detection, QR), Digio (eSign / KYC camera), Razorpay, Google Play Billing, PayU (web), OTPless (OTP auto-read), Freshchat (support), Google ML Kit, ZXing, image cropper |
| Security | **RootBeer** (root detection), native `libSecureComponent.so`, `libtoolChecker.so`, `libndp-detector.so` (anti-tamper / debugger detection) |

Native libs (arm64): 17, including `librive-android`, `libmmkv`, `libimagepipeline`, `libconscrypt_jni` and `libnativecore`.

### 7.2 Runtime behaviour seen on the Quote journey
- **Start-up initialises many SDKs:** Firebase Analytics ("App measurement initialized"), Sentry (manual init, `auto-init: false`), RootBeer checks (42 log lines per cold start), MMKV (84 lines), the Chromium/WebView provider, and the camera manager, all before the Quote page.
- **Freshchat** `RemoteConfig` caused **long monitor contention** in 2 of 3 cold starts, and one run skipped 32 frames. A support SDK is touching the critical start-up path.
- **A WebView instance stays alive** on the Quote page (`WebViews: 1` in meminfo).
- Firebase Analytics logs screen-view events per screen.
- 176 threads in the process while on the Quote page, including many coroutine `DefaultDispatcher` threads, the NATS thread, OkHttp and Mali GPU threads.
- `FLAG_SECURE` is **not** set on the Quote page (screenshots and screen recording work).

---

## 8. RAM usage and application storage — fresh vs after login

### 8.1 RAM (PSS, `dumpsys meminfo`)

| State | Total PSS | Java heap | Native heap | Code | Graphics | Notes |
|---|---|---|---|---|---|---|
| **Fresh** (data cleared, login screen) | **182.5 MB** | 18.8 | 42.8 | 40.2 | 60.9 | 0 WebViews |
| Home after login | 279.7 MB | — | — | — | — | |
| **Quote page opened** (after fresh login) | **367.7 MB** | 45.5 | 135.0 | 75.0 | 67.9 | RSS 460 MB, 1 WebView |
| Quote after scrolling all sections | 384.8 MB | 60.8 | 134.8 | 75.3 | 69.6 | +17 MB, mostly Java heap |
| Quote in a long session (start of test) | 395.4 MB | 59.2 | 105.0 | 52.8 | **112.2** | 3 activities, 2,201 views |
| Peak seen (5th repeated open) | 400.8 MB | | | | | |

**Leak check (10 open/close cycles of Quote):** PSS on the search screen went from 354.8 MB to 376.1 MB (**+21 MB**). The activity count stayed at 3, so **no activity leak**, but there is mild retained growth (caches and bitmaps). Opening the Quote page costs about **+90 MB** over Home.

### 8.2 Storage (Settings › App info › Storage)

| State | App | Data | Cache | Total |
|---|---|---|---|---|
| Download size (APK splits: base 86.3 + arm64 12.0 + xxhdpi 0.2) | 98.5 MB | — | — | — |
| **Fresh** (data cleared, first launch to login screen) | 125 MB | **2.98 MB** | **1.20 MB** | **130 MB** |
| **After login** (+ ~5 Quote opens) | 125 MB | 8.26 MB | 2.24 MB | 136 MB |
| After ~1 h of normal use today | 125 MB | 12.69 MB | 6.62 MB | 145 MB |

The data footprint is lean, consistent with no persistent Quote or chart cache: login adds about 5 MB of data and about 1 MB of cache, and an hour of use adds about 15 MB in total.

---

## 9. What we can take from this (for Rise app)

| Groww does well | Groww's gaps |
|---|---|
| Optimistic render on repeat opens (last price shown at once, refreshed in about 0.5 s) gives a sub-200 ms *perceived* load | Re-renders about 32 fps when idle; 97 % of frames are wasted, costing CPU and battery |
| Prefetches all tabs: tab switch under 150 ms, no spinners | No offline banner; stale prices look live |
| Unsubscribes the depth stream when it isn't visible (about 16× less data) | No disk cache for the Quote page or charts; offline cold start is blocked |
| Smooth list scrolling (1–3 % jank) with sticky header, tabs and CTA | Slow socket recovery (~30 s) and manual chart retry after reconnect |
| Small, cheap per-timeframe chart fetches (~3 KB each) | Layout shift on cold load (Market Depth → AI Insights) |
| Clear account-state gating on CTAs | Heavy SDK start-up (Freshchat contention, RootBeer, WebView, camera) |

---

## 10. Methodology and limitations
- One device, one Wi-Fi network, one session during live market hours. Absolute numbers will differ on other devices and networks; relative findings should hold.
- Touch input came from `adb shell input`. Event pacing is not human-like, which inflates jank on gesture-heavy tests (scrub).
- Visual timings come from `screenrecord` (variable frame rate, up to 60 fps), roughly ±17–33 ms.
- Per-API latency is **not** available (TLS, pinning and anti-tamper on a non-rooted device). Network cost is reported as per-UID byte deltas from `netstats`, which include background traffic from the app in the same window.
- Cold-start PIN entry was done by hand, so "PIN submit" is taken from the last PIN-screen frame in the recording.
- Groww's data was cleared once for the fresh-state measurements, and the user then logged in again.

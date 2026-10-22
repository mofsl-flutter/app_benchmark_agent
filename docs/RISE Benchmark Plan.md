[Overview](#overview) [Apps](#apps) [Scope](#scope) [Sections](#sections) [Metrics](#metrics) [Scroll and response](#devtools) [API timing](#logcat) [Their claims](#claims) [Flutter builds](#flutter) [RISE UAT](#uat) [First look](#findings) [Protocol](#protocol) [Output](#output) [Q&A](#qa) [Next steps](#next)

App Optimization · 21 Oct 2026 For review · no test data yet

# RISE Benchmark Plan

How we will measure where the RISE app stands against Kite, Groww, Angel One, INDmoney, Kotak Neo and SAHI. All seven apps run on one phone, and every result is captured as a number.

Device

Galaxy S25 UltraSM-S938B · Android 16 · 11 GB RAM · screen up to 120 Hz, rate fixed for runs

Network

Wi-Fi, 5 GHzLink speed 433 Mbps, signal −42 dBm, logged again before each block of runs

Repetitions

5 per app and screenReport the median and p90; flag runs that spread more than 20%

In scope

Launch and the dashboard tabs you listedCompared section by section. Add Funds is out of scope.

Judging

10 criteria, 10% eachThe nine measured parameters plus Build and stack. Seven apps are ranked and RISE UAT is shown last

**Leadership:** read this overview, [Output](#output) and [Q&A](#qa). The final report opens with a one-screen scorecard that ranks RISE on every parameter.

**Engineering:** the rest of this page is the method, the first signals from RISE's logs, and the checks that make the numbers defensible.

## The seven apps

Framework and Flutter version were read from each installed APK. Versions are what is on the phone today.

| App | Package | Version | Framework | Flutter and Dart |
| --- | --- | --- | --- | --- |
| **RISE** | `com.mosl.mobile` | 6.2.09 | FlutterSkia renderer in the installed build, see Flutter builds | 3.44.2 to 3.44.9Dart 3.12.2 |
| Kite | `com.zerodha.kite3` | 3.11.11 | Flutter | 3.41.3 or 3.41.4Dart 3.11.1 |
| Groww | `com.nextbillion.groww` | 18.21.1 | NativeNo Flutter or React Native engine found | n/a |
| Angel One | `com.msf.angelmobile` | 126.9.1 | NativeNo Flutter or React Native engine found | n/a |
| INDmoney | `in.indwealth` | 9.9.88 | Flutter engine presentNo Flutter log lines during launch and home, so those screens may be native. To confirm in the pilot. | 3.38.9Dart 3.10.8 |
| Kotak Neo | `com.kotak.neo` | 2.2.86 | Flutter | 3.38.10Dart 3.10.9 |
| SAHI | `com.aaritya.sahi_trade_app` | 1.0 | Flutter | 3.44.2 to 3.44.9Dart 3.12.2 |
| **RISE UAT**Compared last, not ranked | `com.mosl.mobile.uat` | 6.1.13(UAT-3) | FlutterSame Flutter and Dart as RISE | 3.44.2 to 3.44.9Dart 3.12.2 |

Kite's mutual funds live in the separate Coin app (`com.zerodha.coin`, also Flutter and also installed), so Coin is measured for the MF screen.

RISE UAT is the team's optimised test build of the same app. It is measured after the seven apps and is not part of the ranking. See [RISE UAT](#uat).

## Which screens, on which apps

These are the dashboard tabs you listed for each app after login. If an app has no matching tab, the cell is N/A and never counts as zero. Where apps show similar data under different tab names, the comparison is made section by section.

| App | Screens we measure | Note |
| --- | --- | --- |
| RISE | Home, Stocks, F&O, MF, Research, Commodity, US Stocks, StratX | Eight tabs, returned by the landing-page call in the 21 Oct log. The launch config also lists five bottom-bar items: Explore, Watchlist, More, Trades, Portfolio. That the eight tabs sit inside Explore is inferred from the log order and needs a look on the phone. |
| INDmoney | Stocks, F&O | Its US Stocks tab is not on your list. |
| Groww | Explore | Scroll the whole screen and record every section and the data it shows. Stocks, F&O or MF sections inside Explore are compared with the matching tabs on the other apps. |
| SAHI | F&O, Stocks, Commodities, ETFs | The only app with an ETFs tab on your list. |
| Angel One | Stocks, F&O, Mutual Funds, Commodity |  |
| Kotak Neo | Stocks, F&O, Mutual Funds |  |
| Kite | Not on your list | Your first note marks Kite as done. My assumption: it stays in the launch, RAM, storage and bandwidth runs, with no screen tests unless you add them. Its mutual funds live in the separate Coin app. |
| RISE UAT | Same screens as RISE | Measured last, in a pass after the seven apps. Not ranked. |

### Where the comparisons line up

| Screen type | RISE | INDmoney | Groww | SAHI | Angel One | Kotak Neo |
| --- | --- | --- | --- | --- | --- | --- |
| Home or Explore | ● | – | ● | – | – | – |
| Stocks | ● | ● | ? | ● | ● | ● |
| F&O | ● | ● | ? | ● | ● | ● |
| Mutual funds | ● | – | ? | – | ● | ● |
| Commodity | ● | – | ? | ● | ● | – |
| ETFs | – | – | ? | ● | – | – |

● on your list, will be measured – not on your list, N/A ? may appear as a section inside Groww's Explore, to confirm by scroll capture

RISE's Research, US Stocks and StratX tabs are measured and described, but there is nothing on the other apps' lists to score them against. Whether an app shows a personalised section depends on that account's holdings, so those sections are flagged and not compared on content.

## Comparing section by section

Screens with different names often carry the same data. A Stocks tab on one app and the Explore screen on another can both open with an indices strip and a list of most-traded stocks. So each screen is cut into sections, and sections of the same type are compared across apps.

### From a screen to a section table

1. **Scroll capture.** A script swipes a fixed distance, takes a screenshot after each swipe and stops at the bottom. It is its own pass, because screenshots slow an app down.
2. **Name every section** as the app shows it, with its position and screenshot. For Groww's Explore this inventory is the main output.
3. **Give each section a type** from the list on the right. Sections of one type on different apps are compared. A section only one app has is described and not scored.
4. **Record what it holds:** number of data points, live or static, and whether it changes with the account.
5. **Time it,** as in the table below.

### Section types: a starting list

Indices stripWatchlistMarket moversMost tradedTrendingSectors and themesOption chain entryF&O moversMF collectionsTop funds and SIPCommodity pricesETFsExpert picksIPOsNews and insightsPortfolio snapshotBanners and offersLearn

Only four of these are seen so far, all on RISE: indices, trending stocks, expert picks and most traded. The rest is my guess from common broker layouts. The scroll capture corrects the list before any section is scored.

### What RISE's own log gives for Home, section by section

One run on 21 Oct, with the DNS filter on, so it is directional. Which section each call feeds is inferred from the endpoint name. Start times are measured from the first Explore call.

| Section, as I read it | Call | Starts | Takes | Times sent |
| --- | --- | --- | --- | --- |
| CMS content (banners or promos, my guess) | `cmsapi/v2/api/Explore/Home` | +0.00 s | 516 ms | 2× |
| Layout, the order of sections | `Explore/SectionsOrder?segment=Home` | +0.01 s | 316 ms | 1× |
| Indices | `Explore/Stocks?sections=Indices` | +0.01 s | 507 ms | 3× |
| Trending stocks and Expert picks | `Explore/Home?sections=TrendingStocksOnMo&sections=MoExpertPicks` | +0.01 s | 585 ms | 1× |
| Most traded | `Explore/HotStocks?type=MostTraded&exchange=0` | +0.59 s | 261 ms | 1× |

Four of the five calls start within 10 ms of each other, so the sections load in parallel. Most traded starts about 0.6 s in, within 1 ms of the Trending call finishing, which suggests it waits for that call. The log does not say. The last Explore call ends about 0.85 s after the first one starts. That is network time only, and rendering comes on top.

Three of the 27 launch calls repeat an earlier request: Indices three times within 24 ms, and the CMS Home call twice. Each copy has its own start time, so they are separate requests and not one log line printed twice. The log does not say which widget sent each copy.

### What we record for every section

| Measure | How | Applies to |
| --- | --- | --- |
| Time to content | From the tap to the moment the section's area stops changing. ffmpeg crops the recording to that area and runs `freezedetect` on it. | Sections visible on arrival |
| Pop-in on scroll | From the section entering the screen to real data replacing the placeholder, at a fixed scroll speed. | Sections below the first screen |
| Data points | Count of distinct values shown: symbols, prices, percentages, labels. Counted from the screenshots against a fixed rubric. | All sections |
| Live or static | Whether the values change during a 30 s watch. | All sections |
| Personalised | Whether it changes with the account's holdings or watchlist. | All sections |
| Source call | Endpoint, time, size and cache hit or miss, read from the log. | RISE only. For the others, hosts and bytes per screen from PCAPdroid. |

Prices tick while we watch, which can keep a section's area from ever looking still. The pilot checks the freeze test against frame-by-frame reading and sets how much pixel change it ignores.

## What gets measured

Your seven parameters, plus launch time and bandwidth. Each one has a headline number, a method, and the tool that produces it.

Launch

### App launch

Headline

Cold and warm launch: time to first frame and time until home is usable, in ms. The MPIN or biometric step is excluded.

How

`am start -W` for first frame, plus screen-recording timed from the moment auth is submitted to a finished home screen.

Tools

adb, ffmpeg frame analysis

On Flutter apps the system's "Displayed" time only marks the first frame, often a splash. That is why the recording is the headline.

1

### Load time and API calls

Headline

Per screen and per section: tap to first content, and tap to visually complete (ms).

Also

- **RISE:** call count, serial vs parallel, total and slowest call, KB, CDN hit rate, cache hit or miss
- **Competitors:** connections, hosts and bytes at screen open

Tools

Screen recording + ffmpeg, RISE log parser, PCAPdroid

2

### Scrolling and gestures

Headline

Effective FPS, jank % and p50 / p90 / p99 frame time over 10 identical swipes per list screen.

How

Perfetto frame timeline records every frame the display compositor handles. Swipes use fixed distance and speed so every app gets the same gesture.

Tools

Perfetto, `input swipe`

The screen switches between 60 and 120 Hz, so one rate is fixed for the headline run and the rate each app received is read from the trace. Details are under [scroll and response](#devtools).

3

### Screen updating

Headline

Price updates per minute for the same symbol on every app, time to resume live ticks after 60 s in the background, and recovery after a network drop.

How

Recording of the price region. RISE also logs its socket state, so a stall can be matched to its cause.

Tools

Screen recording, RISE socket logs

Runs only while the market is open: equity 9:15 to 15:30 IST, commodity evening session to 23:30 IST.

4

### Offline caching

Headline

Per screen with airplane mode on, scored 3 = cached data shown, 2 = skeleton or placeholder, 1 = error message, 0 = crash or hang.

Also

Is stale data labelled? Time to show cached content, and auto-recovery time after reconnect.

Tools

`cmd connectivity airplane-mode`, cold relaunch, recording

The 0 to 3 scale is a proposal for you to change before testing.

5

### Data pointers

Headline

Per screen: distinct data points above the fold and in total.

Also

Personalisation signals (holdings-aware content, recently viewed, recommendations), promo and banner count, and taps needed for key journeys: buy a stock, open an option chain, start a SIP.

Tools

Full-page screenshots counted against a written rubric

The rubric is fixed before the first screenshot is counted, so every app is scored the same way.

6

### External SDKs

Headline

SDK list by category (analytics, attribution, crash, performance monitoring, CRM, security), and the third-party calls made before first content.

Also

Share of bytes going to third parties and native library count.

Tools

`apkanalyzer` on the pulled APKs, PCAPdroid host list, logcat tag inventory

Seen so far in RISE's logs: Firebase Performance, Firebase Sessions, Datadog, NotifyVisitors, AppsFlyer.

7

### RAM and storage

RAM

PSS, Java heap, native heap and graphics at three checkpoints: the MPIN screen, home after 30 s idle, and after visiting every screen.

Storage

Fresh = installed APK size. Logged in = app + data + cache as the system reports it.

Tools

`dumpsys meminfo`, `apkanalyzer`, Settings → App info

No app is cleared or logged out, so there is no true pre-login RAM reading. The MPIN screen stands in for it.

BW

### Bandwidth

Conditions

For every block of runs: Wi-Fi or mobile, signal strength, link speed, and a measured speed test.

Data used

MB received and sent per app and per screen, from each app's byte counters before and after the run.

Tools

`dumpsys netstats`, `dumpsys wifi`, PCAPdroid cross-check

The system keeps these counters in 2-hour buckets, so we take the difference inside the open bucket. The pilot checks this against PCAPdroid's byte count.

## How scroll and screen response are measured

Everything below comes from developer options and adb commands, so no app has to be modified. "Checked" means the command returned data on your phone today. None of it has been run against a real test yet.

| What we want | Option or command | What it gives | On this phone |
| --- | --- | --- | --- |
| Screen response, tap to content | `screenrecord` or scrcpy `--record`, read with ffmpeg `freezedetect` and `scdet` | When the screen starts changing after the tap and when it stops. The same method for all seven apps. | Tools foundffmpeg has `freezedetect`, `scdet`, `crop`, `mpdecimate` and `signalstats`. No recording made yet. |
| The moment of the tap | Show taps (`show_touches`), Pointer location | A dot on every touch, so the recording shows the exact frame of the tap. | Off nowBoth read 0. Show taps is switched on for runs. |
| Frame times and jank, summary | `dumpsys gfxinfo <package>`, with `reset` before each test | Total frames, janky %, p50 / p90 / p95 / p99 frame time, missed vsyncs, high-input-latency count. | PartlyReturned numbers for Groww, Angel One, INDmoney and Kotak Neo. Counters run from process start, so they are reset per test. For the Flutter apps it is not known whether these are Flutter's frames or only the Android window's. |
| Frame by frame, native apps | `dumpsys gfxinfo <package> framestats` | One row per frame: intended time, deadline, completion and frame interval. | CheckedRows returned for Groww. Its frame interval was 8.3 ms, which is 120 Hz. |
| Frames and jank on every app, Flutter included | Perfetto trace, frame timeline source | Each frame shown for each app's layer, the jank type, and the refresh rate in force. | PartlyThe data source is listed on the phone. The trace reader is not on the Mac yet. The Perfetto web viewer is the fallback. |
| Refresh rate each app gets | `dumpsys display` (`mActiveRenderFrameRate`), frame interval in `framestats` or the trace | The rate the screen actually ran at. | VariesRead 60 Hz in one check and 120 Hz in a later one. |
| Animation speed | `window_animation_scale`, `transition_animation_scale`, `animator_duration_scale` | Stretches or removes every animation. | CheckedAll read 1.0. They stay at 1.0 so timings match what users see, and the values go on the Env sheet. |
| CPU and memory while scrolling | `dumpsys cpuinfo`, `dumpsys meminfo` before and after | CPU % per app, and RAM growth over a scroll test. | Checkedcpuinfo gave a per-app line (Kotak Neo at 29% in one sample). meminfo worked on RISE and Kotak Neo earlier. |
| Crashes and restarts | `dumpsys activity exit-info <package>` | Past process exits with time and reason, so a crash or kill during a test is not missed. | CheckedReturned records for Kotak Neo. |
| Heat and charging | `dumpsys thermalservice`, `dumpsys battery` | Thermal status, battery temperature, charging state. | ChargingThermal status 0. The phone is charging over USB (84%, about 33 °C). See the protocol. |
| On-screen frame bars | Profile GPU rendering (`debug.hwui.profile`) | Bars drawn for each frame, native apps only. | Not setVisual cross-check only. The numbers above are the measures. |

Not used: Strict mode flashes, layout bounds and forced MSAA. They colour the screen and give no number.

### Fix the refresh rate before comparing frame rates

On this phone the screen switches between rates, and an app held to a lower rate has a bigger frame budget (16.7 ms at 60 Hz, 8.3 ms at 120 Hz). Frame rate and jank % are only comparable when every app runs at the same rate.

- The display service read 60 Hz in one check and 120 Hz in another today. The panel supports 120 Hz.
- One frame sampled from Groww had an 8.3 ms interval, which is 120 Hz.
- INDmoney's counters showed 55.6% janky frames while its slowest 1% of frames took 13 ms. That fits an 8.3 ms budget. I have not confirmed it.
- Zerodha's own engineering blog says Flutter apps did not run at a high refresh rate by default on Android, and that adaptive panels made this harder. The post is undated and may not describe current Flutter, but it is a reason to check, not assume.

The headline scroll run uses one fixed rate for every app, if the phone can hold it. The rate each app actually received is recorded from the trace, and the trace judges each frame against its own deadline. A second pass on the adaptive setting shows what users see day to day.

### Scroll test

- Two gestures sent with `input swipe`: a slow drag of about 1,000 px over 400 ms, and a fast fling of about 1,000 px over 80 ms. 1,000 px is about a third of this screen's 3,120 px height. These are starting values for the pilot to tune.
- Ten of each per list screen, from the top, at the same coordinates on every app.
- For each test: a `gfxinfo` reset and dump, a Perfetto trace, `meminfo` before and after, a CPU sample every second, and a recording.
- Reported: p50, p90 and p99 frame time, jank %, longest frame, refresh rate received, placeholders seen while scrolling, CPU % and RAM growth.
- Injected swipes lack a finger's pressure and speed curve. They are identical for every app, so the numbers compare apps and do not describe the feel of scrolling by hand.

### Screen response test

- Tap the tab at fixed coordinates, noted once per app from a screenshot.
- Time from the tap dot to first content, and to a settled screen, for each section.
- Two opens per screen: the first one after launch, and a revisit within 60 s. The revisit shows what each app keeps in memory.
- Cold-state runs follow the protocol: force-stop, and a person types the MPIN.
- Every run also logs charging state, thermal status and the refresh rate in force.

### Settings I would change during runs, and put back

| Setting | Now | During runs |
| --- | --- | --- |
| Show taps | Off | On |
| Display refresh rate | Switching between 60 and 120 Hz | Fixed to one value, chosen with you. Whether it holds on this phone is tested in the pilot. |
| Wireless debugging (optional) | Off | On, so the phone can be unplugged |
| Animation scales, Private DNS | 1.0 and Automatic | No change |

## Can we time API calls through logcat?

For RISE, yes, in full. For the competitors, no. Their release builds do not write request details to the log.

RISE: yes

Every API call is logged as a JSON line with method, URL, status and `duration_ms`. Calls through the CDN also carry cache, edge and origin timings. A text line next to it adds the response size.

```
{"ts":"…18:05:35.177","level":"SUCCESS","type":"API",
 "method":"POST",
 "url":".../TradingApiV2/api/Init",
 "status":200,"duration_ms":252,
 "api_version":"4.0",
 "cdn":{"cache":"MISS", ...}}
```

The `ts` field is the moment the request starts. It matches the text log's response line to within 1 ms once the duration is added.

Competitors: no

What each app's log showed during your run, filtered to that app's process:

- **INDmoney:** image CDN and analytics hosts only (70 and 4 lines), no timings
- **Groww:** no URLs and no timings
- **Angel One:** 2 URL lines, no timings
- **SAHI:** networking classes load, no request lines
- **Kotak Neo:** read after launch: 587 log lines, no URLs and no timings. A 40-second PCAPdroid capture while the app launched and was browsed shows 17 hosts, 77 TCP connections and about 813 KB on the wire. Request paths stay encrypted, so only hosts, timing and bytes are visible.
- **Kite:** not running when checked, so not read

Android apps ignore user-installed certificates, so request contents cannot be read without modifying the apps. We measure what a user feels instead.

### What replaces it for the comparison

Same for all 7

**Screen recording.** The time from tap to the frame where the screen stops changing. Every app is timed by the same rule, so this is the headline load number.

Hosts, bytes

**PCAPdroid.** A per-app capture that works without root. It shows which hosts were contacted, when, how many connections opened and how many bytes moved. Request-level timing from it is an estimate and is labelled so. It runs in a separate pass, because its VPN adds overhead.

RISE only

**Log parser.** Reads the JSON lines and cache messages into a per-screen table, so we can show how much of RISE's load time is the network and how much is the app.

### What the RISE log gives you: the first six calls of a launch

From your run on 21 Oct, with the DNS filter on, so treat it as directional. The log held 27 calls in about 40 seconds.

CallStartms

POST /TradingApiV2/api/Init+0.00 s

252

POST /userlogin/api/Login/2FA+1.53 s

952

GET /TradingApiV2/api/User/Config+2.48 s

202

GET /user/api/UserManagement/GetUserProfile+2.48 s

71

GET /cmsapi/v2/api/AppLaunch/Config+2.69 s

41

GET /cmsapi/v2/api/AppLaunch/PinnedMessage+2.69 s

46

The 1.3 s gap after Init is most likely the biometric prompt, since the 2FA request carries `biometricValidated: true`. The last two calls start the instant User/Config finishes, so they appear to wait for it. The longest chain is Init, 2FA, User/Config, then PinnedMessage: about 1.45 s of network time. These are the kinds of answers the parser will give for every screen.

## What the competitors say about their own performance

Everything I could find that the six apps have published about their speed, size or reliability, each tied to the test that would check it. None of it was measured by us unless the row says so.

| App | What they claim | Kind | Source | How we test it |
| --- | --- | --- | --- | --- |
| Kite | Android APK of about 10 MB for one CPU architecture, kept small by avoiding heavy dependencies and drawing graphics as SVG. | Number, self-reported | [Zerodha Tech blog](https://zerodha.tech/blog/from-native-to-react-native-to-flutter/)Undated. It mentions Dart 2.15 (December 2021), so it is from late 2021 or later. | 7 Storage. On your phone Kite is 17.3 MB across all 11 splits, so we compare the base APK plus one architecture split. |
| No third-party user-profiling or marketing SDKs in the app, stated as a product philosophy. | Design claim | Same blog | 6 SDK inventory and the hosts the app contacts. |  |
| Very low network use: a binary WebSocket stream for price ticks and ETag caching on repeated API calls, so the app stays usable on bad networks. | Design claim | Same blog | BW MB per screen, and 4 offline behaviour. |  |
| Moved off React Native because price updates lagged on mid-range Android phones. Each stock now has its own update stream and only the changed number redraws. | Design claim | Same blog, and [a write-up of the 2019 Kite 3 talk](https://ajinasokan.com/posts/flutter-zero-to-production/) | 3 price updates per minute, and 2 scrolling on a busy watchlist. |  |
| Frame drops appear only the first time a navigation transition runs (shader compilation), and are worse on iOS. Animations are kept to a minimum. | Self-reported limit | Same blog | 2 Compare the first and the repeat opening of the same screen. |  |
| Kite 3 launched in July 2019 with significant speed improvements, and gave no figures. | Qualitative | [Zerodha Z-Connect](https://zerodha.com/z-connect/kite/introducing-the-kite-3-mobile-app), 1 Jul 2019 | Context only. Launch and load times are measured for every app anyway. |  |
| 2019 scale: about 30 million ticks a second from the backend to about 300,000 live users, over 1 million active devices and about 3 million orders a day. | Number, dated | The 2019 talk write-up | Not testable from a phone. Context only. |  |
| Groww | No performance claim found. Its engineering blog on Medium returned a block page to my automated fetch, and my searches turned up no Groww post about app speed, startup or size. | Not found | [medium.com/groww-engineering](https://medium.com/groww-engineering)Blocked for me, not read. | Needs a manual read in a browser. |
| Angel One | October 2022, "Angel One 2.0": users get faster interactions on charting, order handling, settlement and reporting, with zero tolerance for crashes, bugs and slowness. | Qualitative | [Angel One blog](https://www.angelone.in/blog/android-product-update-october-2022), Oct 2022 | 1 2 Load and scroll on the chart and order screens. |
| February 2024, #RahoHameshaSuper campaign: the second SuperApp edition promises better speed, security and reliability, including quick execution on low networks. | Qualitative | [BestMediaInfo](https://bestmediainfo.com/2024/02/angel-one-highlights-superapps-speed-security-and-reliability-features), Feb 2024 | Optional low-network pass. It needs a throttled connection, which the phone alone cannot give. |  |
| INDmoney | Price ticks from the exchanges to the app in under 50 ms. Order processing under 20 ms at peak. Withdrawals in about 3 seconds. About 1 million ticks a minute on a typical day, with spikes of up to 40%. | Number, vendor case study | [AWS case study](https://aws.amazon.com/solutions/case-studies/indmoney-case-study/) for INDstocksUndated in my copy. Server side. | 3 price updates per minute for the same symbol. The phone cannot verify the 50 ms or 20 ms. |
| Over 95% of price ticks reach devices in under 200 ms. Over 76% of order updates reach devices in under 50 ms. 90% of orders reach the exchange within 150 ms of the tap. Trade-screen p95 load time is down by more than 96%, with no before or after value. Price packets shrank from 500 B to 180 B. | Number, self-reported Re-check wording | [INDmoney engineering post](https://www.indmoney.com/blog/stocks/indstocks-delivers-super-fast-trading)The site blocked direct download, so these figures came through a summarising fetch tool. | 1 trade-screen load, 3 price updates, and BW bytes per screen. |  |
| Kotak Neo | No app performance claim found. A "rebuilt for speed" case study matched my search, but it is about the Kotak Securities website, so it is excluded. The "Switch to Neo" page loads its text in the browser and I could not read it. The search tool reported only customer testimonials about speed. | Not found | [QED42 case study](https://www.qed42.com/work/enhanced-security-performance-for-kotak-securities)Excluded: website, not the app. | Needs a manual check of the Neo page and the latest release notes. |
| SAHI | P95 latency of 6.61 ms from its order system to the exchange, and a mean of about 5.92 ms (4.28 ms to the order-management system, 0.20 ms for the risk check, 1.45 ms to the exchange). Measured over 9,089,472 real orders from 13 to 30 March 2026, and published on 16 May 2026. | Number, self-reported | [SAHI blog](https://www.sahi.com/blogs/lightning-fast-order-execution-fno-trading), June 2026Server side. States sample size, dates and percentile. | Not testable from the phone: the clock starts at SAHI's server, after the tap. We compare only the in-app side. |
| Describes itself as a high-performance trading app for active traders, with in-house charts. No app-side figure. | Qualitative | SAHI's Google Play listing | 2 3 Chart scrolling and price updates. |  |

### Read this before quoting any of it

- Most published numbers describe the server path, such as how fast a price tick reaches the phone or an order reaches the exchange. They say little about launch, scrolling or screen load, which is what this benchmark measures.
- No source I could read gives a launch time or a scroll frame rate for any of the six apps. The only screen-load figure is INDstocks', and it is a relative drop with no before or after value.
- Almost everything is self-reported. SAHI's post is the most open: it states the sample size, the dates and the percentile.
- INDmoney's two sources set different bars for the same thing: price ticks under 50 ms in the AWS case study, but 95% under 200 ms in the engineering post. Quote either one only with its definition.
- I found no independent test with a stated method. The comparison articles in the search results gave no measured latency or crash data, judged from their snippets. I did not open them.
- Kite's figures are from 2019 or from an undated post, so they may not describe the current app.

### Measured today: installed app size

Total size of each app's APK and splits as installed on your S25 Ultra, read over adb. Play Store download sizes will differ. Kite's separate Coin app is 20.7 MB.

AppBuildMB

RISEFlutter

123.5

Angel OneNative

118.7

Kotak NeoFlutter

116.9

INDmoneyFlutter

99.5

GrowwNative

93.9

SAHIFlutter

87.0

KiteFlutter

17.3

### Measured today: Play Store rating

User sentiment, not speed. Shown for context, read from each Play Store listing today.

| App | Rating | Ratings |
| --- | --- | --- |
| Groww | 4.79 | 2.52M |
| INDmoney | 4.57 | 463k |
| SAHI | 4.51 | 34.6k |
| Kotak Neo | 4.49 | 217k |
| Kite | 4.42 | 394k |
| Angel One | 4.40 | 1.93M |
| RISE | 3.99 | 145k |

### What I could not read

- Groww's engineering blog returned a block page and Angel One's did not respond, so neither was read. Both may hold performance posts.
- INDmoney's blog returned a block page to direct download. The INDstocks post figures above came through a summarising fetch tool, so check them against the post before quoting.
- Kotak Neo's "Switch to Neo" page has no text in its downloaded HTML, because the browser builds it.

## The Flutter builds, side by side

Five of the seven apps are built with Flutter, and Kite's separate mutual-fund app (Coin) is too. Groww and Angel One are native. The Dart version comes from each app's Flutter engine file and is matched to a Flutter release with Flutter's own release list. The settings come from each app's manifest. Everything was read from the installed apps on 21 Oct 2026.

| App | Flutter | Dart | Lines behind | Renderer setting | Android min / target | Dart binary / assets (MB) | Build and stack |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **RISE** | 3.44.2 to 3.44.98 patch releases share this Dart build. The repo pins 3.44.4, which is probably the one. | 3.12.2 | 1 | Off (opted out)Installed build. Newer source turns Impeller on at launch for most phones. | 28 / 37Declared. The variant Play sent to this phone says 32. | 50.6 / 37.3 | 5/9 (56%) |
| **SAHI** | 3.44.2 to 3.44.98 patch releases share this Dart build, so the exact one can't be told apart | 3.12.2 | 1 | Off (opted out) | 24 / 36 | 35.4 / 22.5 | 5/9 (56%) |
| **Kite** | 3.41.3 or 3.41.4 | 3.11.1 | 2 | Off (opted out) | 24 / 36 | 14.4 / 1.4 | 4/9 (44%) |
| **Coin (Kite MF)** | 3.41.5 | 3.11.3 | 2 | Off (opted out) | 24 / 36 | 9.4 / 1.1 | not scored |
| **Kotak Neo** | 3.38.10 | 3.10.9 | 3 | On | 29 / 36 | 51.6 / 41.6 | 4/9 (44%) |
| **INDmoney** | 3.38.9 | 3.10.8 | 3 | Default (key absent) | 24 / 36 | 10.9 / 2.0 | 5/9 (56%) |
| **Groww** | n/a | n/a | n/a | n/a | 32 / 36Unconfirmed, see below | n/a | 1/4 (25%)provisional |
| **Angel One** | n/a | n/a | n/a | n/a | 24 / 35 | n/a | 2/4 (50%) |
| **RISE UAT**not ranked | 3.44.2 to 3.44.9Same Dart build as RISE | 3.12.2 | 1 | Off in the manifest, on at launchThe launch-time choice is in this build, and the source rule gives Impeller on for this phone. Predicted, to be confirmed from the launch log. | 28 / 37 | 52.1 / 37.5 | 7/9 (78%)renderer points predicted |

The current stable Flutter is 3.47 (8 Oct 2026). A new minor line arrives about every quarter, so "1 line behind" means the previous quarter's release. Coin is scored with Kite, not on its own. Dart binary and assets are uncompressed sizes inside the app. The minimum Android column shows the declared minimum where it is known. Play can raise the value in the variant it delivers to newer phones, so the manifest on the phone is not always the declared one. See the note on RISE below.

RISE UAT is shown for reference only. It is left out of the points table and the pairs below, because it is the same app as RISE. Scored the same way, counting the launch-time renderer choice, it earns 7/9 against production RISE's 5/9. Both builds declare a minimum Android of 28, so the two extra points both come from the renderer. The renderer points are a prediction from the source rule for this phone, until UAT's launch log confirms it.

### How "Build and stack" is scored

| Point | Applies to | Rule |
| --- | --- | --- |
| **S1** Target Android | All 7 | 37 = 2, 36 = 1, 35 or lower = 0 |
| **S2** Minimum Android | All 7 | 24 or lower = 2, 25 to 29 = 1, 30 or higher = 0. Lower means more phones can install it. Scored on the declared minimum. A store can raise the value in the variant it delivers to newer phones, so the installed manifest is not always the declared one. |
| **F1** Flutter currency | Flutter apps | Current line = 3, then one point less per line behind, down to 0 |
| **F2** Renderer in effect | Flutter apps | Impeller on or left at default = 2, opted out = 0. A launch-time choice in the app's own code counts over the manifest. |

An app's score is the points it earns divided by the points available to it: 9 for a Flutter app, 4 for a native app. F2 is scored for the test phone, because a launch-time choice can differ by chipset and Android version. Groww and Angel One are not marked down for Flutter facts that do not exist. The point carries 10% of the overall score, the same as each of the nine measured parameters. The thresholds and weights are my proposal and can change before the runs.

### Points earned today

| App | S1 | S2 | F1 | F2 | Earned | Score |
| --- | --- | --- | --- | --- | --- | --- |
| **INDmoney** | 1 | 2 | 0 | 2 | 5 of 9 | **56%** |
| **RISE** | 2 | 1 | 2 | 0 | 5 of 9 | **56%** |
| **SAHI** | 1 | 2 | 2 | 0 | 5 of 9 | **56%** |
| **Angel One** | 0 | 2 | n/a | n/a | 2 of 4 | **50%** |
| **Kite** | 1 | 2 | 1 | 0 | 4 of 9 | **44%** |
| **Kotak Neo** | 1 | 1 | 0 | 2 | 4 of 9 | **44%** |
| **Groww** | 1 | 0\* | n/a | n/a | 1 of 4 | **25%** |

Six of the seven apps land between 44% and 56%, so this point moves the overall ranking little. RISE is scored at its declared minimum Android of 28. A build that turns Impeller on would earn RISE two more points on F2, which is what the UAT build does (7/9, 78%). * Groww's S2 uses its installed 32 until its declared minimum is confirmed. Its score would sit between 25% and 75% depending on the answer.

### One against another

Every pair of the five Flutter apps. A name is the winner on that point and "tie" means equal points. The last column counts points won by each side, ties left out. Pairs with RISE are highlighted.

| Pair | S1 target | S2 reach | F1 Flutter line | F2 renderer | Same Flutter line | Renderer settings | Wins |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **RISE** vs **Kite** | RISE | Kite | RISE | tie | no | off / off | 2 to 1 |
| **RISE** vs **INDmoney** | RISE | INDmoney | RISE | INDmoney | no | off / default | 2 to 2 |
| **RISE** vs **Kotak Neo** | RISE | tie | RISE | Kotak Neo | no | off / on | 2 to 1 |
| **RISE** vs **SAHI** | RISE | SAHI | tie | tie | yes | off / off | 1 to 1 |
| **Kite** vs **INDmoney** | tie | tie | Kite | INDmoney | no | off / default | 1 to 1 |
| **Kite** vs **Kotak Neo** | tie | Kite | Kite | Kotak Neo | no | off / on | 2 to 1 |
| **Kite** vs **SAHI** | tie | tie | SAHI | tie | no | off / off | 0 to 1 |
| **INDmoney** vs **Kotak Neo** | tie | INDmoney | tie | tie | yes | default / on | 1 to 0 |
| **INDmoney** vs **SAHI** | tie | tie | SAHI | INDmoney | no | default / off | 1 to 1 |
| **Kotak Neo** vs **SAHI** | tie | SAHI | SAHI | Kotak Neo | no | on / off | 1 to 2 |

After the runs, each pair also gets the measured columns: scroll jank %, p99 frame time, cold launch and graphics memory. Then the table can say whether the build facts explain the gap or the app code does.

### What the data says

- **RISE and SAHI are a controlled pair.** Both use Dart 3.12.2 (built 9 Jun 2026) and the same renderer setting. Any gap between them in the measured runs comes from app code, not from Flutter.
- **RISE is on the newest Flutter line of the Flutter apps**, one behind the current release. The installed build (6220) renders with Skia. Its manifest says `EnableImpeller=false`, but that is only a default: source from 7 Oct 2026 lets `MainActivity` switch Impeller on at launch for Android 11 and above, except MediaTek and Exynos phones. The 6220 build does not have that code, and this phone (Snapdragon 8 Elite, Android 16) would get Impeller from a build that does. So "RISE uses Skia" holds for this build only. Kite, Coin and SAHI opted out in their manifests too. Kotak Neo sets Impeller on and INDmoney leaves it at the default, which I expect to mean on for this Flutter version but have not confirmed. Other apps could override their manifest at launch as well, so the pilot reads each app's launch log. RISE's own launch log warns that the opt-out options "are going to go away in an upcoming Flutter release".
- **RISE's minimum Android is 28, and the 32 seen on this phone comes from how Play delivered the app.** The Play-installed 6.2.09 (build 6220) shows 32 in the system's package record and in all three of its files. The Play listing, as the team read it, says 28+, and the Gradle file says 28 at every commit. The installed files carry Play's bundle markers and sparse-encoded resource tables (65 of 89 resource types). That is the packaging of a variant for Android 12L (API 32) and newer, and it is why the manifest value is 32 on this Android 16 phone. Groww shows the same pair, 32 with sparse tables (71 of 95). No other app does, and the sideloaded UAT builds show their normal minimum with no sparse tables. I could not see Play's own variant list, so this is an inference from that pattern. A phone on Android 9 to 11 would be expected to receive a build with minimum 28. Kotak Neo starts at Android 10 and Kite, SAHI, INDmoney and Angel One at Android 7.
- **RISE ships a heavy Flutter payload:** 37.3 MB of assets and a 50.6 MB Dart binary. Kotak Neo is similar (41.6 and 51.6). Kite is at 1.4 and 14.4.
- **INDmoney may be only partly Flutter.** Its Dart binary is small (10.9 MB) and its launch log showed no Flutter lines, so some screens may be native. Its score applies to the Flutter parts.
- **RISE and Kotak Neo show only 5 or 6 Dart package names** inside the app, against 38 to 170 for the others. That may mean their Dart code is obfuscated. I have not verified it, and it is not scored.

### What was checked, and what is still open

| Check | Result |
| --- | --- |
| Do the Flutter engine and the app's code come from the same build? | Yes for all six Flutter apps: both files carry the same snapshot hash. |
| Does the Dart to Flutter match hold up? | Each Dart build is dated 1 to 8 days before the first Flutter release that ships it, and every release is older than the app's install date. |
| Which renderer runs at launch? | Open The manifest shows a default, and an app can override it at launch, as RISE's newer source does. RISE's own log confirms Skia for the installed build, which has no such code. The other apps need a cold start each, which the pilot covers. The check for a launch-time choice recognises RISE's own code only, so the other apps' launch logs are what settle it. UAT's renderer is predicted on from its source rule and is confirmed once its launch log is read. |
| Why does RISE's installed minimum Android (32) differ from its source (28)? | Likely explained Play delivered a variant for Android 12L and above, with the minimum raised to 32. The Play listing reads 28+. Not proven from Play's side. Play Console's bundle explorer, or the APK that Play delivers to an Android 11 phone, would settle it. |
| Do RISE's `ForceGLES2` and `EnableVulkan` settings do anything? | Closed No. A 9 Oct commit message and the Gradle comment in the repo state that only `EnableImpeller` is a real engine flag, and that the other two are kept only so manifest merges do not change. That is the repo's own note, which I did not test separately. |
| Is the Dart code obfuscated? | Open Needs a symbol-name check. |

These facts describe the builds on the phone today. They are read again at the start of the full runs, because an app update changes them.

## RISE UAT: the optimised build, compared last

The team has made performance changes that are meant to be in the UAT build. It is the same app as RISE, so it is not ranked against the six competitors. It is measured after the other seven apps and shown in the last row of every table. Its job is to show whether the changes move the numbers against production RISE.

### How it is compared

1. **Last in the queue.** The seven ranked apps are measured first. If time runs short, UAT is the part that gets dropped.
2. **Back to back with production RISE.** In its own final pass, UAT and a fresh run of production RISE alternate, three repeats each, on the same screens and the same network. This keeps the before-and-after gap clear of drift since the main runs. The extra RISE run is my addition.
3. **A difference table, not a rank.** For each parameter the report shows UAT, production RISE and the gap, on the same screens and sections as RISE.
4. **Greyed out of every ranking.** It does not take part in the points table or the head-to-head pairs.

### Which build this is

There are two UAT packages on the phone. `com.mosl.mobile.uat` (6.1.13(UAT-3), installed 21 Oct) is the one the repo's UAT flavor produces, since its Gradle suffix is `.uat`. `com.mosl.superapp.master` (6.1.11(UAT-7)) is not defined anywhere in the repo's Gradle files, so I took it to be an older, separate build and left it out. Tell me if that is the wrong choice.

The version label comes from the repo's version file and says nothing about how new the code is. UAT's Dart binary is larger than production's.

### Production RISE and RISE UAT, as installed

Read from the two installed apps and from the repo on 22 Oct 2026.

| Fact | RISE (Play, build 6220) | RISE UAT (installed) |
| --- | --- | --- |
| Package and version | `com.mosl.mobile` 6.2.09 | `com.mosl.mobile.uat` 6.1.13(UAT-3), build 6101 |
| Installed from | Google Play | The package installer (sideloaded)Play can deliver precompiled-code profiles that a sideloaded build does not get. That could slow UAT's launches a little. Not tested. |
| Install size | 123.5 MB, split by phone type | 152.6 MB, one file holding both ARM versionsNot comparable. Compare the Dart binary and assets below. |
| Flutter and Dart | 3.44.x, Dart 3.12.2 | The same Dart build |
| Dart binary / Flutter assets | 50.6 MB / 37.3 MB | 52.1 MB / 37.5 MB |
| Minimum Android | 28 (Android 9), declaredThe variant Play delivered to this phone shows 32. | 28 (Android 9)Matches the repo's Gradle file. |
| Impeller setting in the manifest | Off | Off |
| Launch-time Impeller choice | Not in the build | In the buildUAT's code contains the log text that choice prints (`hardware=`, `board=`, `soc=`). Production's code does not. This phone (Snapdragon, Android 16) would get Impeller from it, so UAT probably renders with Impeller. To confirm from its launch log. It is counted in UAT's Build and stack score. |
| Environment setting | Release | DebugSee "Read this before comparing" below. |
| Servers | Production | UAT servers by default. Pilot is reachable from a home-screen shortcut, and production is blocked in this build.The addresses are in generated config I did not open. The first UAT capture lists the hosts it really calls. |
| Environment switcher in the app | Absent | PresentFound in the build's Dart code, absent in production's. |
| Build and stack score | 5/9 (56%) | 7/9 (78%)The two extra points come from Impeller on at launch. Both builds declare a minimum Android of 28. The renderer points are predicted for this phone. |

### Optimisations in the repo that this build might hold

From commit messages made after production's version commit (14 Oct). All of these are on the repo head. Which of them are in the installed UAT build depends on the commit it was made from, which I do not know. Only the first row could be checked against the build itself.

| Change | Where it should show | Date (2026) | In the UAT build |
| --- | --- | --- | --- |
| Launch-time Impeller choice: on for Android 11 and above, off for MediaTek, Exynos and older Android | Scroll and frame times, all screens | 7 and 9 Oct | Confirmed |
| R8 code optimisation turned on for release builds | App size, startup | 9 Oct | Not checked |
| Jank fixes on the F&O dashboard (two tiers) | Scroll, F&O | 9 Oct | Not checked |
| Jank fixes on the commodity dashboard (two tiers) | Scroll, Commodity | 12 Oct | Not checked |
| Biometric Skip tap no longer blocks the UI thread: analytics deferred, protobuf response dumps gated | Launch | 16 Oct | Not checked |
| Charts subscribe to ticks without waiting for the page's reply, and the stale-feed probe is gone | Charts, live updates | 15 Oct | Not checked |
| Watchlist and US stock watchlist optimisation | Watchlist screens | 12 Oct | Not checked |
| Jank fixes on the home tab and the stock dashboard | Scroll, Home and Stocks | 8 and 9 Oct | Reverted in the repo |

The reverted row matters: if the team expects Home and Stocks to be faster in UAT, the repo history says those two fixes were taken out again. If you give me the branch or commit, I can check the build against this list.

### Read this before comparing

- **UAT does extra work that production does not.** In UAT's debug environment, requests on the network package's protobuf path also get Dio's log interceptor and a pretty-printing logger. Every response body is also JSON-encoded for an on-device API activity capture. The landing screen shows a debug API-list button. UAT can therefore look slower than the same code would in production, which means the optimisation gains may be understated.
- **UAT talks to UAT servers by default.** Its API and screen-load times include server differences, so they describe the build against UAT and not against production. If Pilot turns out to use production-like servers, a Pilot-mode pass is the closest like-for-like. The first capture will show which hosts each mode calls.
- **The data differs.** The UAT account's holdings, watchlist and market data may not match the production account, so section contents and sizes can differ. Sections are compared by type.
- **The renderer may change at the same time.** If the launch-time Impeller choice is active, any change in scroll smoothness mixes the renderer with the other optimisations. The runs cannot separate them.
- **How results are worded.** UAT results are reported as "UAT build against UAT servers". They are called an optimisation gain only if a production-like pass confirms them.

## First look at RISE

These come from one run on your phone and are signals to confirm, not results. Each row says how the formal runs will settle it.

| Signal | What the log or device shows | How we confirm | Status |
| --- | --- | --- | --- |
| **Private DNS filter** | It was set to `dns.adguard-dns.com` during your run, and RISE's Datadog upload failed with `Failed to connect to browser-intake-datadoghq.com/0.0.0.0`. | Now on Automatic. A pre-run check refuses to start if it goes back to a fixed hostname. | Resolved |
| **Renderer** | The installed 6220 build logs *The application opted out of Impeller*, so RISE renders with Skia there. Newer source (7 and 9 Oct commits) switches Impeller on at launch for most phones, so the next release is likely to change this. Kite, Coin and SAHI opted out in their manifests too. Kotak Neo sets Impeller on, and INDmoney leaves it at the default. | Record the build version on every run. Cold-start each app and read its launch log, then compare jank in the scroll runs. See [Flutter builds](#flutter). | Preliminary |
| **Minimum Android version** | RISE declares 28 (Android 9), which is what the Play listing shows. The build Play delivered to this phone shows 32, because of a variant for Android 12L and above. Kotak Neo needs Android 10, and Kite, SAHI, INDmoney and Angel One go down to Android 7. Groww's 32 looks like the same delivery effect and is not confirmed. | Read "Requires Android" on Groww's Play page, as was done for RISE. | Explained |
| **Flutter payload** | 37.3 MB of Flutter assets and a 50.6 MB Dart binary, both uncompressed. Kotak Neo is similar at 41.6 and 51.6. Kite is at 1.4 and 14.4. | Read again at the start of the full runs. | Measured |
| **Startup lock contention** | 13 `Long monitor contention` warnings in the first seconds, the longest 960 ms, inside obfuscated `secret.jfh.M()` and `NativeInteractor.str498`. | Perfetto trace of five cold starts, then name the SDK that owns those locks. | Preliminary |
| **Login on the launch path** | `Login/2FA` took 952 ms. `User/Config` (202 ms) then gates two more calls. | Repeat in 5 cold runs and report the median. | Preliminary |
| **Cache misses** | *No valid cache found* for `home_dashboard`, `wealth_summary`, `pinned_messages` and `app_launch_config`, with a 7200 s TTL configured. | Launch twice within the TTL. Misses on the second launch are a real gap; on the first they may be expected. | Preliminary |
| **Memory** | 560 MB PSS in one reading, of which 363 MB is graphics. A WebView is pre-warmed for charts by `ChartPrewarmService`. | The same three checkpoints on all seven apps. | Preliminary |
| **Installed size** | 123.5 MB with its splits, the largest of the seven apps on the phone and about 7 times Kite's 17.3 MB. Kite itself states a target of about 10 MB per architecture. | Repeat from the Play Store download size and compare against each app's own claim. | Measured |
| **Repeated requests** | On opening Home, the Indices call was sent three times within 24 ms and the CMS Home call twice. That is 3 extra requests among the 27 in the launch log. | Count repeats per screen over five cold opens, and find which widgets send them. | Preliminary |
| **Logging overhead** | About 2,240 lines in 40 s in a production build. Every API call is logged twice, successful calls also print an empty `{API Failed}` line, and the base URL is doubled in the JSON `url`. | Count log lines per minute for every app. The fix is a logging cleanup. | Hygiene |

## How every run is done

The same steps for every app, so differences in the numbers come from the apps and not from the way we tested.

### Before each block of runs

- Private DNS is not set to a fixed hostname
- Same Wi-Fi network, 5 GHz; signal and a speed test noted
- Battery above 50%. Charging state and thermal status are logged each run. USB charging warms the phone, so wireless debugging is preferred.
- Fixed brightness, Do Not Disturb on, other apps closed
- Logcat buffer raised from 5 MB to 16 MB and streamed to a file
- Touch indicators on, so taps show in recordings
- App versions recorded on the Env sheet

A script checks these and refuses to start if one fails.

### Each run, in order

1. Force-stop the app for a cold run, or leave it in the background for a warm one.
2. Clear logcat, snapshot byte counters, start the screen recording, the Perfetto trace and the log stream.
3. Follow the tap script for that screen. A person types the MPIN; PINs never go into scripts.
4. Wait 10 s for the screen to settle, then stop everything.
5. Save the video, trace, log, memory and byte counters, and write one result row.
6. Rotate the app order on the next repeat to cancel out time-of-day and server load.

A second pass on mobile data covers launch and home only. The PCAPdroid capture runs as its own pass, never during timing runs. RISE UAT is measured last, in its own pass after the seven apps, together with a fresh re-run of production RISE.

## What you get at the end

A report workbook for the team and a published report for leadership, both built from the same measured medians.

### Report workbook

SummaryEnv and networkScreen mapSection mapSection timingLaunch1 Load and API2 Scroll3 Live updates4 Offline5 Data pointers6 SDKs7 RAM and storageBandwidthFlutter stackRISE UAT deltaFindings

Every sheet keeps the raw runs next to the median and p90, so any figure can be traced to its recording.

### Scorecard layout

A mock. The real cells fill from measured medians and show where RISE ranks against the other six on each parameter. The Build and stack column is already filled, from facts read off the installed apps. RISE UAT sits in the last row and is not ranked. The asterisk marks Groww's provisional figure.

| App | Launch | Load time | Scroll FPS | Live updates | Offline | Data pointers | SDKs | RAM and storage | Bandwidth | Build and stack |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| RISE |  |  |  |  |  |  |  |  |  | 56% |
| Kite |  |  |  |  |  |  |  |  |  | 44% |
| Groww |  |  |  |  |  |  |  |  |  | 25%\* |
| Angel One |  |  |  |  |  |  |  |  |  | 50% |
| INDmoney |  |  |  |  |  |  |  |  |  | 56% |
| Kotak Neo |  |  |  |  |  |  |  |  |  | 44% |
| SAHI |  |  |  |  |  |  |  |  |  | 56% |
| RISE UATnot ranked |  |  |  |  |  |  |  |  |  | 78% |

### Report order

1. Scorecard: RISE's rank on each parameter, on one screen.
2. The biggest RISE gaps, each with its root cause: network, rendering or app code.
3. Evidence per parameter, with the recording or trace behind each number.
4. Method and limits.
5. Prepared questions and answers.

## Questions we should expect

Each answer is also in the final report, so nobody has to defend it from memory.

Is a flagship S25 Ultra representative of our users?

No. It hides slowness that a mid-range phone would show. This round gives a like-for-like comparison on one device. We recommend repeating launch and home on a mid-range phone as a follow-up.

How is "load time" defined, and is it fair between Flutter and native apps?

From the tap to the frame where the screen stops changing, read from a recording. The rule is identical for all seven apps. Five of them, including RISE, ship the Flutter engine, so framework alone does not explain a gap.

Do differences between the logged-in accounts skew the results?

They can. Holdings and watchlist size are recorded for each app on the Env sheet, and data-heavy screens are compared per row where that matters.

How much of RISE's slowness is the server and how much is the app?

RISE's logged API time is set against the total screen time from the recording. What is left over is rendering and app logic. The earlier table shows this split for the first six launch calls.

How do we know network variance did not drive the results?

Signal strength and a speed test are logged before every block, the app order rotates on each repeat, and results are medians of five runs. Runs that spread more than 20% are flagged and repeated.

Why can't we see the competitors' API times?

Their release builds do not log requests, and Android apps ignore user-installed certificates, so their traffic cannot be read without modifying them. We report what a user feels from the recording, plus hosts and bytes from PCAPdroid.

RISE showed 560 MB of RAM. Is that high, and why?

We cannot say until the other six apps are measured the same way. In that one reading, 363 MB was graphics. Two possible contributors to test are the pre-warmed chart WebView and the Skia renderer.

Do logging and SDK load slow RISE down?

We measure it instead of assuming it: log lines per minute, SDK count, and the 960 ms startup lock contention, each compared against the other apps.

Were all apps current, and was any ad blocker or DNS filter on?

Versions are recorded on the Env sheet. A DNS filter was on during the first look and has been switched off. A check before every block stops the run if it comes back.

Do the competitors' own speed claims hold up?

Most of what they publish is about the server path: how fast a price tick reaches the phone or an order reaches the exchange. We can check the phone side of that, such as price updates per minute and bytes per screen, but not their server clocks. We found no launch time or scroll frame rate published by any of them, so those two come only from our own runs.

The full list, with sources and what each one tells us, is in [their claims](#claims).

Why compare sections and not whole screens?

The apps name and group their tabs differently. A Stocks tab on one app and Explore on another can open with the same indices strip and most-traded list. Comparing a section with the same type of section on another app keeps the comparison fair. A section only one app has is described and not scored.

Were the apps all at the same screen refresh rate?

Not by default: this phone switches between 60 and 120 Hz. The headline scroll run fixes one rate for every app if the phone allows it, and the rate each app actually received is recorded from the trace.

Is RISE's Flutter version a problem?

Not by version. RISE is on the newest Flutter line of the Flutter apps we checked, one line behind the current release. What stands out is the Skia renderer in the installed build (newer source switches to Impeller), the large Dart payload, and a minimum Android of 28, which is above the 24 that four competitors support. The [Flutter builds](#flutter) section has the side-by-side facts.

Why does the Build and stack point carry only 10%?

It describes how an app is built and does not measure how it feels to use. The nine measured parameters cover what users see. The weights are a proposal and can be changed, and the section shows the points behind each score so a different weighting can be tried.

Why is the UAT build last and not ranked?

It is the same app as RISE, so ranking it would put RISE in the table twice. It is also a test build with its own servers and extra logging. It is measured after the seven apps and shown in the last row, as a before-and-after for the team's optimisations.

Can we say the optimisations worked from the UAT numbers?

Only partly. UAT runs against UAT servers and does extra logging that production does not, so its numbers can hide or exaggerate gains. A clean claim needs the optimised code with release settings against a production-like server. The report states which of these the UAT run had.

What should be fixed first?

The gaps are ranked by size and by how many users hit them. Launch and home come first because every session passes through them.

## Next steps

Nothing is cleared, logged out or changed in any app. The tooling is built after you have reviewed this page.

### Order of work

1. **Review this plan.** Change metrics, scoring or scope here first.
2. **Build the tooling and run a pilot:** one app, three screens, two repeats. Check the video timings by hand and confirm the byte counters.
3. **Run the full matrix** once the pilot passes, with market-hours tests scheduled for the right sessions. RISE UAT goes last.
4. **Produce the workbook and the leadership report.**

### Needs you

- Keep all seven apps logged in, plus Coin for Kite's MF.
- PCAPdroid 2.0.2 is installed. To avoid a tap on every capture, set an API key in its settings before the full runs.
- Type the MPIN or biometric yourself during launch runs.
- Open Groww's and INDmoney's engineering blogs in a browser and send me any post about app speed, startup or size. Both blocked my automated fetch.
- Tell me which branch or commit the UAT build was made from and which optimisations you expect in it, so I can check the build against that list.
- Confirm the UAT build is logged in with an account that has holdings and a watchlist like the production one, and whether a Pilot-environment pass is wanted.
- Read "Requires Android" on Groww's Play page, as you did for RISE. Groww's installed 32 may be a Play variant too, and its score depends on the answer.
- Confirm whether Kite needs screen tests, since your list leaves it out.
- Say OK to the settings changes under [scroll and response](#devtools), and keep the phone free while a run is going.
- Be on hand for the equity live-update runs between 9:15 and 15:30 IST. Commodity can use the evening session.

### My calls to check

- 5 repeats, reported as median and p90.
- Recording-based "visually complete" as the headline load metric.
- The 0 to 3 offline scale.
- MPIN screen as the stand-in for pre-login RAM.
- Mobile-data pass for launch and home only.

Tooling: tshark 4.6.9 is now installed for reading captures. The Perfetto trace processor is not installed on the Mac, so the trace analysis can fall back to the Perfetto web viewer if the corporate firewall blocks the download.

Plan v8 · 21 Oct 2026 · Figures marked preliminary come from one run on the Galaxy S25 Ultra with the DNS filter on.
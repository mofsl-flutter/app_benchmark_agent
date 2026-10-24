# RISE watchlist: issues report

Benchmark: `reports/watchlist/watchlist_mahidhar_OPPO-CPH3009_2026-10-23.xlsx` plus the notes in
`results/watchlist/mahidhar_OPPO-CPH3009/` and `results/_app/mahidhar_OPPO-CPH3009/`.
Device: OPPO CPH3009, Android 17, 120 Hz. App: RISE 6.2.09.
Code read: `mosl-riseapp-repo` at branch `develop/sprint_18_release_pod4_mm_researchhome_fixes_oct21`
(HEAD `63788d1ac8`, working tree; 4 files have uncommitted edits, one of them `trader_network/lib/DIOApiService2.dart`).

Folders analysed:

- `packages/trader_watchlist` (the module: 82 Dart files in `lib/`, ~23,000 lines; 16 test files)
- shared code the watchlist screen depends on: `packages/trader_widgets` (StreamingBaseWidget),
  `packages/trader_home_market` (indices rail), `packages/mo_app_bar` (wealth tile in the header),
  `apps/super_app` (landing header, MainActivity, AndroidManifest), `packages/trader_network`
  (API client and logging), `packages/trader_core` (CleverTap helper, PortfolioSummaryService),
  `packages/trader_search` (add-scrip search), `packages/mo_get_quote` (quote navigation)
- git dependencies from the pub cache: `mosl_broadcaster` 3deab191 (price socket), `mosl_socket_core` 35cd64f0

Lines marked "(verify)" are inferred from the code and need a profiler or the device to confirm.

## 1. Where the app stands (from the benchmark)

| Area | RISE today | Best other app | Gap |
|---|---|---|---|
| CPU on idle Bench 20, live market (C1) | 185.5 % (110.5, 185.5, 188.7) | 22.4 % | 8x, last of 7 |
| Idle redraw, no input (U4) | 39.6 fps | 5.5 fps | 3 of 4 measurable |
| Idle frames identical to previous (U5) | 49.5 % | 1.6 % | 4 of 7 |
| PSS growth over 10 open/close cycles (R9) | +60.0 MB | −0.1 MB | last; next app +19.9 |
| PSS after 5 min (R3) | 380.5 MB | 206.3 MB | last |
| PSS on Bench 20 (R2) | 361.2 MB, bimodal ~352 / ~438 | 218.1 MB | last |
| Scroll FPS at 120 Hz (S5) | 75.3 fps (~63 % of offered frames) | 120.3 fps | last of 4; jank S1 only 0.34 % |
| LTP changes per minute, RELIANCE (U1) | 17.0 /min, on whole seconds | 42.9 /min | last, one run |
| Resume after 1 min background (U3) | 1.0 s after the screen reappears; stale prices shown first | 0.55 s | one run |
| Offline score (O1) | 44.4 | 61.1 | joint last |
| Features score (D1) | 72.2 | 94.4 | joint last |
| Third-party domains in 60 s (X3) | 9 | 1 | last |

Good results to keep: tab switch jank S7 1.62 % (best of 4), frame times S2–S4 near best, 0 crashes.
Not measured: screen loading times (L2–L14). Battery (C2) does not discriminate between apps.

## 2. Biggest wins first

1. Live ticks rebuild whole rows, the wealth tile and the indices rail, even when nothing shown changes
   (C1, U4, U5). Fix: A2, A3, A4, A6. Expected: most of the identical idle frames go away.
2. The wealth tile in the header animates every 3 s forever (U4, C1). Fix: A5 (needs Product).
3. Scrolling down rebuilds the whole header on every frame (S5). Fix: C1 (one-line guard).
4. Rows are torn down and rebuilt on every list update because keys are created in `build`, and
   each row leaks a stream subscription and three tooltip controllers (R9, R3). Fix: B1, B2, B3.
5. Release builds print analytics events with the client code, whole cached API responses and a
   misleading "API Failed" line on every success (privacy, CPU). Fix: F1–F9.
6. No offline banner and no stale marker (O1). Fix: E1, E2 (Product).

## 3. Issues by area

### A. Idle CPU and redraw (C1 185.5 %, U4 39.6 fps, U5 49.5 %)

- A1. Several changes below need a kill switch. Add `WatchlistPerfFlags` (Remote Config, default = today), same
  pattern as `mo_mutual_funds/lib/mf_common/utils/mf_feature_flags.dart`.
- A2. Every price packet rebuilds the whole row: `StreamBuilder` wraps the row's full `Column`
  (name, badges, "Updates" chip, SVGs, `CasSessionRow`, performance line) in
  `trader_watchlist/lib/ui/watchlist_item/watchlist_item.dart:180-190`. The broadcaster mutates one cached
  `BroadcastResponse2` per symbol and re-publishes it for every packet
  (`mosl_broadcaster: lib/internal/broadcast_channel.dart:243-251`), including packets that change only
  fields the row does not show. Fix: listen only in the price column and skip a rebuild when the shown
  strings are unchanged. Explains part of U5 (identical frames) (verify the share with DevTools).
- A3. A new filtered stream is created for every row on every list build:
  `streamCtrl: onTickReceived(watchistScrip.symbol)` (`widgets/watchlist_listing.dart:257-258`).
  `StreamBuilder` resubscribes and `startWith` re-emits the cached value, so every list update costs an
  extra build per row. Fix: cache one stream per symbol in the listing state.
- A4. The header wealth tile rebuilds twice per holdings tick: `PortfolioSummaryService` adds a new value
  to the MOFSL subject and then to the overall subject on every holding P&L tick
  (`trader_core/lib/providers/portfolio_summary_service.dart:820-828`), and the tile combines three
  streams with `Rx.combineLatest3` without `distinct` (`mo_app_bar/lib/widgets/wealth_overview_switcher.dart:86-101`).
  The shown value is rounded, so most of these rebuilds draw the same pixels (verify with the test account's holdings).
- A5. The wealth tile rotates "MO Wealth" / "External Wealth" every 3 s with a 500 ms page animation
  (`wealth_overview_switcher.dart:269-275`, `311-315`) for as long as the header is mounted, which is always
  on the watchlist. At 120 Hz a 500 ms animation every 3 s is about 60 frames per 3 s, i.e. about 20 of the
  39.6 idle fps (verify). Fix needs Product: slower rotation, a fixed number of turns, or no rotation on the Watchlist tab.
- A6. The indices rail creates new tick streams on every header build
  (`trader_home_market/lib/home/ui/widgets/commonindices_show.dart:436-441`). With C1 the header builds rarely,
  so this matters less after C1. Fix: cache the streams.
- A7. Not explained by the code alone (verify): how much CPU goes to parsing socket packets on the UI isolate
  (`mosl_broadcaster: lib/internal/broadcast_channel.dart:173-190`) and to the texture compositing pass (C5).
  C1 also rose from 110.5 % in the first session to ~187 % later; this may be market activity or
  accumulated listeners (B1, B5). Profile one idle minute with DevTools CPU profiler before and after A2–A6.

### B. Memory and leaks (R9 +60 MB, R3 380.5 MB, R2 bimodal)

- B1. `WatchlistItem` subscribes to `toolTipSteamSubscription.stream` in `initState` and never cancels;
  `dispose` is empty; the three `JustTheController`s per row are never disposed
  (`ui/watchlist_item/watchlist_item.dart:96-115`, `133-137`). Fix: keep the subscription and cancel it, dispose the controllers.
- B2. `WatchlistListing.build` replaces the cubit's `StreamController<bool>.broadcast()` on every build and
  never closes the old one (`widgets/watchlist_listing.dart:116-118`). The cubit is app-scoped
  (`apps/super_app/lib/Investor/core/utils/trader_bloc.dart:90`), so these live for the whole session.
  Fix: create once in `initState`, close in `dispose`.
- B3. Keys are created inside `build`: `RectGetter.createGlobalKey()` for the list (line 115) and for every row
  (line 294). A new `GlobalKey` forces Flutter to unmount and remount the row subtree on every list update
  (open, cache then network result, sort, refresh), so every row's `Slidable`, `StreamBuilder`, tooltip
  controllers and subscriptions are recreated each time. Fix: keep keys in the state, per index.
- B4. The app-scoped cubit keeps the screen's `BuildContext` (`saveContext` in `build`, `watchlist_cubit.dart:177-179`,
  called at `watchlist_screen.dart:530`) after the screen is disposed. Fix: clear it in `dispose`.
- B5. The indices rail adds a listener to `cubit.mappedIndices.stream` on every mount and never cancels it
  (`commonindices_show.dart:148-155`, `dispose` at `162-169`). The watchlist is remounted on every bottom-nav visit.
- B6. `BasePageState.startQuoteStreaming` appends to `quoteSymbolList` on every call
  (`trader_widgets/lib/StreamingBaseWidget.dart:115-118`); the listing calls it on every scroll end, so the list
  grows without bound while the screen is open.
- B7. R2's two states (Java heap ~25 MB vs ~94–102 MB in the dumps) and `webviews=1` are not explained by Dart code
  (verify): take a 10-cycle DevTools memory diff and an Android heap dump after B1–B6.

### C. Scrolling and frame delivery (S5 75.3 fps at 120 Hz, S1 0.34 %)

- C1. On every reverse `ScrollUpdateNotification` the listing calls `togglePersistHeader(false)`
  (`widgets/watchlist_listing.dart:161-165`), which emits a new `TogglePersistHeader` each frame
  (`watchlist_cubit.dart:101-104`; states have no `==`, `safeEmit` does not dedupe). The header
  `BlocBuilder` (`watchlist_screen.dart:588-597`) then rebuilds the landing header, wealth tile, indices rail,
  tab bar and banners on every scroll frame. The pin value is not used (comment at `watchlist_screen.dart:877-882`).
  Fix: emit only when the value changes.
- C2. The outer `BlocBuilder` rebuilds the whole `NestedScrollView` (header included) on every
  `WatchlistListLoaded` (`watchlist_screen.dart:549-554`), and the list `BlocBuilder` rebuilds again. (verify)
- C3. `ListView.separated(shrinkWrap: true)` inside an `Expanded` (`widgets/watchlist_listing.dart:194-197`):
  the viewport re-measures its content on every change. The height is already bounded. Fix: drop `shrinkWrap`.
- C4. `getVisible` walks every row key and calls `startQuoteStreaming` on every scroll end and on every
  `ScrollMetricsNotification` at the top (`widgets/watchlist_listing.dart:166-178`); each call sends a
  subscribe packet and writes a log line in the broadcaster (`broadcast_controller.dart:248-258`). Fix: only
  when the visible set changes.
- C5. The app renders through `RenderMode.texture` on Android 11+ (`apps/super_app/android/app/src/main/kotlin/com/mosl/mobile/MainActivity.kt:120-130`).
  Texture mode adds a copy and a second composition pass through the Activity's view hierarchy; this is
  the likely reason RISE shows up as `VRI-com.mosl.mobile/MainActivity` and delivers ~63 % of 120 Hz frames
  while frame times are low (verify). Fix: A/B `RenderMode.surface` behind a flag.

### D. Live prices and returning to the app (U1 17/min, U3)

- D1. No client-side throttle found: packets are published as they arrive
  (`mosl_broadcaster: lib/internal/packet_publisher.dart:53-69`), and the watchlist renders each one. The
  whole-second cadence is therefore likely the feed itself (verify with BE: is the regular quote feed
  conflated to 1 s per symbol?). Not fixable in FE.
- D2. The price socket is shut 15 s after the app is paused (`BroadcastOptions.defaultShutdownDelay`,
  `mosl_socket_core: lib/models/broadcast_option.dart:45`; `BroadCastHelper` does not override it,
  `mosl_broadcaster: lib/core/broadcast_helper.dart:56-65`). After 60 s away the app reconnects and logs in
  again, and rows show the last cached prices until then. Fix options: a longer delay from Remote Config
  (Product/BE trade-off) and the "updating" marker in E2.

### E. Offline (O1 44.4)

- E1. The only offline message is a snackbar gated by `shouldShowToast`, which needs
  `BottomNavCubit.currentPageInd == 1` (`watchlist_cubit.dart:181-185`). That index is only set by
  `trader_bottom_bar/lib/bottom_navigation.dart:566,598`; the RISE shell hosts the watchlist from
  `mo_dashboard/lib/dashboard_screen.dart:263`, which never sets it (verify on device). Result: no message.
  Fix: an in-screen banner on the watchlist (Product).
- E2. No stale marker: the LTP text uses the same style online and offline
  (`ui/watchlist_item/watchlist_item.dart:971-981`). Fix: dim prices and show "Last updated hh:mm:ss" while
  offline or while the socket is not logged in (Product).
- E3. `StreamingBaseWidget.stopNetworkStreaming` cancels the connectivity subscription but leaves the field
  non-null, and `startNetworkStreaming` only subscribes when it is null
  (`trader_widgets/lib/StreamingBaseWidget.dart:208-228`). After the first trip to the background the screen
  never hears about network changes again (verify). Shared by every streaming screen.
- E4. Offline cold start stops at the mPIN screen with "Oops, something went wrong!". Opening a cached
  watchlist before mPIN validation is a Product and security decision.

### F. Release logging and privacy (from the creation notes)

- F1. `callCleverTap` prints every event and every attribute with `print` (`trader_core/lib/utils/clevertapfunc.dart:206-224`),
  so `add_to_watchlist` with Client Code appears in logcat. Fix: debug builds only.
- F2. `handleResponse` writes "API Failed: The new error <type>" before parsing every protobuf response, success
  included (`trader_network/lib/DIOApiService2.dart:943-946`). Fix: remove it.
- F3. The API log builds `'${realUri.origin}${requestOptions.path}'` while `path` is already a full URL
  (`DIOApiService2.dart:390`; `WatchlistAPI.watchlist = "${BASE_URL}api/Watchlist"`), which is the doubled
  `https://tradingapi.mofsl.nethttps://...` line. Fix: log `realUri`.
- F4. Every cached call prints the whole parsed response: `print('response is >> $response')`
  (`DIOApiService2.dart:277`). For the watchlist that includes holdings quantities. Fix: remove.
- F5. `utf8.encode(finalResponse.toString())` is run on every response only to log its size
  (`DIOApiService2.dart:377`). Fix: use the raw byte length.
- F6. The committed HEAD still has `debugPrint('BEARER_TOKEN [$url]: ...')`; the working copy has it commented
  but not committed (`DIOApiService2.dart:313`). Fix: commit the removal.
- F7. `firebase_performance_logcat_enabled = true` in the release manifest
  (`apps/super_app/android/app/src/main/AndroidManifest.xml:116-118`).
- F8. The broadcaster writes the user id on socket login and the full symbol set on every subscribe
  (`mosl_broadcaster: lib/internal/broadcast_channel.dart:213-219`, `broadcast_controller.dart:248-251`) (owners' call).
- F9. `registerVisibilityDetector` `debugPrint`s on every visibility callback (`StreamingBaseWidget.dart:70-74`).
- Not traced to code: the constant orientation events in logcat (no orientation listener found in Dart,
  Kotlin or Java sources; likely an SDK or the OS).

### G. Opening the watchlist (not measured yet: L2–L14 are empty)

- G1. `fetchWatchlist` awaits the MTF list before it starts the watchlist call (`watchlist_cubit.dart:199-205`).
- G2. Fixed 300 ms waits after sort snapshots (`watchlist_cubit.dart:1211-1212`, `1554`, `1596`).
- G3. Every bottom-nav visit emits `WatchlistLoading` and shows the shimmer even though the app-scoped cubit
  still holds the last list (`watchlist_cubit.dart:199-203`, `watchlist_screen.dart:991-992`).

### H. Features (D1 72.2)

- H1. Depth, alerts and Buy/Sell are only on the quote page; long-press opens edit mode
  (`widgets/watchlist_listing.dart:143-151`). A quick-action sheet over the list needs Product.
- H2. No sparkline on rows; needs an intraday series from BE and a Product decision.

### I. Third-party SDK traffic (X3 9 domains)

- I1. Most of the 9 domains come from app-level SDKs (VWO, Protectt.ai, AppsFlyer, Firebase), not from this
  module. Product and BE decide which may contact the network while the watchlist is idle.
- I2. The watchlist mounts a Plotline banner widget on every open (`watchlist_screen.dart:971`) and wraps the
  kebab in a Plotline `PView` (`watchlist_options_bottomsheet.dart:43-45`) (verify whether these trigger network calls).

### J. Creation flow and accessibility

- J1. Name prefilled "WatchList N" (`widgets/add_new_watchlist/add_new_watchlist.dart:53-78`); select it on focus.
- J2. No confirmation after a successful add from search (`trader_search/lib/ui/widgets/search_result_item_widget.dart:577-589`).
- J3. Kebab `InkWell` has no semantic label (`ui/watchlist_options/ui/watchlist_options_bottomsheet.dart:46-49`).
- J4. Add/remove icon in search results has no semantic label (`search_result_item_widget.dart:603-611`).
- J5. Header shift with the wealth rotation: the tile sits in a fixed `0.055 × screen height` box with an
  `AnimatedSize` inside (`wealth_overview_switcher.dart:333-345`); the shift likely comes from the tile
  switching between `SizedBox.shrink()` and content when the stream re-emits (verify).

### K. Tests

- K1. Widget test: a list update must not remount rows (counts `initState` calls).
- K2. Leak test: 10 mount/unmount cycles of the listing leave no live tooltip listeners.
- K3. Unit test: `togglePersistHeader` emits once per value change.

## 4. Suggested order of work

1. Day 1: A1, C1, B1, B2, A3, F1, F2, F3, F4 (small and safe).
2. Day 2: B3, C3, C4, A2 (behind A1), B4, B6.
3. Then: A4, A6, B5 (shared packages), E1 and E2 after the Product decision, A5 after the Product decision.
4. Experiments behind flags: C5 (render mode), D2 (socket delay), E3.
5. Product/BE items: D1, E4, H1, H2, I1.

## 5. How to check progress

Re-run on the same OPPO CPH3009, same Bench 20 list, same Wi-Fi:

- `bench.py --group idle` and `--group live` in market hours: U4, U5, C1 (target: C1 well under 100 %, U5 close to 0).
- `--group scroll`: S5 at 120 Hz (target ≥ 110 fps) with S1 unchanged.
- `--group leak` and `--group ram --with-r3`: R9 (target ≤ 20 MB), R3.
- Manual O1 airplane-mode script after E1/E2.
- Logcat on a release build while adding a stock: no client code, no "API Failed" on 200, no doubled URL.
- Fill L2–L14 before and after G1–G3.

# Watchlist creation — summary (Bench 20)

OPPO K14 Plus 5G (CPH3009, Android 17) · 22 Oct 2026 · developer: mahidhar

Each app got a new watchlist named **Bench 20** with the same 20 NSE stocks, added A–Z:
ASIANPAINT, AXISBANK, BAJFINANCE, BHARTIARTL, HCLTECH, HDFCBANK, HINDUNILVR, ICICIBANK, INFY, ITC,
KOTAKBANK, LT, MARUTI, NTPC, RELIANCE, SBIN, SUNPHARMA, TCS, TITAN, ULTRACEMCO.

## Comparison

| App | Version | Taps to create a list | Taps per stock | Exact stock first in search | List order | Stock count shown |
|---|---|---|---|---|---|---|
| **RISE** | 6.2.09 | 4 + clear prefilled name | 2 | ✅ 20/20 | A–Z (add order) | no |
| Kite | 3.11.11 | 4 | 2 | ✅ 20/20 | A–Z | ✅ 20/250 |
| Groww | 18.21.1 | 3 | 2 | ✅ 20/20 | A–Z | ✅ "20 stocks" |
| Angel One | 126.10.0 | 4 | 2 | ❌ LT 4th, RELIANCE 3rd | newest first | no |
| INDmoney | 9.9.86 | 2 + clear prefilled name | 2 | ✅ 20/20 | newest first | ✅ "20 Stocks" |
| Kotak Neo | 2.2.86 | 3 | 2 | ❌ LT 5th, under the keyboard | newest first | no |
| SAHI | 1.0 | **2** | 2 | ⚠️ "LT" returns nothing; found via "LARSEN" | newest first | no |

Taps are counted from the app's Watchlist screen. "Taps per stock" excludes typing the symbol.
Dhan and Coin are not installed on this phone (N/A).

## Findings

**RISE**
- Search put the exact NSE stock first for all 20 (below an "Option Chain" card).
- Name field is prefilled ("WatchList 9"); it must be cleared before typing.
- No visible confirmation when a stock is added (Kite, Groww, Angel One, INDmoney show a toast).
- The list-menu icon and the per-result add icon have no accessibility label (SAHI labels them "Add to watchlist" / "Remove from watchlist").
- Release build writes to logcat: the client code and the CleverTap `add_to_watchlist` event, a doubled API URL (`https://tradingapi.mofsl.nethttps://...`), "API Failed" on a 200 response, and repeated orientation events.
- Add API: `POST Watchlist/Scrip` returned 200 in ~106 ms.

**Competitors**
- Angel One and Kotak Neo rank other results (IPO cards, LTF, LTTS, RPOWER) above LT / RELIANCE, so tapping the top row adds the wrong stock.
- SAHI does not search on 2-letter queries, so LT cannot be found by its own symbol.
- Groww, after adding all 20, showed a stale "No stocks added" page next to a "Delete watchlist" button; reopening the tab showed 20.
- INDmoney's name field is prefilled ("WATCHLIST 2") and typing appends to it.
- Kotak Neo gives no confirmation on add; Angel One, INDmoney, Kotak Neo and SAHI list newest first.

## Method and limits

- Lists were built by the agent with scripted `adb input` taps (developer waived agent rule 2 for Bench 20 only; lists to be deleted later).
- Each step was checked before the next: screenshots for most apps; for RISE (screenshots blocked) the UI accessibility tree plus RISE's own `add_to_watchlist` log line; for SAHI the button label changing to "Remove from watchlist".
- Tap counts are comparable across apps. Times in `creation.csv` (W2, W4, W5) include the agent's checking pauses and are **not human times**; do not compare them.
- Full numbers: `creation.csv`. Step-by-step flow per app: `creation_steps.md`. Action logs with timestamps: `~/.riise-benchmark/artifacts/watchlist/creation/` (not committed).

# Watchlist creation steps per app (Bench 20)

Built by the agent with scripted taps on 22 Oct 2026 (rule 2 waived by the developer for Bench 20 only).
Tap counts are comparable across apps; times include the agent's screenshot checks and are not human times.

## Kite 3.11.11
Create (4 taps + name):
1. Watchlist tab -> tap the layers+ icon at the right of the list tabs (opens "My watchlists": 7 lists, Discover 35)
2. Tap "+ New watchlist" at the bottom
3. Type the name "Bench 20" in the dialog (keyboard opens on its own)
4. Tap "Create" (list is added as the 8th, the manager stays open)
5. Tap "Bench 20" to open it (empty, "Nothing here", 0/250)

Add a stock (2 taps + symbol):
1. Tap "Search & add" (first stock) or "Clear" (next stocks; the search screen stays open after each add)
2. Type the symbol
3. Tap "+" on the NSE row (always the first result for all 20); a green tick and "Added to watchlist" toast confirm
After the 20th: back arrow to the list -> shows 20/250, A-Z, all NSE.

## Groww 18.21.1
Create (3 taps + name):
1. Stocks -> swipe the tab row (Explore, Holdings, Positions, Orders, My Watchlist, All watchlists) -> tap "All watchlists"
2. Tap "+ Add watchlist" (bottom sheet "Create new watchlist", keyboard opens)
3. Type "Bench 20", tap "Create" -> Groww jumps straight into "Search Groww" for this list

Add a stock (2 taps + symbol):
1. Tap the search field (first stock) or the x clear button (next stocks; search stays open)
2. Type the symbol
3. Tap the bookmark icon on the first row (company name + symbol, e.g. "Asian Paints Ltd. / ASIANPAINT"); toast "Stock saved to Bench 20"
After the 20th: back arrow -> stale "No stocks added" page (bug); Back key -> list gets its own tab "Bench 20" (pinned) -> "20 stocks", A-Z.

## Angel One 126.10.0
Create (4 taps + name):
1. WATCHLIST (bottom nav) -> tap the + circle right of the list tabs (menu: "Create new watchlist", "Manage All Watchlists")
2. Tap "Create new watchlist" (bottom sheet, name max 20 characters)
3. Type "Bench 20", tap "CREATE" -> new tab "Bench 20" appears but the app stays on the previous tab
4. Tap the "Bench 20" tab -> "This Watchlist is Empty" with "Add to watchlist" and trending stocks

Add a stock (2 taps + symbol):
1. Tap "Add to watchlist" (first stock) or the x clear button (next stocks; search stays open)
2. Type the symbol; filters All / Stock / F&O / ETF / IPO
3. Tap the star+ on the "<SYMBOL> NSE EQ" row; toast "<SYMBOL> added to Bench 20."
   - LT: 4th row (Integris Medtech IPO card, LTF, LTTS ranked above)
   - RELIANCE: 3rd row (Jio Platforms IPO card, RPOWER ranked above)
After the 20th: back arrow -> Bench 20 lists newest first (ULTRACEMCO ... ASIANPAINT), all NSE, no count shown.

## INDmoney 9.9.86
Create (2 taps + clearing a prefilled name + name):
1. INDstocks -> Watchlist (top tab row; the row shifts while loading, a first tap landed on IPO) -> tap "+ Create Watchlist" chip
2. Bottom sheet "Create new Watchlist!" has the name prefilled as "WATCHLIST 2"; typing appends to it, so delete it first
3. Type "Bench 20", tap "Create Watchlist" -> the new list opens by itself (empty, "Add Stocks")

Add a stock (2 taps + symbol):
1. Tap "Add Stocks" (first stock; opens "Search & Add" with the keyboard up) or the x clear button (next stocks)
2. Type the symbol; results grouped "Indian Market" then "Related Searches" (F&O)
3. Tap + on the first Indian Market row (company name, e.g. "Asian Paints"); toast "Added to Bench 20 - Change >"
After the 20th: Done -> Bench 20 shows "20 Stocks", newest first.

## Kotak Neo 2.2.86
Create (3 taps + name):
1. Watchlist (bottom nav) -> tap the list+ icon right of the list tabs -> "Manage watchlists" (drag handles, red x delete per list)
2. Tap "+ New list" -> sheet "Give your list a name"
3. Type "Bench 20", tap "Save" -> the new tab "Bench 20" opens by itself (empty)

Add a stock (2 taps + symbol):
1. Tap "Search & add" (first stock) or the x clear button (next stocks)
2. Type the symbol; filters All / Stocks / F&O / Commodities
3. Tap the bookmark on the "<Company> Ltd / NSE - SYMBOL" row (fills blue; no toast)
   - LT: 5th row (Paras Healthcare IPO, Jio Platforms IPO, LTTS NSE, LTTS BSE above), hidden under the keyboard; scroll needed
After the 20th: back arrow -> Bench 20 lists newest first, all NSE, no count shown.

## RISE 6.2.09 (screenshots blocked; built from the UI accessibility tree, each add confirmed in RISE's log)
Create (4 taps + clearing a prefilled name + name):
1. Watchlist (bottom nav) -> tap the unlabelled icon right of the list tabs (opens a sheet: Info / Sort / Manage; Add Scrip, Create New Watchlist, Heatmap View, Show Performance, Show MTF Info, Detailed View)
2. Tap "Create New Watchlist" -> sheet with Custom / Readymade tabs, "Name Your Custom Watchlist", name prefilled "WatchList 9"
3. Tap the name field, delete "WatchList 9", type "Bench 20"
4. Tap "Create" -> the new tab "Bench 20" opens by itself: "No Stocks is Added in this Watchlist !" + "Add Stocks"

Add a stock (2 taps + symbol):
1. Tap "Add Stocks" (first stock; search opens with the keyboard up) or the x clear button (next stocks)
2. Type the symbol; tabs All / Stocks / Options / Futures; first result is an "Option Chain" card
3. Tap the (unlabelled) add icon on the "SYMBOL | NSE | <Company>" row - always the first stock row; no visible toast, but RISE logs add_to_watchlist and POST Watchlist/Scrip returns 200 (~106 ms)
After the 20th: back arrow -> Bench 20 shows the 20 stocks in add order (A-Z), all NSE.

## SAHI 1.0
Create (2 taps + name):
1. Watchlist (bottom nav) -> first visit shows a tip "Switch between list, chart, and column views" (Close) -> tap the + right of the list tabs
2. Sheet "Create new watchlist" (name max 18 characters): type "Bench 20", tap "Create" -> the new tab "Bench 20" opens by itself (empty, "+ Search & Add")

Add a stock (2 taps + symbol):
1. Tap "+ Search & Add" (first stock) or the x clear button (next stocks)
2. Type the symbol; tabs Stocks / F&O; results are "<Company> / NSE • SYMBOL" then the BSE row
3. Tap "Add to watchlist" (bookmark) on the NSE row; it fills and its label becomes "Remove from watchlist"
   - LT: typing "LT" shows no results (2-letter queries only show the "Add from Option Chain" panel); typing "LARSEN" finds "Larsen & Toubro / NSE • LT"
After the 20th: back -> Bench 20 lists all 20, all NSE.

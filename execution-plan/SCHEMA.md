# Execution plan — data format

The `benchmark-execution-plan` agent writes JSON files into one data folder, and
`build_plan.py` turns them into the HTML pages:

```bash
python3 execution-plan/tools/build_plan.py <data_dir> <out_dir>
```

| File | Required | Page(s) it produces |
|---|---|---|
| `meta.json` | yes | header, footer and overview of every page |
| `section-<LETTER>.json` | at least one | `section-<letter>.html`, plus `index.html`, `files.html`, `teams.html`, `risk.html` and `full-report.html` built from all sections |
| `summary.json` | no | `summary.html` (one-page summary and a 2–4 day package) |
| `optimized.json` | no | `optimized-plan.html` (smallest FE-only set) |
| `preferred.json` | no | `most-preferred-plan.html` (biggest contributors per factor, FE only) |

A complete worked example (RISE stock quote page, 117 changes) is in
`execution-plan/examples/quote/`. Check every file with
`python3 -I -c "import json,sys;json.load(open(sys.argv[1]))" <file>`.

---

## meta.json

```json
{
  "title": "Quote Module Change Plan",
  "app": "RISE",
  "subject": "Stock quote page",
  "module_path": "packages/mo_get_quote",
  "code_stats": "194 Dart files · ~37,000 lines",
  "date": "23 Oct 2026",
  "branch": "hotfix/headless_chart_fix",
  "measured_on": "Samsung Galaxy M14, Android 14, 60 Hz, 22 Oct 2026",
  "benchmark_source": "reports/combined/scorecard_2026-10-22.md",
  "smoke_test": "open, all tabs, segments, depth, chart, buy/sell, alerts, back navigation"
}
```

`module_path` is the module folder relative to the code repository root. Files under it count as
"this module" and every other file as a shared package. Optional: `footer`, which replaces the
generated footer text.

---

## section-&lt;LETTER&gt;.json

One file per area: idle work, scrolling, opening, tab switching, live data, memory, chart,
offline, stability, code quality, tests. Letters A, B, C and so on, in reading order.

```json
{
  "section": "A",
  "title": "Idle animations and background work",
  "intro": "2–4 sentences: what this area covers, what is wrong today in plain words, what the changes achieve.",
  "measured": [ {"metric": "Idle redraw after market close", "current": "13.3 fps (99 % identical frames)", "expected": "≈ 0 fps"} ],
  "changes": [
    {
      "id": "A1",
      "title": "Short imperative title (max ~8 words)",
      "summary": "One or two plain sentences: the problem and the change.",
      "categories": ["FE"],
      "risk": "Low",
      "risk_reason": "Why this risk level; what existing behaviour could be affected.",
      "effort": "S",
      "user_visible": false,
      "product_decision": null,
      "be_request": null,
      "files": [ {"path": "packages/<module>/lib/....dart", "lines": "81-92", "change": "What changes in this file, one line."} ],
      "current": "What the code does today and its effect (2–4 sentences, plain).",
      "steps": ["Concrete step 1", "Concrete step 2"],
      "before_code": {"path": "packages/<module>/lib/....dart", "lines": "81-92", "code": "exact code copied from the file (<= 25 lines, trimmed with // ... where needed)"},
      "after_code": {"code": "proposed code sketch (<= 30 lines)"},
      "safety": ["How existing functionality is preserved (flag, fallback, same output, same API)"],
      "regression_checks": ["What QA must re-test after this change"],
      "after_improvement": "Expected effect, in measurable terms where possible.",
      "depends_on": ["C3"],
      "verify": false
    }
  ]
}
```

### Field rules

- **id**: section letter followed by a number starting at 1, with no gaps. IDs are global, so other files reference them.
- **measured.current**: copied from the benchmark file, never estimated. **measured.expected**: a target, worded as an estimate.
- **categories** (one or more):
  - `FE`: a front-end change inside `module_path` only.
  - `FE-Shared`: a front-end change in a shared package or the app shell, which other modules depend on.
  - `BE`: a change to the backend, API, socket server, CDN or a Remote Config value.
  - `Product`: changes what the user sees or how a feature behaves. Fill in `product_decision` with the exact question for Product.
- **risk**, meaning the impact on existing functionality:
  - `Low`: internal to one widget or function, no visible behaviour change, easy to revert.
  - `Medium`: changes loading order, timing, state flow or a visible detail inside the module, and needs a regression pass on the affected screen.
  - `High`: touches a shared package, navigation or the back-stack, a live-data subscription model or the core state flow. It ships behind a feature flag and needs a full regression pass.
- **effort**: `S` is 1 day or less, `M` is 2–4 days, `L` is 1 week or more (one FE developer).
- **user_visible**: true if a user could notice any difference other than "faster or smoother".
- **files**: every file touched, with its path from the code repository root. Write pub-cache or git dependencies as `<package>: lib/...`.
- **before_code**: real code copied from the current file, with the exact line range. Never paraphrase it.
- **safety**: for anything user-visible or risky, a Remote Config or feature flag whose default keeps today's behaviour.
- **verify**: true when the root cause is inferred and must be confirmed on the device.

---

## summary.json

```json
{
  "title": "Quote Module Summary",
  "problems": [ {"title": "Two carousels keep animating when nobody can see them", "cause": "…", "effect": "13.3 fps of identical frames …", "ids": ["A1", "A2"]} ],
  "outcome":  [ {"area": "Quote open, repeat", "today": "1,313 ms", "after": "≤ 400 ms"} ],
  "package": {
    "title": "Major changes possible in 2–4 days",
    "intro": "optional",
    "plan": [ {"owner": "Dev 1 · Idle and scrolling", "rows": [ {"when": "Day 1", "ids": ["C1", "A1"], "what": "…"} ]} ],
    "effect": [ {"area": "Idle after market close", "today": "…", "after": "…"} ],
    "needs_product": "optional text",
    "needs_be": "optional text",
    "later": ["C2", "C7"]
  }
}
```

The package uses only Low or Medium changes with effort `S` (or short `M`) whose `depends_on`
items are also in the package.

## optimized.json

The smallest FE-only set: categories `FE` only, inside `module_path`, no new dependencies and no
flags unless unavoidable.

```json
{
  "title": "Optimized FE Plan",
  "intro": "…",
  "meta_note": "optional, e.g. '7 small pull requests'",
  "items": [
    {"n": 1, "title": "Carousels rotate only while visible", "ids": ["A1", "A2"], "area": "Idle cost",
     "files": [ {"path": "lib/ui/…dart", "lines": "27-48"} ],
     "why": "optional, defaults to the first change's 'current'",
     "change": "optional, defaults to the first change's 'summary'",
     "before": "optional code; defaults to the last change's before_code",
     "after": "optional code; defaults to the last change's after_code",
     "risk": "Low", "risk_why": "…", "test": ["…"], "effect": "…"}
  ],
  "achieve": [ {"metric": "Idle redraw after market close", "today": "13.3 fps", "after": "≈ 0 fps", "items": "1"} ],
  "notice": ["What users will notice, one line each"],
  "one_line": "One-line result",
  "schedule_intro": "optional",
  "schedule": [ {"who": "Dev 1", "rows": [ {"when": "Day 1", "items": "1, 5", "work": "…"} ]} ],
  "not_fixed": [ {"what": "Quote open under 0.5 s", "where": "≈ 0.9–1.0 s after this plan", "why": "…", "ids": ["C2", "C7"]} ]
}
```

## preferred.json

For each factor in the benchmark, the causes that contribute most, and only the changes that remove
them. Front-end changes only; the page shows no effort or time estimates.

```json
{
  "title": "Most Preferred Plan",
  "problem_intro": "The <screen> has … but it is slow and heavy to use. Measured on <device>:",
  "problem_points": ["It takes 1.3–2.5 s to open …"],
  "problem_outro": "These come from a small number of causes in the code. …",
  "factors": [
    {"key": "loading", "title": "Loading time", "problem": "…",
     "today": "1,313 ms repeat …", "after": "≈ 400–500 ms …",
     "causes": [ {"level": "Largest", "text": "Opening calls run one after another …", "ids": ["C2", "C3"]} ],
     "ids": ["C2", "C3", "C4"],
     "covers": ["…"], "not": ["…"]}
  ],
  "foundation": "C1",
  "phases": [ {"title": "Phase 1 · Quick wins", "ids": ["C1", "A1"], "desc": "…"} ]
}
```

Cause levels are `Largest`, `Large`, `Medium` and `Small`.

## Writing rules for every file

- Plain, specific English. No marketing words.
- In plan files, talk only about **today vs after improvement**. No competitor names, no ranks and
  no "top N" language (the benchmark is the input, not the subject).
- Every claim must be checked against the code you read. If you cannot confirm it, drop it or set
  `verify: true` and say what to check.
- Prefer the smallest change that fixes the problem without changing behaviour.
- Write plain text; the generator escapes HTML.

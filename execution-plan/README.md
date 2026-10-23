# execution-plan

Everything for the optional `benchmark-execution-plan` agent
(`.claude/agents/benchmark-execution-plan.md`, command `/benchmark-execution-plan`).

| Path | What |
|---|---|
| `SCHEMA.md` | Data format of a plan (`meta.json`, `section-*.json`, `summary.json`, `optimized.json`, `preferred.json`) and the writing rules |
| `tools/check_plan.py` | Checks a plan's data: ids, categories, risk, dependencies, FE-only preferred plan, no competitor names or ranks in engineering files, the 2–4 day package rules, the management files, and that each `before_code` matches the source file |
| `tools/build_plan.py` | Builds the HTML site from a plan's data (`tools/plan_pages.py`, `tools/roadmap_page.py` and `tools/assets/` are used by it) |
| `tools/rank_impact.py` | Scorecard what-ifs with the dashboard's scoring: `scan` (where the rank is), `plan` (minimum and robust lever sets, break-even, scores per phase → `rank.json`), `snapshot` |
| `examples/quote/` | Worked example: RISE stock quote page, 117 changes |
| `plans/` | Generated plans, one folder per run: `plans/<module>_<date>/` with `benchmark-facts.md`, `issues-report.md`, `data/` and `site/`. Git-ignored |

Rebuild or check a plan by hand:

```bash
python3 execution-plan/tools/check_plan.py execution-plan/plans/<plan>/data --code-root <app repo root>
python3 execution-plan/tools/build_plan.py execution-plan/plans/<plan>/data execution-plan/plans/<plan>/site
open execution-plan/plans/<plan>/site/index.html
```

Where the rank is, and the rank impact of a plan:

```bash
python3 -I execution-plan/tools/rank_impact.py scan --module <m> --results results/<m>/<developer>_<phone>
python3 -I execution-plan/tools/rank_impact.py plan execution-plan/plans/<plan>/data --module <m> --results results/<m>/<developer>_<phone>
```

The example:

```bash
python3 execution-plan/tools/check_plan.py execution-plan/examples/quote
python3 execution-plan/tools/build_plan.py execution-plan/examples/quote /tmp/quote-plan && open /tmp/quote-plan/index.html
```

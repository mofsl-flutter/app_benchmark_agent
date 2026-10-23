---
description: Optional - turn a benchmark result (scorecard, module report, comparison .md/.html/.xlsx) and the module's source code into an execution plan (issues report, detailed change plan, summary, optimized FE plan, most preferred plan) and a management roadmap that shows which fixes reach a rank goal
argument-hint: <benchmark-file> <module-folder | RISE-repo-path> [full|rank|issues|plan|roadmap|summary|optimized|preferred|refresh] [goal, e.g. top3]
---

Use the `benchmark-execution-plan` agent with these arguments: `$ARGUMENTS`.

- The first argument is the benchmark file. It can be any scorecard, module report, comparison or
  workbook, inside or outside this repo. If it is missing, list the newest files under `reports/`
  (`*.md`, `*.xlsx`) and ask which one to use.
- The second argument is the code location. It can be the module folder (for example
  `~/StudioProjects/mosl-riseapp-repo/packages/mo_get_quote`) or the whole RISE repository
  (`~/StudioProjects/mosl-riseapp-repo`). With the whole repository, the agent finds the module
  folder and asks you to confirm it. If the argument is missing, ask for it.
- The third argument is the mode. The default is `full`.
- The fourth argument is the rank goal, for example `top3` (both scorecards), `tech3 ux1`. The default
  is top 3 on both scorecards.

Follow the agent's steps and hard rules exactly. Never edit the app code. Write the plan only into
a new folder under `execution-plan/plans/`.

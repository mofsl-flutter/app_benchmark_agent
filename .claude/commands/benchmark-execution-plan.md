---
description: Optional - turn a benchmark result (scorecard, module report, comparison .md/.html/.xlsx) and the module's source code into an execution plan (issues report, detailed change plan, summary, optimized FE plan, most preferred plan)
argument-hint: <benchmark-file> <module-folder | RISE-repo-path> [full|issues|plan|summary|optimized|preferred]
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

Follow the agent's steps and hard rules exactly. Never edit the app code. Write the plan only into
a new folder under `execution-plan/plans/`.

---
description: Re-check RISE only - benchmark the installed RISE app again for one module, compare with the existing report, update the report's RISE values and show the improvement (e.g. /benchmark-verify quote)
argument-hint: <module> [report.xlsx]
---

Use the `benchmark-verifier` agent for `$ARGUMENTS`.

The first argument is the module. The second, optional, is the existing report to compare against
(the module workbook under `reports/<module>/`). If the module is missing, list the modules that
have a report under `reports/` and ask which one. Follow the agent's steps and hard rules exactly:
measure RISE only, on the report's phone, into `results/_verify/<date>/`, and update the report
only after the developer says yes.

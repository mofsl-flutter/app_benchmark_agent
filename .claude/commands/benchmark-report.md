---
description: Combine every developer's benchmark results into the shared workbook and scorecard
---

Use the `benchmark-runner` agent in mode **report**.

Run `python3 build_report.py --combined`, then show the scorecard tables and the completeness
summary it produced. Do not modify any results files.

Finish with the agent's optional execution-plan question (mode `report`, step 4). Never start the
planner unless the developer says yes. If the runner's last message contains
`EXECUTION_PLAN: yes | <report file> | <path>`, start the `benchmark-execution-plan` agent with that
file, that path and mode `full`.

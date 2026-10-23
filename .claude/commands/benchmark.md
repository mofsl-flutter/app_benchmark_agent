---
description: Run or resume the RISE benchmark for one module on this developer's phone (e.g. /benchmark fno)
argument-hint: <module>
---

Use the `benchmark-runner` agent in mode **run** for module `$ARGUMENTS`.

If `$ARGUMENTS` is empty, first list the modules in `modules/` (without `_app`) and ask which one
the developer was assigned, then proceed. Follow the agent's step list exactly and stop on any
failed hard pre-flight check.

When the runner finishes and its last message contains `EXECUTION_PLAN: yes | <report file> | <path>`
(the developer said yes to the optional execution plan), start the `benchmark-execution-plan` agent
with that report file, that path and mode `full`. If the developer said no, or the line is missing,
do nothing more.

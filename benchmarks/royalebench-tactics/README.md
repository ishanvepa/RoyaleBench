# RoyaleBench Tactics

Generated Harbor dataset: **7 runnable variants**, all against **planner-bot**.
Read [the benchmark guide](../../docs/tactics.md) for scenarios, scores, validation and launch commands.

The [manifest](manifest.json) records every proposed variant, its validation evidence and release status.
Candidates without a passing reference and release gate remain in `candidates/`, outside the runnable task list.
Regenerate with `python -m cr_arena.build_tactics`; edit the source specifications, not these task folders.

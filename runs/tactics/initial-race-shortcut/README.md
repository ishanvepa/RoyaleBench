# Initial tower-race shortcut

The exhaustive opening audit of published Tactics revision `@1` found that Fireball aimed at
the friendly Giant at y=23 wins **both** race positions. The spell's shorter flight still
damages the nearby enemy tower, avoiding the intended commitment-versus-defense distinction.

Each folder retains the exact private task configuration, accepted action log and independently
replayed report. Both rewards are 1 with integrity 1. Reproduce a report with:

```bash
python -m cr_arena.royale_task verify --config runs/tactics/initial-race-shortcut/03-tower-race-b/task.json --log runs/tactics/initial-race-shortcut/03-tower-race-b/actions.jsonl --out /tmp/royalebench-initial-shortcut
```

The corrected source moves the friendly Giant to y=24 in both positions and requires an exhaustive
opening audit before packaging. An immediate Fireball on the friendly Giant then wins A and loses B.
The initial artifact is historical evidence of a task defect, not a model failure or a winning
reference for the corrected task.

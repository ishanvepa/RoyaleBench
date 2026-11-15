#!/bin/bash
# Grade by replaying the carried action log from the task seed (fresh verifier container).
set -uo pipefail
mkdir -p /logs/verifier
LOG=/var/lib/royale/actions.jsonl
[ -f "$LOG" ] && cp "$LOG" /logs/verifier/actions.jsonl
cd /opt/referee/app
if ! PYTHONPATH=/opt/referee/app /opt/referee/venv/bin/python -m cr_arena.royale_task verify \
        --config /tests/task.json --log "$LOG" --out /logs/verifier; then
    echo "verifier crashed; reward 0" >&2
    echo '{"reward": 0.0, "integrity": 0.0}' > /logs/verifier/reward.json
fi

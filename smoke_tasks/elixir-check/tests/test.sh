#!/bin/bash
set -euo pipefail
mkdir -p /logs/verifier
python3 - <<'PY'
import json
from pathlib import Path

reward = 0
try:
    answer = json.loads(Path('/app/answer.json').read_text())
    reward = int(
        isinstance(answer, dict)
        and set(answer) == {'remaining_elixir'}
        and type(answer['remaining_elixir']) is int
        and answer['remaining_elixir'] == 1
    )
except (OSError, ValueError, TypeError):
    pass
Path('/logs/verifier/reward.txt').write_text(f'{reward}\n')
print(f'Elixir smoke-test reward: {reward}')
PY

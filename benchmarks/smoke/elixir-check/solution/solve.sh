#!/bin/bash
set -euo pipefail
mkdir -p /app
printf '{"remaining_elixir":1}\n' > /app/answer.json

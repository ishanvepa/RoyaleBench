#!/bin/bash
# Plumbing check only: waits at every decision until the match ends. Expect reward 0 (a loss).
set -u
cr > /dev/null
for _ in $(seq 1 400); do
    out="$(cr act 0)" || true
    case "$out" in *"GAME OVER"*) echo "$out"; exit 0;; esac
done
echo "match did not finish" >&2
exit 1

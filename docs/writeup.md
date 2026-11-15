# Public writeup

[`writeup.html`](writeup.html) is the public research writeup. It covers motivation,
the task interface, the frozen v9 model comparison, performance by task type, synchronized
recorded gameplay, failure analysis, inference cost, methodology,
and limitations. [`modal_writeup.py`](../modal_writeup.py) serves
the page and its evidence assets locally or on Modal.

The **Overview** section directly above Background preserves the team's supplied
five-paragraph introduction verbatim and uses the same article styling.

## Styling

The page follows the [Vals AI Poker Agent benchmark](https://www.vals.ai/benchmarks/poker_agent):
white backgrounds, warm gray text and rules, green leaderboard cells, a restrained
title, 640-pixel article columns, serif body text, and compact data controls.
The title block uses the reference's 800-pixel width; figures break out to 768
pixels, the task-type chart to 1024, and the leaderboard to the 1280-pixel frame.
The cost visualization follows its framed Pareto scatter plot with square
markers, a tinted clickable legend, monospaced axes, and focus/hover details.
Its controls switch between cost per task and cost per move on logarithmic or
linear scales, and performance between objective success and tasks passed.
Cost per move uses the same run-cost-to-recorded-decisions ratio as the leaderboard.
The task-type chart shows each model's pass rate and passed/total counts for
Resource allocation (3 tasks), Timing (4), Placement (3), and Conversion (11).
All bars use a zero-to-100-percent scale and harness colors. Models can be
ordered by overall score or success within a selected type. Rates are derived
from the embedded per-task rewards; incomplete attempts retain zero reward.
The shared harness filter controls the leaderboard, cost chart, and task-type
chart. The cost chart's legend toggles affect only that chart.
Model-family logos in the results table are embedded from the repository's
[existing logo assets](../cr_arena/assets/logos/README.md), so they work offline.
Background, Results, Tasks, and Methodology use the published
[RoyaleBench page's section layout](https://ishanvepa171--royalebench-writeup.us-east.modal.run/):
plain headings, a three-column capability panel, results grouped with their
charts, a task catalog, and stacked methodology subsections.
These four sections use a 728-pixel reading column. The catalog draws its 21
tasks, objective types, capabilities, and pass counts from the same embedded
v9 snapshot; the published reference's historical results are not imported.
[`theme.css`](writeup-assets/theme.css) defines the shared palette and Söhne,
Martina Plantijn, and Berkeley Mono font faces. These fonts load from Vals AI's
public font URLs, with system fallbacks when offline; no font binaries are
redistributed. [`writeup.css`](writeup-assets/writeup.css) styles the article,
tables, diagrams, charts, and responsive layouts. Both standalone replay pages
also load the shared theme. Their recorded frames and game graphics are unchanged.

Keep these stylesheets alongside the HTML when copying or publishing the page.
Replay regeneration applies the same theme automatically and records renewed
export hashes without changing the source trace hashes.

## Evidence boundaries

The headline cohort is **12 finished full-task runs on `royalebench/royalebench-v9@1`**,
with **21 tasks and one attempt per model per task**. Its snapshot is the same
November 15, 2026, 11:47 a.m. PST cohort recorded in
[`runs/royalebench-v9/difficulty.json`](../runs/royalebench-v9/difficulty.json).
All 252 task rewards and costs are exported to
[`writeup-assets/results.json`](writeup-assets/results.json), with model and
harness IDs, run IDs, settings, per-task durations and metric checksums. No
credentials, secret references, organization IDs, raw agent logs, or environment
variables are exported. Costs come from cached harness metrics or persisted
token-pricing records; refreshing does not launch a model or call a billing API.
Keep the page focused on results, task mechanics, and verified failure cases.
Outside the team's verbatim Overview, omit model-output quotations, editorial
taglines, and speculative future work.
The page ends after Limitations. The reproduction section, on-page run
manifest, acknowledgements, and footer are omitted; the frozen JSON remains
available through the results snapshot link in the results discussion.

The same data is embedded in the HTML, so tables and plots need no live dashboard
or API. The leaderboard, task-type chart, and cost chart share a harness filter.
The leaderboard's **Cost / move** is total run inference cost divided by the
sum of recorded agent decisions across all 21 attempts. This includes submitted
waits and rejected actions, excludes automatic verifier waits, and includes
inference overhead from the full run. It is not a per-model-call price or an
unweighted mean of per-task ratios. Missing counts or a zero denominator display
as unavailable.
The export also includes completion per task and incomplete counts per model.
There are 34 incomplete attempts, all scored zero under the original grading;
33 belong to the four mini-SWE-agent runs with `step_limit=12`. The leaderboard
reports completion separately. The [v9 failure analysis](royalebench_v9_failure_analysis.md)
provides the completion audit and controlled timing/aim/allocation probes used
in the behavioral section. Its concise examples describe observed tactical errors
and successful actions: urgent defense, knockback placement, counter allocation,
and body-block timing. Diagnostic simulator probes do not add model attempts
or change official rewards.

The synchronized **v6@1** case is separate historical evidence, from run
`45124458-3a52-4e73-b380-ee42f6934b19`. It is not counted as an extra v9 result.
The playback caption links to [`opus-trace.txt`](writeup-assets/opus-trace.txt),
a readable export of that task's recorded assistant messages, commands, and tool
outputs in source order. Session metadata and empty reasoning blocks are omitted;
message text is unchanged. The header records the source trajectory SHA-256, and
the seven commands (initial observation plus six plays) match the saved run.
The two replay pages use the current shared renderer and original recorded frames;
both traces are independently verified during rebuilding. All six model/reference
card IDs and deployment ticks match, but several placements differ, so the
comparison does not isolate one action as the cause. The export includes
[`replay-provenance.json`](writeup-assets/replay-provenance.json) with source and
output hashes. Both boards use a common elapsed-time cursor and hold terminal
state after their respective endings. Playback pauses when scrolled out of view
or when the browser tab is hidden. The replay handshake supports both local
`file://` previews and HTTP hosting. Local files use opaque message origins and
targeted parent/iframe window checks; HTTP keeps exact origin checks. The parent
pings on initialization and iframe load, covering already-loaded recordings.

## Preview and check

```powershell
uv run --frozen --extra hosting python -X utf8 modal_writeup.py
```

Open <http://127.0.0.1:8768/>. This serves the actual deployment routes, including
assets and GitHub redirects for the Markdown guides. Opening the HTML directly
also supports the embedded results and synchronized playback. Use the HTTP
preview to check deployment routes and guide redirects. The preview binds only
to the local interface.

```powershell
python tools/build_writeup.py --check
node tools/check_writeup_dom.cjs
node tools/check_writeup_browser.cjs
uv run --frozen --extra hosting --with pytest python -m pytest -q tests/test_writeup_hosting.py
```

The evidence check works from a fresh checkout. It checks the pinned source
manifest, all exported rewards and cost totals, embedded data identity, anchors,
local assets, absence of private metadata, and replay export checksums. The route
checks cover the page, JSON, replays, guide redirects, and missing/private paths.
The Node check exercises rendering logic, filters, binary reward cells, task
inspection, and synchronized playback in a minimal DOM, without a browser.
The browser regression check uses the existing `web/` Playwright dependencies
and installed Chromium. It checks local-file and HTTP readiness, play/pause,
advancing boards, both final frames, reset, and reload with external fonts blocked.
Visual review should cover desktop and phone widths, filtering, task-cell
inspection, and synchronized playback through both endings.

## Refresh deliberately

The public page is a frozen snapshot, rather than a live leaderboard. Editing
prose or styles does not require fetching any evaluation artifacts.

```powershell
python tools/build_writeup.py --refresh
uv run --frozen python tools/build_writeup.py --replays
```

`--refresh` requires the ignored local `runs/evals/` cache and accepts only full,
finished, error-free runs on v9@1. It requires exact parity with the 12-run
difficulty snapshot. New runs require explicitly selecting and documenting a new
cohort and updating the frozen difficulty evidence; they cannot silently enter
this page. The exporter writes `results.json` and replaces only the embedded
`benchmark-data` JSON block, preserving the article and human overview slot.

`--replays` needs the original extracted model artifact under
`runs/recent/v7-design/opus/04-critical-cycle-and-connect/` and the saved reference
trace under `runs/royalebench-v6/docker/04-critical-cycle-and-connect/`. It verifies
both traces, matches their coordinates to `demo/evidence.json`, checks deployment
parity, and regenerates the two standalone HTML assets and provenance. These are
local operations; no new evaluation is performed.

When changing the cohort, also review the static findings and headline numbers in
the article, then recheck the browser layout. Capability labels are editorial
groupings rather than separately validated scores. The README's required opening
overview remains exclusively human-authored; its text is not generated here. The
existing team overview slot on the web page remains available for a human intro.

## Publish

```powershell
uv run --frozen --extra hosting python -X utf8 -m modal deploy modal_writeup.py
```

This uploads the HTML and the tracked `docs/writeup-assets/` directory. Markdown
guide links redirect to the public repository. No evaluation cache, `.env`, or
model credentials are included. See the [Modal guide](modal_guide.md) for the
existing public URL and deployment setup. Local edits and preview do not update
the deployed site automatically.

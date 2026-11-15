# Qwen on Modal

Qwen uses the existing **`mini_swe_agent`** harness. No model-specific harness
or code patch is needed.

## Configuration

The model preset in `evals.toml` supplies:

| Setting | Value |
| --- | --- |
| Harness | `mini_swe_agent` |
| Model | `openai/Qwen/Qwen3.8-2.4T-A95B` |
| API key variable | `OPENAI_API_KEY` |
| Key secret | `modal-qwen-api-key` |
| Endpoint variable | `OPENAI_API_BASE` |
| Endpoint secret | `modal-qwen-base-url` |
| Sandbox provider | `modal` |

The key secret holds the full Modal proxy key and secret joined with a period:
`wk-....ws-...`. The endpoint secret holds this public URL:
`https://ishanvepa171--ep-qwen3-8-2-4t-a95b-server.us-west.modal.direct/v1`.
The URL is stored as a Valkyrie secret reference only to deliver it into the
sandbox environment; its value is not confidential. Credentials stay in Valkyrie.

The `openai/` prefix tells LiteLLM to use Chat Completions. It does not identify
the model's maker. The endpoint serves `Qwen/Qwen3.8-2.4T-A95B`.
See [Modal authentication](https://modal.com/docs/guide/webhook-proxy-auth) and
[LiteLLM compatible endpoints](https://docs.litellm.ai/docs/providers/openai_compatible).

## Run from the dashboard

Restart the dashboard to reload `evals.toml`, then select:

1. Dataset `royalebench/royalebench-v1@3`.
2. Harness `mini_swe_agent`.
3. Model `openai/Qwen/Qwen3.8-2.4T-A95B`.
4. Secret `modal-qwen-api-key` and concurrency 1.
5. One task initially, such as `01-immediate-lethal`.

The backend injects `OPENAI_API_KEY` from the selected secret and `OPENAI_API_BASE`
from the preset's additional secret reference. The preview command includes both
mappings. It also applies the preset's standard harness options:
`cost_tracking=ignore_errors` and `step_limit=12`. Selecting another harness is
rejected for this model configuration to avoid sending incompatible requests.

The `ModelPreset` fields `agent`, `secrets` and `agent_kwargs` are optional generic
configuration support. Other models retain their existing launch settings. No
functional changes were made to the mini-SWE-agent contract or implementation.
The existing stock bundle needed its text files normalized from CRLF to LF so
its shell installer could run on Linux; it remains installed as `mini_swe_agent`
with the same upstream version and code.

## Run from PowerShell

The endpoint URL reference is already saved. To recreate it in a new organization:

```powershell
'https://ishanvepa171--ep-qwen3-8-2-4t-a95b-server.us-west.modal.direct/v1' | uv run valkyrie secret set modal-qwen-base-url
```

Run one task with the existing harness:

```powershell
uv run valkyrie run start --agent mini_swe_agent --dataset royalebench/royalebench-v1@3 --model openai/Qwen/Qwen3.8-2.4T-A95B --provider modal -s OPENAI_API_KEY modal-qwen-api-key -s OPENAI_API_BASE modal-qwen-base-url -k cost_tracking ignore_errors -k step_limit 12 --task-ids 01-immediate-lethal --concurrency 1 --label qwen-stock-mini-swe-lethal-pilot
```

Increase the standard step limit for longer scenarios only after inspecting the
pilot. `ignore_errors` prevents unknown token prices from aborting play; a zero
reported by that fallback is not evidence of free inference. Check Modal billing
for actual charges. The stock harness's model output settings apply; the removed
custom harness's 16,384-token override is no longer applied.

## Dataset networking

Revision `@3` (tag `modal-qwen`) adds the exact endpoint hostname to all eleven
v1 task allowlists. Scenario instructions, scoring, reference logs, opponents and
resource limits are unchanged from `@2`. The separate verifier has no network.
All eleven protected reference logs replayed successfully when `@3` was packaged.
Use the same dataset revision and harness when comparing models.

## Validation and historical evidence

The stock-harness pilot is `b31fb94a-e51c-44c8-9868-5fb1ecc2f372`, on revision
`@3`, concurrency 1. It finished with independent verifier reward **1.0**,
integrity **1.0** and objective met. Qwen made six API calls in 15.50 seconds of
agent runtime and played `cr act 5`, the winning Fireball. Reported usage was
27,893 prompt tokens and 1,352 completion tokens; billing remains unknown.
The [stock pilot evidence](../runs/royalebench-v1/qwen_mini_swe_pilot.json) records
the configuration, verifier result and seven SHA-256-verified raw artifacts,
including the exact stock harness ZIP, mirrored to the durable archive.

Attempts `efa01b44-0c7d-4419-9a73-1178701a8f6c` and
`ce229e6c-cf0d-4979-9d3d-022a9cfa838c` were force-stopped after the original
bundle's CRLF shell-script setup error. They are setup failures, not model scores.

The earlier pilot `50b70c82-7768-4ca2-932b-28bfc074ba36` used the now-removed
`mini_swe_agent_modal_qwen` variant. Its success (reward 1, integrity 1) remains
historical evidence, and must not be labeled as a stock-harness result.
Its [evidence file](../runs/royalebench-v1/qwen_modal_pilot.json) records the exact
configuration and SHA-256-verified raw artifact locations. The custom generator,
its tests and the installed custom agent have been removed. An inactive local
cache and the historical uploaded ZIP remain as provenance.

The normalized archive collector currently requires Unix-only `fcntl`. On
Windows, the stock pilot's raw downloads were mirrored to the durable archive
with every file's SHA-256 verified; normalized analysis exports are not produced
by that fallback.

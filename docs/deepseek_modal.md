# DeepSeek on Modal

Use the existing `mini_swe_agent` harness with the DeepSeek endpoint. No custom
harness or additional credential is required. The live pilot confirmed that the
existing shared proxy pair works.

| Setting | Value |
| --- | --- |
| Endpoint | `https://ishanvepa171--ep-deepseek-v4-1-flash-1017-server.us-west.modal.direct/v1` |
| Harness | `mini_swe_agent` |
| Model | `openai/deepseek-v4.1-flash-1017` |
| Response model | `deepseek-ai/DeepSeek-V4.1-Flash-1017` |
| API key | `OPENAI_API_KEY` from existing `modal-qwen-api-key` |
| API base | `OPENAI_API_BASE` from `modal-deepseek-base-url` |
| Provider | `modal` |
| Dataset | `royalebench/royalebench-v1@5` |
| Harness options | `step_limit=12`, `cost_tracking=ignore_errors` |

The `openai/` prefix selects LiteLLM's compatible Chat Completions transport.
The saved credential contains the full Modal proxy token pair. Its reuse was
authorized for the shared endpoints; no credential values are copied into the
repository or read back from Valkyrie.

Revision `@5`, tagged `modal-deepseek`, adds the exact DeepSeek hostname to all
eleven agent allowlists. Existing model hosts remain allowed. Task instructions,
scenario inputs, resources and scoring are unchanged from `@4`; the separate
verifier has no network. Dataset discovery/configuration/LF checks passed.

The endpoint accepted the configured model ID and returned
`deepseek-ai/DeepSeek-V4.1-Flash-1017` in responses. Pilot
`c68e25b0-8c92-44cf-af7f-bd2254e66083` finished `01-immediate-lethal` at
concurrency 1. The separate verifier awarded reward **1.0**, integrity **1.0**
and objective met. The agent made three model calls, played the winning Fireball
with `cr act 5` and submitted. Agent runtime was 11.91 seconds, with 8,721 prompt
tokens and 371 completion tokens. Actual billing remains unknown.

[Pilot evidence](../runs/royalebench-v1/deepseek_mini_swe_pilot.json) records the
verifier result, exact configuration, model usage and seven raw artifact hashes.
The raw artifacts were mirrored to the durable archive with SHA-256 verification.
Normalized collection still requires Unix-only `fcntl`; this fallback preserves
the raw evidence without producing normalized analysis exports.

Restart the dashboard to reload `evals.toml`, then select the dataset, harness,
model and existing key reference shown above. The preset automatically injects
DeepSeek's base URL and the stock harness options. Start with concurrency 1 and
one task.

The equivalent PowerShell command is:

```powershell
uv run valkyrie run start --agent mini_swe_agent --dataset royalebench/royalebench-v1@5 --model openai/deepseek-v4.1-flash-1017 --provider modal -s OPENAI_API_KEY modal-qwen-api-key -s OPENAI_API_BASE modal-deepseek-base-url -k cost_tracking ignore_errors -k step_limit 12 --task-ids 01-immediate-lethal --concurrency 1 --label deepseek-stock-mini-swe-lethal-pilot
```

Compare models using the same dataset revision and harness settings. One
integration pilot does not measure aggregate benchmark performance.

The public base URL has been saved as a Valkyrie reference. To recreate it:

```powershell
'https://ishanvepa171--ep-deepseek-v4-1-flash-1017-server.us-west.modal.direct/v1' | uv run valkyrie secret set modal-deepseek-base-url
```

See [Inkling on Modal](inkling_modal.md) and [Qwen on Modal](qwen_modal.md) for
the shared credential setup and the existing stock harness's Linux line-ending
packaging repair. `ignore_errors` permits unknown token prices; a reported zero
does not establish actual inference cost. Check Modal billing for charges.

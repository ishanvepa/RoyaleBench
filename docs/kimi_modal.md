# Kimi on Modal

Use the existing `mini_swe_agent` harness and shared Modal proxy credential.
No model-specific harness is needed.

| Setting | Value |
| --- | --- |
| Endpoint | `https://ishanvepa171--ep-kimi-k3-1-pro-server.us-west.modal.direct/v1` |
| Harness | `mini_swe_agent` |
| Model | `openai/kimi-k3.1-pro` |
| Response model | `moonshotai/Kimi-K3.1-Pro` |
| API key | `OPENAI_API_KEY` from `modal-qwen-api-key` |
| API base | `OPENAI_API_BASE` from `modal-kimi-base-url` |
| Modal serving app | `ep-kimi-k3-1-pro` |
| Sandbox provider | `modal` |
| Dataset | `royalebench/royalebench-v1@6` |
| Harness options | `step_limit=12`, `cost_tracking=ignore_errors` |

The existing key reference contains the full shared Modal proxy token pair.
Credential values are not read back or written to tracked files. The `openai/`
prefix selects LiteLLM's compatible Chat Completions transport.

Revision `@6` (tag `modal-kimi`) adds the exact Kimi endpoint hostname to all
eleven agent allowlists. Existing model hosts remain allowed. Scenario inputs,
instructions, scoring, resource limits and verifier isolation are unchanged
from `@5`. Dataset discovery/configuration/LF checks passed for all eleven tasks.

The endpoint accepted the existing shared credential and configured model ID,
returning `moonshotai/Kimi-K3.1-Pro` in responses. Pilot
`a46a46f4-ebc2-4519-8220-94b73d5e68c8` finished `01-immediate-lethal` at
concurrency 1. The separate verifier awarded reward **1.0**, integrity **1.0**
and objective met. Kimi made three API calls, played the winning Fireball with
`cr act 5` and submitted. Agent runtime was 12.31 seconds, with 8,187 prompt
tokens and 444 completion tokens. Actual billing remains unknown.

[Pilot evidence](../runs/royalebench-v1/kimi_mini_swe_pilot.json) records the
exact configuration, model usage, independent verifier result and seven raw
artifact checksums. All seven files were mirrored to the durable archive and
verified with SHA-256. Normalized collection still requires Unix-only `fcntl`;
this fallback preserves the raw evidence without normalized analysis exports.

Restart the dashboard to load the `evals.toml` preset. Select dataset
`royalebench-v1@6`, harness `mini_swe_agent`, model `openai/kimi-k3.1-pro`,
secret `modal-qwen-api-key`, concurrency 1 and one task initially. The preset
automatically injects Kimi's base URL and stock harness options. `modal_app`
identifies the serving app for the existing Modal billing lookup.

The equivalent PowerShell command is:

```powershell
uv run valkyrie run start --agent mini_swe_agent --dataset royalebench/royalebench-v1@6 --model openai/kimi-k3.1-pro --provider modal -s OPENAI_API_KEY modal-qwen-api-key -s OPENAI_API_BASE modal-kimi-base-url -k cost_tracking ignore_errors -k step_limit 12 --task-ids 01-immediate-lethal --concurrency 1 --label kimi-stock-mini-swe-lethal-pilot
```

One integration pilot does not establish aggregate model strength.

The endpoint URL reference is saved. To recreate it:

```powershell
'https://ishanvepa171--ep-kimi-k3-1-pro-server.us-west.modal.direct/v1' | uv run valkyrie secret set modal-kimi-base-url
```

See [DeepSeek](deepseek_modal.md), [Inkling](inkling_modal.md) and
[Qwen](qwen_modal.md) for previous stock harness pilots using the same credential.
Use the same dataset revision and harness settings when comparing models.
Unknown-price fallback values do not establish actual cost; check Modal billing.

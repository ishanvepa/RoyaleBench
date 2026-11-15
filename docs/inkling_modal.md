# Inkling on Modal

Use the existing `mini_swe_agent` harness for this endpoint:
`https://ishanvepa171--ep-inkling-2-small-server.us-west.modal.direct/v1`.
No custom harness is needed.

## Setup status

- The base URL is saved in Valkyrie as `modal-inkling-base-url`.
- Dataset `royalebench/royalebench-v1@4`, tagged `modal-inkling`, allows this exact
  hostname as well as the existing model hosts. All eleven task configurations
  changed only in their model-host allowlist relative to `@3`.
- Dataset discovery, configuration and LF checks passed for all eleven tasks.
- The owner authorized reusing the Qwen credential. The stock-harness pilot
  `153d8ecf-69d4-4357-9c55-4a9552ab3934` finished successfully with
  `modal-qwen-api-key` and `modal-inkling-base-url` on revision `@4`, concurrency 1.
- The endpoint accepts `openai/inkling-2-small` through LiteLLM and reports
  `thinkingmachines/inkling-2-small` in responses. Its active `evals.toml` preset
  uses the existing `mini_swe_agent`, step limit 12 and `cost_tracking=ignore_errors`.
- The separate verifier awarded reward **1.0**, integrity **1.0** and objective
  met on `01-immediate-lethal`. Inkling made three model calls, played the winning
  Fireball (`cr act 5`) and submitted. Agent runtime was 12.22 seconds, with 8,714
  prompt tokens and 456 completion tokens. Actual billing remains unknown.
- [Pilot evidence](../runs/royalebench-v1/inkling_mini_swe_pilot.json) records the
  verifier result, exact configuration, usage and seven raw artifact checksums.
  Raw files were mirrored to the durable archive and verified with SHA-256;
  normalized archive collection still requires Unix-only `fcntl`.

[Modal proxy authentication](https://modal.com/docs/guide/webhook-proxy-auth)
requires both the `wk-` token ID and its matching `ws-` secret. The API key for
LiteLLM is the pair joined with a period: `wk-....ws-...`.

## Credential reuse

Use the existing `modal-qwen-api-key` reference when it is accepted by this
endpoint; the pilot confirmed it is accepted. No duplicate secret needs to be
created. That reference contains the
full existing token pair. Reusing only a `ws-` value with another `wk-` ID does
not establish that the new pair is valid. The live pilot tested the existing pair.

## Run with the existing credential

Restart the dashboard to load the preset, then select dataset
`royalebench-v1@4`, harness `mini_swe_agent`, model `openai/inkling-2-small`,
secret `modal-qwen-api-key`, concurrency 1 and one task initially. The preset
automatically injects the separate Inkling base URL.

The equivalent PowerShell command is:

```powershell
uv run valkyrie run start --agent mini_swe_agent --dataset royalebench/royalebench-v1@4 --model openai/inkling-2-small --provider modal -s OPENAI_API_KEY modal-qwen-api-key -s OPENAI_API_BASE modal-inkling-base-url -k cost_tracking ignore_errors -k step_limit 12 --task-ids 01-immediate-lethal --concurrency 1 --label inkling-stock-mini-swe-lethal-pilot
```

This one-task pilot verifies integration, not aggregate model strength. Use the
same dataset revision and harness settings for comparisons with Qwen.

## Optional separate credentials and model discovery

Run this in PowerShell locally. Prompts hide the values; the output shows only
the served model ID and the saved Valkyrie reference. Do not paste the secret
into chat or a tracked file.

```powershell
$proxyIdInput = Read-Host 'Paste full wk- token ID' -AsSecureString
$proxySecretInput = Read-Host 'Paste matching full ws- secret' -AsSecureString
$proxyId = ([System.Net.NetworkCredential]::new('', $proxyIdInput).Password -replace '[\x00-\x20\x7F]', '')
$proxySecret = ([System.Net.NetworkCredential]::new('', $proxySecretInput).Password -replace '[\x00-\x20\x7F]', '')
if (-not $proxyId.StartsWith('wk-') -or -not $proxySecret.StartsWith('ws-')) {
    throw 'Expected the full wk- token ID and matching ws- secret.'
}
$proxyBearer = "$proxyId.$proxySecret"
$baseUrl = 'https://ishanvepa171--ep-inkling-2-small-server.us-west.modal.direct/v1'
$served = Invoke-RestMethod -Uri "$baseUrl/models" -Headers @{ Authorization = "Bearer $proxyBearer" }
$proxyBearer | uv run valkyrie secret set modal-inkling-api-key
if ($LASTEXITCODE -ne 0) { throw 'Saving the Valkyrie credential failed.' }
$served.data | Select-Object id
Remove-Variable proxyBearer, proxySecret, proxyId, proxyIdInput, proxySecretInput
```

For a different served model, the `evals.toml` preset should use `openai/<exact-served-id>`,
`secret_env = "OPENAI_API_KEY"`, `agent = "mini_swe_agent"`,
`secrets = { OPENAI_API_BASE = "modal-inkling-base-url" }` and
`agent_kwargs = { cost_tracking = "ignore_errors", step_limit = "12" }`.
Select the existing `modal-qwen-api-key` as the credential, or
`modal-inkling-api-key` if a separate pair was saved above. Start with one task on `@4`
and concurrency 1. Unknown-price fallback values do not establish actual cost.

See [Qwen on Modal](qwen_modal.md) for the verified stock harness configuration
and the previous Windows line-ending packaging repair.

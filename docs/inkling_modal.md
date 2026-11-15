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
- Authentication, the served model ID, the active model preset and a live pilot
  are pending the matching proxy token secret. An unauthenticated `/v1/models`
  request returned HTTP 401. A `wk-` token ID alone is insufficient.

[Modal proxy authentication](https://modal.com/docs/guide/webhook-proxy-auth)
requires both the `wk-` token ID and its matching `ws-` secret. The API key for
LiteLLM is the pair joined with a period: `wk-....ws-...`.

## Save credentials and discover the model

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

After discovery, the `evals.toml` preset should use `openai/<exact-served-id>`,
`secret_env = "OPENAI_API_KEY"`, `agent = "mini_swe_agent"`,
`secrets = { OPENAI_API_BASE = "modal-inkling-base-url" }` and
`agent_kwargs = { cost_tracking = "ignore_errors", step_limit = "12" }`.
Select `modal-inkling-api-key` as the credential. Start with one task on `@4`
and concurrency 1. Unknown-price fallback values do not establish actual cost.

See [Qwen on Modal](qwen_modal.md) for the verified stock harness configuration
and the previous Windows line-ending packaging repair.

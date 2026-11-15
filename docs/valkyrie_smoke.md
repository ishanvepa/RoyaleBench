# Valkyrie connection smoke test

This single-task dataset checks the hosted execution path: sandbox startup,
Claude Code installation, model authentication, answer-file creation, grading,
and retrieval of results and traces. It is an infrastructure check and should
be excluded from reported benchmark difficulty results.

## Prepared resources

- Organization: `hackathon-rip-ojas-e8d933c926`
- CLI used to prepare the test: `valkyrie-cli v2026.11.14`
- Installed harness: `claude_code-v1.0.0` from the public agent registry
- Published dataset: `royalebench/smoke@1`, also tagged `v1`
- Source: `benchmarks/smoke/elixir-check/`
- Grading: 1 for the exact requested JSON object with integer answer 1; 0 otherwise
- Agent limit: 120 seconds; verifier limit: 30 seconds

The task deliberately requires no game knowledge: subtract card costs of 4,
3, and 2 from 10 starting elixir with regeneration disabled.

## Connect credentials once

In each terminal session, select your own secret name. Ben uses
`anthropic-api-key-ben`; Ishan uses `anthropic-api-key-ishan`. Change the example
below to your name:

```bash
export VALKYRIE_ANTHROPIC_SECRET="anthropic-api-key-ben"
```

The variable contains only a secret name. If that secret is not already saved,
enter your Anthropic key once at the hidden prompt:

```bash
valkyrie secret set "${VALKYRIE_ANTHROPIC_SECRET:?Set your secret name first}"
```

Skip this command for an existing key: setting the same name replaces its
value. These secrets are available to the organization, and usage is charged
to the API account selected by each run. The name suffix does not make a
secret private to that person.

Modal is configured once for the team. Check `valkyrie provider list` and reuse
the existing connection. If Modal is not connected, create an API token in the credited workspace at
<https://modal.com/settings/tokens>. Upload its token ID and secret with hidden
prompts, without saving a credentials file in the repository:

```bash
python3 -c 'import getpass,json; print(json.dumps({"MODAL_TOKEN_ID":getpass.getpass("Modal token ID: "),"MODAL_TOKEN_SECRET":getpass.getpass("Modal token secret: ")}))' | valkyrie secret set modal-credentials
valkyrie provider set modal modal-credentials
```

These commands save organization secrets; team members can then reference them
by name in runs.

## Run one task

```bash
valkyrie run start \
  --agent claude_code-v1.0.0 \
  --dataset royalebench/smoke@1 \
  --model anthropic/claude-sonnet-4-6 \
  --provider modal \
  -s ANTHROPIC_API_KEY "${VALKYRIE_ANTHROPIC_SECRET:?Set your secret name first}" \
  --slice 0:1 --concurrency 1 \
  --label royalebench-connection-smoke --connect
```

Record the run ID printed by the CLI. After completion:

```bash
valkyrie run results RUN_ID --path ./runs/valkyrie-smoke-results.json
valkyrie run artifacts RUN_ID
valkyrie run output RUN_ID --output-dir ./runs/valkyrie-smoke-output
```

A completed task with reward 1, plus a downloaded model trace, confirms the
execution path. Publishing the dataset alone does not confirm model or Modal
credentials work.

## Republish source changes

```bash
valkyrie dataset push royalebench/smoke ./benchmarks/smoke
```

Use the new immutable revision printed by the CLI for subsequent runs.

## Verified run

On November 14, 2026, run `27f16d60-bfea-44f1-b371-c115be59bfab`
completed with one finished task, reward **1.0**, and aggregate score **100.0**.
It used `anthropic/claude-sonnet-4-6`, `claude_code-v1.0.0`,
`royalebench/smoke@1`, Modal, concurrency 1, and the organization secret
`anthropic-api-key-ben`. The agent reported approximately $0.0159 of model
usage; this excludes sandbox charges.

An earlier setup run failed because the Modal secret was not a JSON object.
Saving both token fields as one JSON object fixed that configuration issue.
The run recorded here succeeded on its first attempt with Ben's named secret.

Saved evidence:

- Results: `runs/valkyrie-ben-key-smoke-results.json`
- Model trace: `runs/valkyrie-ben-key-smoke-output/elixir-check/logs/trajectory.jsonl`
- Model output: `runs/valkyrie-ben-key-smoke-output/elixir-check/logs/final_message.txt`
- Model usage: `runs/valkyrie-ben-key-smoke-output/elixir-check/logs/summary.json`

This proves the execution path works; the intentionally trivial task does not
measure meaningful Clash Royale strategy.

## References

- [Valkyrie quickstart](https://docs.valkyrie.vals.ai/get-started/quickstart)
- [Modal connection setup](https://docs.valkyrie.vals.ai/get-started/sandbox-providers)
- [Harbor task format](https://docs.harborframework.com/tasks/overview)

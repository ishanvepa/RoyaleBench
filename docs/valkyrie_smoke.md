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
- Source: `smoke_tasks/elixir-check/`
- Grading: 1 for the exact requested JSON object with integer answer 1; 0 otherwise
- Agent limit: 120 seconds; verifier limit: 30 seconds

The task deliberately requires no game knowledge: subtract card costs of 4,
3, and 2 from 10 starting elixir with regeneration disabled.

## Connect credentials once

Enter your Anthropic key at the hidden prompt:

```bash
valkyrie secret set anthropic-api-key
```

Create a Modal API token in the credited workspace at
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
  -s ANTHROPIC_API_KEY anthropic-api-key \
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
valkyrie dataset push royalebench/smoke ./smoke_tasks
```

Use the new immutable revision printed by the CLI for subsequent runs.

## References

- [Valkyrie quickstart](https://docs.valkyrie.vals.ai/get-started/quickstart)
- [Modal connection setup](https://docs.valkyrie.vals.ai/get-started/sandbox-providers)
- [Harbor task format](https://docs.harborframework.com/tasks/overview)

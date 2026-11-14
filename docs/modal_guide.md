# Modal quick guide

Modal supplies the cloud sandbox compute for RoyaleBench evaluation tasks. For the November 14–15 Build Your Own Eval hackathon, our Modal credits pay for the environments where agents execute Clash Royale tasks and graders check their outputs. Model API usage uses the separate model-provider credits described in the [track guide](build_eval_track.md).

## How it fits

`Harbor task files → Valkyrie evaluation run → Modal sandbox → scores and traces in Valkyrie`

We define the task environment, inputs, and grading; Valkyrie coordinates execution using `--provider modal`. [Modal Sandboxes](https://modal.com/docs/guide/sandboxes) provide isolated containers for running the task code. Start with the existing [connection smoke test](valkyrie_smoke.md) before spending credits on benchmark comparisons.

## Connect once

1. Claim the hackathon Modal credits and select the credited Modal workspace.
2. Create an API token in [Modal token settings](https://modal.com/settings/tokens).
3. After selecting our Valkyrie organization (see the [Valkyrie guide](valkyrie_guide.md)), upload the token through hidden prompts and configure the provider:

```bash
python3 -c 'import getpass,json; print(json.dumps({"MODAL_TOKEN_ID":getpass.getpass("Modal token ID: "),"MODAL_TOKEN_SECRET":getpass.getpass("Modal token secret: ")}))' | valkyrie secret set modal-credentials
valkyrie provider set modal modal-credentials
```

The secret contains both `MODAL_TOKEN_ID` and `MODAL_TOKEN_SECRET`. Keep their values out of repository files and shell history. Model authentication is configured separately; the [smoke-test guide](valkyrie_smoke.md) includes the Anthropic secret setup.

For direct Modal development, follow [getting started](https://modal.com/docs/guide/getting-started) to install the SDK/CLI and run `modal setup`. The Valkyrie workflow above connects its hosted runner through a stored token.

## During the hackathon

- Use `--provider modal --concurrency 1 --slice 0:1` for the initial run. Follow the complete command in the [Valkyrie guide](valkyrie_guide.md).
- Confirm sandbox startup, model output, grading, and trace retrieval before scaling up. A dataset upload alone does not establish that compute works.
- Inspect sandbox logs and resource usage in the [Modal dashboard](https://modal.com/apps); inspect task results and model traces through Valkyrie.
- If startup fails, check the credited workspace, token, and Valkyrie provider configuration. For timeouts or memory failures, inspect logs and task resource limits before retrying.
- Keep task environments and resource limits consistent across model comparisons. Increase concurrency after a small run succeeds.

## Relevant links

- [Valkyrie sandbox provider setup](https://docs.valkyrie.vals.ai/get-started/sandbox-providers): connecting Modal to the evaluation runner.
- [Modal documentation](https://modal.com/docs): platform reference.
- [Modal Sandboxes](https://modal.com/docs/guide/sandboxes): lifecycle, execution, and resource settings.
- [Modal pricing](https://modal.com/pricing): compute costs when planning run size.
- [Project track requirements](build_eval_track.md): credits, deliverables, and judging criteria.

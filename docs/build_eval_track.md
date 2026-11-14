## BUILD YOUR OWN EVAL

### OVERVIEW

The goal of this track is to find a task that frontier models still get wrong, and turn it into a benchmark.

You will be judged on your benchmark’s:

- **Novelty** - How creative is the benchmark
- **Execution** - How well built is the benchmark
- **Difficulty** - Can frontier models solve the tasks or do they struggle
- **Importance** - How much impact would the benchmark have to the world at large

You will also be judged on clarity and presentation of results.

You will run it on Valkyrie, a distributed platform Vals AI uses to run agent benchmarks. Valkyrie is designed to allow easy remote execution of many benchmark tasks in parallel.

### SETUP

1. Claim your Claude and OpenAI API credits in **Your credits** to test your evaluation.
2. Claim your Modal credits for the sandboxes that run your evaluation tasks.
3. [Install uv](https://docs.astral.sh/uv/getting-started/installation/), then the Valkyrie CLI:
   ```
   uv tool install valkyrie-cli
   ```
4. Run `valkyrie login` only if you haven't signed in, using the same account as this hackathon page. Then select your team's organization, **hackathon-rip-ojas-e8d933c926**. An already signed-in session picks up the new org automatically.
   ```
   valkyrie org use hackathon-rip-ojas-e8d933c926
   ```
   Then follow the [Valkyrie quickstart](https://docs.valkyrie.vals.ai/get-started/quickstart) from step 3 to run your first agent. Skip creating an organization.
5. Build tasks in the [Harbor task format](https://docs.harborframework.com/tasks/overview). Use the [dataset commands](https://docs.valkyrie.vals.ai/benchmarks/datasets) to upload your dataset to Valkyrie and run it.

   Example command:
   ```perl
   valkyrie dataset push my-benchmark/my-dataset ./tasks --tag v1
   valkyrie run start --agent claude_code-v1.0.0 \
     --dataset my-benchmark/my-dataset@v1 \
     --model anthropic/claude-sonnet-4-6 --provider modal \
     -s ANTHROPIC_API_KEY anthropic-api-key \
     --concurrency 1 --connect
   ```
6. Watch runs live in the terminal. Everyone on your team sees the same runs, datasets and task logs, and can use any agent a teammate installed.
   ```
   valkyrie tui
   ```
7. Save your project below. Judges see it at demos on Sun 2 PM, and you can edit it until then.

For more information about Valkyrie, consult the [documentation](https://docs.valkyrie.vals.ai/), run `valkyrie --help`, or ask your agent. The source code is publicly available [here](https://github.com/vals-ai/Valkyrie).

### HARNESSES AVAILABLE

We have the following harnesses available to use out-of-the-box:

- [Claude Code](https://github.com/vals-ai/public-agent-registry/tree/main/examples/claude_code-v1.0.0)
- [Codex](https://github.com/vals-ai/public-agent-registry/tree/main/examples/codex-v1.0.0)
- [mini-SWE-agent](https://github.com/vals-ai/public-agent-registry/tree/main/agents/mini_swe_agent)

You can also add a custom harness to Valkyrie: [https://docs.valkyrie.vals.ai/agents/package-an-agent](https://docs.valkyrie.vals.ai/agents/package-an-agent)

### WHAT YOU SUBMIT

- **Code and data:** A GitHub repo with your tasks and a README that says how to run them. You can also upload the dataset to Valkyrie.
- **Writeup:** How the benchmark works, at the top of the README. You should have a one paragraph overview at the start that is entirely human-written.
- **Results:** How frontier models score on your benchmark. Put them in the README (graphs preferred alongside tables).
- **Traces or Examples (optional):** Model rollouts, or the ID of your Valkyrie run. Showing a concrete failure mode the benchmark exposes goes a long way.

### OTHER TIPS

- We recommend focusing on quality of samples, not quantity
- Keep in mind your budget. Try small experiments before scaling up.
- We recommend no public internet access for your agents (to avoid HuggingFace-esque disasters)
- Look at your traces and rollouts in tandem with building the benchmark
- You should be able to justify why you chose the harness you did

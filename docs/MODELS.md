# Models to evaluate

Prices are list prices per million tokens, checked Nov 5, 2026
([Anthropic](https://platform.claude.com/docs/en/models/overview),
[OpenAI](https://developers.openai.com/api/docs/pricing)). Names are the exact strings to pass to
`--model` (LiteLLM names; it already knows these prices, so cost caps work).

## Why this mix

A leaderboard is convincing when it spans the range: the strongest models (is the benchmark
saturated?), mid-priced workhorses (what most people use), and open-weight models (how far behind is
open?). If the ranking comes out in the expected order *and* the strongest model is well below 100%,
the benchmark discriminates. Two vendors at each level keeps it from looking like a one-company test.

| Role | Model | `--model` | $ in / out | Key | Checkpoint (Nov 12) | Full run (Nov 20) |
|---|---|---|---|---|---|---|
| Ceiling | Claude Fable 5.1 | `claude-fable-5-1` | 10 / 50 | ANTHROPIC_API_KEY | – | 1 attempt, Tier 2/3 |
| Ceiling | GPT-6 Astra | `gpt-6-astra` | 10 / 50 | OPENAI_API_KEY | – | 1 attempt, Tier 2/3 |
| Workhorse | Claude Opus 5.5 | `claude-opus-5-5` | 4 / 20 | ANTHROPIC_API_KEY | 1 attempt | 2 attempts |
| Workhorse | GPT-6.1 Sol | `gpt-6.1-sol` | 2 / 10 | OPENAI_API_KEY | 1 attempt | 2 attempts |
| Open-weight, hosted | DeepSeek V4 Pro | `deepseek/deepseek-v4-pro` | 1.32 / 3.96 (LiteLLM table) | DEEPSEEK_API_KEY (new) | optional | 2 attempts |
| Open-weight, local | Qwen3 8B via Ollama | `ollama_chat/qwen3:8b` | free | none | 1 attempt | 2 attempts |

**GPT-6.1 Sol is deliberate:** it's the model all ten v1 pilots used (10/10 first-try passes). Its
v2 score is the cleanest before/after evidence that the new tasks are harder.

**Local model:** Qwen3 8B (about 5 GB) fits a 16 GB Mac alongside Docker; gpt-oss 20B would not.
The harness sets a 16K-token context window for Ollama models, because Ollama's small default
silently cuts off long agent conversations. It will be slow, so run it with `--jobs 1`. It anchors
the bottom of the table for free.

**Calibration probes, not on the leaderboard:** Claude Haiku 5.5 (`claude-haiku-5-5`) and GPT-6
Luna (`gpt-6-luna`), the cheapest model from each vendor, get one run per new task to set its tier (see SPEC.md, admission rule 3).
Keeping them off the leaderboard means no ranked model influenced which tasks exist.
GLM-5.3 and Kimi K3 are strong open-weight alternatives via OpenRouter (would need an `OPENROUTER_API_KEY`).

## Cost policy

The budget is set from measured costs, never guesses. Rules:

1. **Measure before spending.** Each new model gets a smoke run on one task ($1 cap). The checkpoint
   run measures real per-attempt cost by tier; the full-run budget is computed from it.
2. **Spend attempts where they inform.** Tier 1 is saturated (a workhorse model solves it in under a
   minute), so the ceiling models skip Tier 1 entirely and run once on Tier 2/3 only.
3. **Two attempts for workhorses, not three.** Uncertainty comes mostly from the number of tasks,
   so a third attempt buys little precision. pass@2 is reported instead of pass@3.
4. **Cheap calibration.** Tier probes use the cheapest models of each vendor (Claude Haiku 5.5,
   GPT-6 Luna, about $0.10/$0.50 per M tokens), plus the free local model.
5. **Hard caps everywhere.** `--max-cost` per run (required), `--cost-per-attempt` $2 by default
   (an attempt hitting it counts as a failure), 100 agent steps per attempt.

| Run | What runs | Budget rule |
|---|---|---|
| Checkpoint (Nov 12) | Sol + Opus, 1 attempt, all tasks; Qwen3 8B local | cap $15 total |
| Full (Nov 20) | Sol + Opus ×2; Fable + Astra ×1 on Tier 2/3; DeepSeek ×2 (optional); Qwen3 ×2 | measured cost per attempt × attempts, +20% |

Every run requires `--max-cost`, a hard total cap: the run stops when it's reached, the interrupted
attempt is not scored, and the same command with the same `--run-id` resumes.

## Measured so far

| Date | Run | Result | Cost |
|---|---|---|---|
| 2026-11-05 | smoke-sol: GPT-6.1 Sol on dhcp-lease-writer (Tier 1) | Pass, 47 s | $0.05 |

## Commands

```sh
# checkpoint (Nov 12)
kernelmind run --agent mini --model claude-opus-5-5 --max-cost 10 --run-id ckpt-opus
kernelmind run --agent mini --model gpt-6.1-sol     --max-cost 5  --run-id ckpt-sol
kernelmind run --agent mini --model ollama_chat/qwen3:8b --max-cost 1 --jobs 1 --run-id ckpt-qwen3
kernelmind report results/ckpt-*
```

Fairness rules: same scaffold (mini-swe-agent, `mini.yaml`), same limits (100 steps, $2 per attempt, task time
limits), provider-default reasoning settings, no per-model prompt tuning.

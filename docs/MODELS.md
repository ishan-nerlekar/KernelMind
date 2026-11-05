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
| Ceiling | Claude Fable 5.1 | `claude-fable-5-1` | 10 / 50 | ANTHROPIC_API_KEY | – | 1 attempt |
| Ceiling | GPT-6 Astra | `gpt-6-astra` | 10 / 50 | OPENAI_API_KEY | – | 1 attempt |
| Workhorse | Claude Opus 5.5 | `claude-opus-5-5` | 4 / 20 | ANTHROPIC_API_KEY | 1 attempt | 3 attempts |
| Workhorse | GPT-6.1 Sol | `gpt-6.1-sol` | 2 / 10 | OPENAI_API_KEY | 1 attempt | 3 attempts |
| Open-weight, hosted | DeepSeek V4 Pro | `deepseek/deepseek-v4-pro` | 1.32 / 3.96 (LiteLLM table) | DEEPSEEK_API_KEY (new) | optional | 3 attempts |
| Open-weight, local | gpt-oss 20B via Ollama | `ollama_chat/gpt-oss:20b` | free | none | 1 attempt | 3 attempts |

**GPT-6.1 Sol is deliberate:** it's the model all ten v1 pilots used (10/10 first-try passes). Its
v2 score is the cleanest before/after evidence that the new tasks are harder.

**Local model:** gpt-oss 20B needs roughly 16 GB of free memory. It will be slow, so run it with
`--jobs 1`. It anchors the bottom of the table for free.

**Optional additions** if budget allows: Claude Sonnet 5.5 (`claude-sonnet-5-5`, 2/10) and GPT-6.1
Terra (`gpt-6.1-terra`, 1/5) show the price/score curve within each vendor. GLM-5.3 and Kimi K3 are
strong open-weight alternatives, via OpenRouter (would need an `OPENROUTER_API_KEY`).

## Cost estimate (rough; replaced by measured numbers after the checkpoint)

Assumes about 40 agent steps per attempt with prompt caching, roughly the equivalent of 0.2M
full-price input plus 20K output tokens per attempt. Real tasks will vary a lot; the checkpoint run
measures the true per-attempt cost, and the full-run budget gets set from that.

| Run | Attempts | Estimate |
|---|---|---|
| Checkpoint: Opus + Sol on ~15 tasks, 1 attempt | 30 | ~$25 |
| Full: workhorses ×3, ceilings ×1, DeepSeek ×3, 35 tasks | 385 | ~$400 |

Every run requires `--max-cost`, a hard total cap: the run stops when it's reached and resumes from
where it stopped with the same `--run-id`. Each attempt is also capped (`--cost-per-attempt`, default
$5); an attempt that hits its own cap counts as a failure, like running out of time.

## Commands

```sh
# checkpoint (Nov 12)
kernelmind run --agent mini --model claude-opus-5-5 --max-cost 20 --run-id ckpt-opus
kernelmind run --agent mini --model gpt-6.1-sol     --max-cost 10 --run-id ckpt-sol
kernelmind run --agent mini --model ollama_chat/gpt-oss:20b --max-cost 1 --jobs 1 --run-id ckpt-gptoss
kernelmind report results/ckpt-*
```

Fairness rules: same scaffold (mini-swe-agent, `mini.yaml`), same limits (150 steps, task time
limits), provider-default reasoning settings, no per-model prompt tuning.

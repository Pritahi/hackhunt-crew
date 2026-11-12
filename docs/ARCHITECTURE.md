> WORK IN PROGRESS: this document predates the corrected benchmark.
> Fixture pages are illustrative, not official. Old savings/quality claims are not validated.

# Architecture

## The task

Evaluating one hackathon candidate takes four different kinds of judgment
(facts, rules, adversarial risk, build planning), and later agents need what
earlier agents found. The ad-hoc way to wire that is to pass the whole
dossier to every agent. Prompt size then grows with every agent, every
candidate, and every run - the multi-agent token tax Meko is built to cut.

## Two modes, one variable

```
                baseline                              meko
page text ───►  Scout (full dossier in prompt)        Scout (targeted context_search)
                  │ writes output into next prompt      │ writes trace + memory to datapack
                Verifier (dossier + scout out)        Verifier (context_search + memory_search)
                  │                                     │ writes trace + memory
                RedTeam (dossier + both outs)         RedTeam (targeted recall of failure patterns)
                  │                                     │ writes trace + memory
                Builder (dossier + all outs)          Builder (recalls reusable assets)
```

Agent system prompts, the candidate fixture, the model and temperature are
identical across modes. The only difference is how context is assembled,
which is what the benchmark measures.

## Learning across runs

- **Baseline** keeps an in-process list of "learnings" and re-sends the whole
  list with every prompt. It is still an LLM call per agent per candidate,
  every run.
- **Meko** starts warm on run 2+: a prior verdict is recalled from memory and
  reused (fewer LLM calls), and retrieval surfaces only the snippets that
  match (fewer prompt tokens). This mirrors Meko's published direction
  (93% fewer tokens sent, 45% fewer LLM calls through context reuse); the
  benchmark measures this crew's own numbers.

## Token accounting

No estimates. Every Groq response carries metered `usage.prompt_tokens` /
`usage.completion_tokens`; the ledger sums them per mode and per run. In meko
mode each call is also attached to its Meko conversation trace via
`track_token_usage`, so the portal's trace view shows cost next to reasoning.

## Quality gate

A benchmark that wins by getting worse is worthless. `src/metrics.py`
compares every verdict against the fixture's hand-set ground truth and
requires cross-mode accuracy to match before the token savings count.

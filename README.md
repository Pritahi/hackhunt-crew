# HackHunt Crew

**ContextCon 2026 entry - Theme 08: "Do More With Fewer Tokens"** (YugabyteDB Meko x HackerEarth)

A crew of four AI agents that evaluates hackathon candidates for a solo
builder - the kind of work that normally means every agent re-reading every
page and every other agent's full output. The crew runs in two modes on the
identical task and candidate set, and the benchmark measures the difference:

| Mode | How agents get context |
|---|---|
| `baseline` | Current page for Scout, prior agent outputs, plus a growing dump of concise facts/verdicts learned on every earlier candidate is stuffed into each prompt. |
| `meko` | Agents retrieve only what they need from one shared [Meko](https://mekodata.ai) datapack and write back what they learn. |

The same 24 illustrative fixtures, prompts, fixed model and temperature.
Only context assembly differs. Three sequential passes test retained context,
not three independent trials. Fixture labels are not current event advice.

## The agents

1. **Scout** - extracts structured facts from a hackathon's page (prizes,
   eligibility, deadlines, format).
2. **Verifier** - checks the facts against 7 hard entry criteria
   (non-student eligible, online, free, cash prize, solo-allowed, deadline
   open, no face/voice requirement).
3. **RedTeam** - attacks the candidate: hidden costs, prize-payment traps,
   eligibility gotchas. Can kill a candidate outright.
4. **Builder** - for survivors, drafts a build plan that reuses what the
   crew already knows.

## What Meko does (mapped to the judging rubric)

- **Conversations** - every agent turn is saved with its input, output,
  reasoning and plan (`conversation_create` / `conversation_add_message`).
- **Memory** - durable facts and verdicts are promoted from turns
  (`memory_add`) and recalled across agents and across runs (`memory_search`).
  Later passes start warm but every verdict is re-evaluated from the page.
  Candidate-specific conversation filters prevent unrelated deadline leakage.
- **Knowledge base** - the crew's entry criteria live as a searchable shared
  document (`knowledgebase_upload_document` / `knowledgebase_search`).
- **Artifacts** - each candidate's final report is stored whole
  (`artifact_put`) and can be fetched back by hash.
- **Decision traces + token attribution** - every LLM call's metered token
  spend is attached to its conversation trace (`track_token_usage`), so the
  portal can answer "why did the agent do that, and what did it cost?"
- **Context isolation** - memory search uses a candidate-specific conversation
  filter shared by all four agents, while source evidence overrides memory.

## Results

Prospective held-out v4: **74.0% fewer client LLM tokens**, Meko **36/36**
correct verdicts versus full-history baseline **35/36**, with 120 successful
LLM calls in each mode. Twelve new synthetic fixtures, three sequential passes.
See [full table](results/heldout-v4/RESULTS.md), [raw reports](results/heldout-v4/)
and the [plan frozen before testing](docs/VALIDATION_PLAN.md).

| Mode | Pass 1 tokens | Pass 2 | Pass 3 | Total |
|---|---:|---:|---:|---:|
| Full-history | 61,483 | 136,890 | 212,685 | 411,058 |
| Scoped Meko | 31,891 | 38,250 | 36,623 | 106,764 |

This is a small synthetic test against a deliberately naive full-history
baseline, not general production evidence. Passes are sequential, not
independent trials. See measurement boundaries below.

**The original failure remains visible.** Development v3 reduced client tokens
86.2% but lowered accuracy from 69/72 to 65/72. That failed the quality bar.
[Original results](results/RESULTS.md) are unchanged. A deterministic, label-blind
consistency gate over Scout facts was then developed. Post-hoc development
rescoring is 69/72 in both modes, explicitly [retrospective](results/post-hoc-gate.json).
The separate held-out v4 result above was measured only after that gate froze.

## Reproduce

```bash
pip install -r requirements.txt
cp .env.example .env  # fill in locally
set -a; source .env; set +a  # export credentials; never commit .env
python run_benchmark.py --mode both --runs 3 --dataset heldout.json \
  --outdir results/my-heldout-run --decision-policy gated
```

- LLM: Gemini free tier (`gemini-3.1-flash-lite`), temperature 0. No automatic
  model switching during a comparison. Groq is an optional alternative for a
  separate experiment. Quota errors stop the chunk rather than hide in retries.
- Meko: free tier at `https://mcp.mekodata.ai/mcp` (create a datapack and an
  API key in the [Meko cloud portal](https://cloud.mekodata.ai)).

## Notes on the fixture

`data/pages/*.txt` are **illustrative benchmark fixtures, not official sources**.
The first eight are condensed, previously assembled examples inspired by named
competitions; their external accuracy has not been independently verified.
The remaining sixteen are fictional synthetic scenarios designed to exercise
criterion failures. Organizer names, prizes and dates in those cases are
fictional. Do not use these files to choose real competitions.

Ground truth is hand-labeled from the fixture text against a frozen evaluation
date (2026-11-10) and an explicit hobbyist profile. It is not a statement about
any real person's employment status. Data is visible to both modes; labels are
not included in model prompts. This small, task-specific test does not establish
general LLM quality or production savings.

Earlier measurements in `results/diagnostic-v2/` are superseded diagnostics:
they used unpersisted baseline context, mixed model fallbacks and unscoped
memory recall. They must not be cited as final savings. Corrected development and prospective held-out results are linked above.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the design and
[docs/MEKO_USAGE.md](docs/MEKO_USAGE.md) for the full Meko feature mapping.

### Measurement boundaries

Token counts are provider-reported successful LLM completion usage for completed
candidate evaluations. They exclude Meko backend inference/embedding tokens,
HTTP overhead, retries and discarded interrupted candidate attempts. Meko
latency and end-to-end cost are not represented by the LLM token comparison.
Both modes see the same current page and prior agent outputs; baseline also
gets all earlier concise fact/verdict learnings, while Meko retrieves up to five
within the current candidate scope. This is an intentionally naive full-history
baseline, not a claim against optimized local retrieval.

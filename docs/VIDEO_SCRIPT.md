> WORK IN PROGRESS: this document predates the corrected benchmark.
> Fixture pages are illustrative, not official. Old savings/quality claims are not validated.

# Demo video script (target: 4 minutes, screen recording + TTS narration, no face)

Judging: Presentation is 10% - clear video and documentation.

## 0:00-0:25 - The problem
Terminal split screen. Left: a multi-agent run where every prompt carries the
full dossier (token counter spinning up). Narration: "Multi-agent systems
pass whole conversation histories to each other. Every agent added makes
every other agent more expensive. We measured it."

## 0:25-1:00 - Meet the crew
Show README agent diagram. Narration: "HackHunt Crew evaluates hackathon
candidates - Scout extracts facts, Verifier checks the rules, RedTeam attacks,
Builder plans. Four agents that all need what the others learned."

## 1:00-2:00 - Same task, two modes
Screen: `python run_benchmark.py --mode both --runs 2` running.
Narration: "Same eight candidates, same prompts, same model, temperature zero.
Baseline stuffs the full dossier into every prompt. The Meko run retrieves
only what each agent needs from one shared datapack."

## 2:00-3:00 - Inside the datapack
Meko portal: conversation traces with reasoning + token costs, memories
written by one agent recalled by another, the criteria knowledge doc, the
report artifacts. Narration: "Every turn is a trace with its reasoning and
its token cost. One agent's learning becomes every agent's advantage."

## 3:00-3:45 - The numbers
results/RESULTS.md table. Narration reads the three headline numbers:
token reduction %, LLM call reduction %, quality-equal check.

## 3:45-4:00 - Wrap
Narration: "93% fewer tokens is the claim on the page. Here are the numbers
we measured ourselves, on a real task, with the quality gate on."
End card: repo URL.

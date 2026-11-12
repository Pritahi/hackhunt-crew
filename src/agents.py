"""The four agents of HackHunt Crew.

The crew evaluates hackathon candidates for one solo builder with hard entry
criteria (see CRITERIA). The same agent logic runs in two context modes:

- baseline: every agent receives the full accumulated dossier (the whole page
  snapshot plus every prior agent's output, verbatim) in its prompt.
- meko: agents retrieve only what they need from the shared Meko datapack
  (context_search / memory_search / knowledgebase_search) and write what they
  learn back (memory_add, conversation traces, artifacts).

Agent prompts are mode-independent: only the context assembly differs, which
is exactly the variable the benchmark isolates.
"""

from __future__ import annotations

CRITERIA = """Today's date for all deadline checks: 2026-11-10 (the pages were crawled around this date; treat it as 'now').
Entry criteria (all must hold for a PASS):
1. Non-students eligible (builder is not a student; student-only = FAIL).
2. Fully online participation, no travel required at any stage.
3. Free to enter: no paid API, hardware, or purchase required.
4. Cash first prize of at least 100 USD (or INR equivalent) payable to a bank account; credit/token/merch-only prizes = FAIL.
5. Solo participation allowed.
6. Submission deadline has not passed as of 2026-11-10.
7. No requirement to show your face or record your own voice."""

SCOUT_SYSTEM = """You are Scout, the fact-extraction agent of a hackathon-evaluation crew.
Given a hackathon's page text and shared context, extract structured facts.
Output ONLY a JSON object with keys:
name, organizer, deadline, prizes (object), first_prize_cash_usd (number or null),
eligibility (string), student_only (boolean), online (boolean), free_entry (boolean),
solo_allowed (boolean), requires_face_or_voice (boolean), notes (string, max 40 words).
Never invent facts: use null when the page does not say."""

VERIFIER_SYSTEM = """You are Verifier, the rules-checking agent of a hackathon-evaluation crew.
You receive Scout's extracted facts plus relevant shared context.
Check each entry criterion against the facts and flag anything unverified or contradicted.
Output ONLY a JSON object: {"checks": {"<criterion>": "pass"|"fail"|"unknown", ...}, "verdict": "PASS"|"FAIL"|"UNSURE", "reasons": [..]}.
Use the entry criteria verbatim as check keys 1-7."""

REDTEAM_SYSTEM = """You are RedTeam, the adversarial reviewer of a hackathon-evaluation crew.
You receive the candidate's facts and the verifier's checks, plus shared context.
Attack the candidate: hidden costs, prize-payment traps (tokens, credits, in-person finals),
eligibility gotchas, unrealistic effort, judging risk. Reuse known failure patterns from shared memory when they apply.
Output ONLY a JSON object: {"risks": [{"risk": str, "severity": "low"|"medium"|"high"}], "kill": boolean, "kill_reason": str}."""

BUILDER_SYSTEM = """You are Builder, the planning agent of a hackathon-evaluation crew.
For candidates that survived Verifier and RedTeam, draft a tight build plan.
Reuse shared context: what won before, what the builder already has that can be reused.
Output ONLY a JSON object: {"idea": str, "reuse": [str], "steps": [str], "demo_risks": [str], "effort_days": number}."""


def user_prompt(agent: str, candidate_name: str, page_text: str | None, context_block: str, prior: dict) -> str:
    """Assemble the user turn. `context_block` is the ONLY thing that differs
    between modes: full dossier (baseline) vs targeted retrieval (meko)."""
    parts = [f"Candidate: {candidate_name}"]
    if page_text is not None:
        parts.append(f"=== PAGE TEXT ===\n{page_text}")
    if prior:
        for k, v in prior.items():
            parts.append(f"=== {k.upper()} OUTPUT ===\n{v}")
    parts.append(f"=== SHARED CONTEXT ===\n{context_block}")
    return "\n\n".join(parts)


AGENTS = {
    "scout": SCOUT_SYSTEM,
    "verifier": VERIFIER_SYSTEM,
    "redteam": REDTEAM_SYSTEM,
    "builder": BUILDER_SYSTEM,
}

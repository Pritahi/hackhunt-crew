"""Crew orchestrator: runs the 4 agents over every candidate in two modes.

baseline  - context is assembled the way ad-hoc multi-agent systems do it:
            the whole dossier (page text + every prior agent output, plus a
            full dump of everything the crew has ever learned) is stuffed
            into each prompt. Context per agent grows with every agent added.
meko      - agents retrieve only what they need from the shared Meko datapack
            and write back what they learn: conversation traces with
            reasoning, durable memories, a criteria knowledge doc, and the
            final report as an artifact. On later runs the crew starts warm:
            verdicts and failure patterns are recalled from memory instead of
            being re-derived, which cuts both tokens and LLM calls.
"""

from __future__ import annotations

import base64
import json
import re
import uuid

from .agents import AGENTS, CRITERIA, user_prompt
from .llm import GroqLLM
from .meko_client import MekoClient

AGENT_ORDER = ["scout", "verifier", "redteam", "builder"]


def _extract_json(text: str) -> dict:
    """Parse the agent's JSON output, tolerating code fences."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"_raw": text, "_parse_error": True}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"_raw": text, "_parse_error": True}


class Crew:
    def __init__(self, llm: GroqLLM, meko: MekoClient | None = None, mode: str = "baseline"):
        assert mode in {"baseline", "meko"}
        self.llm = llm
        self.meko = meko
        self.mode = mode
        self.learnings: list[str] = []  # baseline mode's in-process "memory dump"

    # -- context assembly: the one variable under test ----------------------

    def _context(self, agent: str, candidate: dict) -> str:
        if self.mode == "baseline":
            blob = [CRITERIA, *self.learnings]
            return "\n\n".join(blob)
        assert self.meko is not None
        query = f"{candidate['name']} hackathon {agent} criteria eligibility prize deadline"
        found = self.meko.context_search(query, agent_id=agent)
        return f"{CRITERIA}\n\n=== RECALLED FROM SHARED MEKO CONTEXT ===\n{found}"

    # -- per-agent step -------------------------------------------------------

    def _step(self, agent: str, candidate: dict, run: int, prior: dict, conversation_id: str | None) -> dict:
        page_text = candidate["page_text"] if agent == "scout" else None
        prompt = user_prompt(agent, candidate["name"], page_text, self._context(agent, candidate), prior)
        plan = [f"retrieve shared context for {candidate['name']}", f"produce {agent} analysis", "write learnings back"]
        out_text = self.llm.chat(
            [{"role": "system", "content": AGENTS[agent]}, {"role": "user", "content": prompt}],
            agent=agent,
            candidate=candidate["name"],
            run=run,
            mode=self.mode,
        )
        parsed = _extract_json(out_text)
        if self.mode == "meko" and self.meko is not None and conversation_id:
            usage = self.llm.ledger.records[-1]
            self.meko.conversation_add_message(
                conversation_id,
                agent_id=agent,
                input_text=prompt[:4000],
                output_text=out_text[:4000],
                reasoning=f"{agent} step for {candidate['name']} in {self.mode} mode, run {run}",
                plan=plan,
                metadata={"candidate": candidate["name"], "run": run, "mode": self.mode},
            )
            self.meko.track_token_usage(
                conversation_id,
                agent_id=agent,
                usage={
                    "model": usage.model,
                    "prompt_tokens": usage.prompt_tokens,
                    "completion_tokens": usage.completion_tokens,
                    "total_tokens": usage.total_tokens,
                },
            )
        return parsed

    def _learn(self, text: str, agent: str, conversation_id: str | None) -> None:
        if self.mode == "baseline":
            self.learnings.append(f"[{agent}] {text}")
        elif self.meko is not None:
            self.meko.memory_add(text, agent_id=agent, conversation_id=conversation_id)

    # -- one candidate -----------------------------------------------------

    def evaluate(self, candidate: dict, run: int) -> dict:
        conversation_id = None
        if self.mode == "meko" and self.meko is not None:
            # Warm-start: recall a prior verdict for this candidate, if any.
            prior_verdict = self.meko.memory_search(f"final verdict for {candidate['name']}", agent_id="crew", limit=3)
            if run > 1 and prior_verdict and '"reused_ok": true' in prior_verdict:
                return {"candidate": candidate["name"], "verdict": "REUSED", "detail": prior_verdict, "reused": True}
            conversation_id = self.meko.conversation_create(
                agent_id="crew",
                title=f"evaluate {candidate['name']} (run {run})",
                session_id=f"run-{run}-{uuid.uuid4().hex[:8]}",
                metadata={"candidate": candidate["name"], "run": run, "mode": self.mode},
            )

        prior: dict = {}
        outputs: dict = {}
        for agent in AGENT_ORDER:
            if agent == "builder" and outputs.get("_eliminated"):
                break
            parsed = self._step(agent, candidate, run, prior, conversation_id)
            outputs[agent] = parsed
            prior[agent] = json.dumps(parsed)
            if agent == "scout":
                self._learn(
                    f"Scout facts for {candidate['name']}: {json.dumps({k: parsed.get(k) for k in ('student_only','free_entry','online','solo_allowed','first_prize_cash_usd','deadline')})}",
                    agent, conversation_id,
                )
            if agent == "verifier":
                self._learn(f"Verifier verdict for {candidate['name']}: {parsed.get('verdict')} - {parsed.get('reasons')}", agent, conversation_id)
            if agent == "redteam" and parsed.get("kill"):
                self._learn(f"RedTeam killed {candidate['name']}: {parsed.get('kill_reason')}", agent, conversation_id)
                outputs["_eliminated"] = True

        verdict = self._final_verdict(outputs)
        report = {"candidate": candidate["name"], "mode": self.mode, "run": run, "verdict": verdict, "agents": outputs}
        if self.mode == "meko" and self.meko is not None:
            blob = base64.b64encode(json.dumps(report, indent=2).encode()).decode()
            self.meko.artifact_store(f"report-{candidate['id']}-run{run}.json", blob, agent_id="crew")
            self.meko.memory_add(
                f'final verdict for {candidate["name"]}: {verdict}. {json.dumps(outputs.get("verifier", {}))[:300]} "reused_ok": true',
                agent_id="crew", conversation_id=conversation_id,
            )
        return report

    @staticmethod
    def _final_verdict(outputs: dict) -> str:
        v = outputs.get("verifier", {}).get("verdict", "UNSURE")
        killed = outputs.get("redteam", {}).get("kill", False)
        if v == "FAIL" or killed:
            return "FAIL"
        if v == "PASS":
            return "PASS"
        return "UNSURE"

    # -- one-shot knowledge seeding (meko mode) ------------------------------

    def seed_knowledge(self) -> None:
        if self.mode != "meko" or self.meko is None:
            return
        doc = base64.b64encode(f"# HackHunt Crew entry criteria\n\n{CRITERIA}\n".encode()).decode()
        self.meko.knowledge_upload("entry-criteria.md", doc, agent_id="crew")

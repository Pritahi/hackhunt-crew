"""Crew orchestrator: runs the 4 agents over every candidate in two modes.

baseline  - context is assembled the way ad-hoc multi-agent systems do it:
            the whole dossier (page text + every prior agent output, plus a
            full dump of everything the crew has ever learned) is stuffed
            into each prompt. Context per agent grows with every agent added.
meko      - agents retrieve only what they need from the shared Meko datapack
            and write back what they learn. Each agent owns one conversation
            per run (Meko conversations are owner-scoped); memories, the
            knowledge base and artifacts are shared datapack-wide. On later
            runs the crew starts warm: verdicts and failure patterns are
            recalled from memory instead of being re-derived, which cuts both
            tokens and LLM calls.
"""

from __future__ import annotations

import json
import re

from .agents import AGENTS, CRITERIA, user_prompt
from .llm import LLM
from .meko_client import MekoClient

AGENT_ORDER = ["scout", "verifier", "redteam", "builder"]


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return {"_raw": text, "_parse_error": True}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {"_raw": text, "_parse_error": True}


class Crew:
    def __init__(self, llm: LLM, meko: MekoClient | None = None, mode: str = "baseline"):
        assert mode in {"baseline", "meko"}
        self.llm = llm
        self.meko = meko
        self.mode = mode
        self.learnings: list[str] = []  # baseline mode's in-process memory dump
        self._conversations: dict[str, str] = {}  # "agent:run" -> conversation id

    # -- conversation management (meko mode; conversations are owner-scoped) --

    def _conversation(self, agent: str, run: int) -> str:
        key = f"{agent}:{run}"
        if key not in self._conversations:
            assert self.meko is not None
            self._conversations[key] = self.meko.conversation_create(
                agent_id=agent,
                title=f"{agent} - run {run} ({self.mode} mode)",
                session_id=f"{self.mode}-run-{run}",
                metadata={"agent": agent, "run": run, "mode": self.mode},
            )
        return self._conversations[key]

    # -- context assembly: the one variable under test ----------------------

    def _context(self, agent: str, candidate: dict, run: int) -> str:
        if self.mode == "baseline":
            return "\n\n".join([CRITERIA, *self.learnings])
        cid = self._conversation(agent, run)
        query = f"{candidate['name']} hackathon eligibility prize deadline entry criteria"
        raw = self.meko.memory_search(query, conversation_id=cid, agent_id=agent, limit=5)
        try:
            items = json.loads(raw).get("results", [])
            seen: set[str] = set()
            mems: list[str] = []
            for it in items:
                t = it.get("memory", "") if isinstance(it, dict) else str(it)
                if t and t not in seen:
                    seen.add(t)
                    mems.append(t)
            recalled = "\n".join(f"- {t}" for t in mems[:5])
        except (json.JSONDecodeError, KeyError, TypeError):
            recalled = raw[:2000]
        return f"{CRITERIA}\n\n=== RECALLED FROM SHARED MEKO MEMORY ===\n{recalled or '(nothing shared yet)'}"

    # -- per-agent step -------------------------------------------------------

    def _step(self, agent: str, candidate: dict, run: int, prior: dict) -> dict:
        page_text = candidate["page_text"] if agent == "scout" else None
        prompt = user_prompt(agent, candidate["name"], page_text, self._context(agent, candidate, run), prior)
        out_text = self.llm.chat(
            [{"role": "system", "content": AGENTS[agent]}, {"role": "user", "content": prompt}],
            agent=agent,
            candidate=candidate["name"],
            run=run,
            mode=self.mode,
        )
        if self.mode == "meko" and self.meko is not None:
            cid = self._conversation(agent, run)
            usage = self.llm.ledger.records[-1]
            self.meko.conversation_add_message(
                cid,
                agent_id=agent,
                input_text=prompt[:4000],
                output_text=out_text[:4000],
                reasoning=f"{agent} step for {candidate['name']}, run {run}",
                plan=[f"retrieve shared context for {candidate['name']}", f"produce {agent} analysis", "write learnings back"],
                metadata={"candidate": candidate["name"], "run": run, "mode": self.mode},
            )
            self.meko.track_token_usage(
                cid,
                name=f"llm-{agent}",
                model=usage.model,
                input_tokens=usage.prompt_tokens,
                output_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            )
        return _extract_json(out_text)

    def _learn(self, text: str, agent: str, run: int) -> None:
        if self.mode == "baseline":
            self.learnings.append(f"[{agent}] {text}")
        elif self.meko is not None:
            self.meko.memory_add(text, conversation_id=self._conversation(agent, run), agent_id=agent)

    # -- one candidate -----------------------------------------------------

    def evaluate(self, candidate: dict, run: int) -> dict:
        if self.mode == "meko" and self.meko is not None and run > 1:
            # Warm start: reuse a memorized verdict instead of re-deriving it.
            cid = self._conversation("crew", run)
            recalled = self.meko.memory_search(
                f"final verdict for {candidate['name']}", conversation_id=cid, agent_id="crew", limit=3
            )
            if '"reused_ok": true' in recalled:
                m = re.search(r"final verdict for .*: (PASS|FAIL|UNSURE)", recalled)
                return {
                    "candidate": candidate["name"],
                    "verdict": m.group(1) if m else "UNSURE",
                    "reused": True,
                    "detail": recalled[:500],
                }

        prior: dict = {}
        outputs: dict = {}
        for agent in AGENT_ORDER:
            if agent == "builder" and outputs.get("_eliminated"):
                break
            parsed = self._step(agent, candidate, run, prior)
            outputs[agent] = parsed
            prior[agent] = json.dumps(parsed)
            if agent == "scout":
                facts = {k: parsed.get(k) for k in ("student_only", "free_entry", "online", "solo_allowed", "first_prize_cash_usd", "deadline")}
                self._learn(f"Scout facts for {candidate['name']}: {json.dumps(facts)}", agent, run)
            if agent == "verifier":
                self._learn(f"Verifier verdict for {candidate['name']}: {parsed.get('verdict')} - {parsed.get('reasons')}", agent, run)
            if agent == "redteam" and parsed.get("kill"):
                self._learn(f"RedTeam killed {candidate['name']}: {parsed.get('kill_reason')}", agent, run)
                outputs["_eliminated"] = True

        verdict = self._final_verdict(outputs)
        report = {"candidate": candidate["name"], "mode": self.mode, "run": run, "verdict": verdict, "agents": outputs}
        if self.mode == "meko" and self.meko is not None:
            cid = self._conversation("crew", run)
            self.meko.artifact_put(
                f"report-{candidate['id']}-run{run}.json",
                json.dumps(report, indent=2).encode(),
                "application/json",
                conversation_id=cid,
                agent_id="crew",
            )
            self.meko.memory_add(
                f'final verdict for {candidate["name"]}: {verdict}. {json.dumps(outputs.get("verifier", {}))[:300]} "reused_ok": true',
                conversation_id=cid,
                agent_id="crew",
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
        cid = self._conversation("crew", 0)
        self.meko.knowledge_upload(
            "entry-criteria.md",
            f"# HackHunt Crew entry criteria\n\n{CRITERIA}\n".encode(),
            conversation_id=cid,
            agent_id="crew",
        )

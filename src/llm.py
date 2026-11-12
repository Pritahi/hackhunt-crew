"""LLM access (Groq, free tier) with per-call token accounting.

Every chat call is recorded in a TokenLedger with the exact prompt/completion
token counts returned by the API, so the benchmark never estimates: it sums
what the provider metered.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


@dataclass
class CallRecord:
    agent: str
    candidate: str
    run: int
    mode: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


@dataclass
class TokenLedger:
    records: list[CallRecord] = field(default_factory=list)

    def add(self, record: CallRecord) -> None:
        self.records.append(record)

    def summary(self, mode: str, run: int | None = None) -> dict:
        recs = [r for r in self.records if r.mode == mode and (run is None or r.run == run)]
        return {
            "mode": mode,
            "run": run,
            "llm_calls": len(recs),
            "prompt_tokens": sum(r.prompt_tokens for r in recs),
            "completion_tokens": sum(r.completion_tokens for r in recs),
            "total_tokens": sum(r.total_tokens for r in recs),
        }


class GroqLLM:
    def __init__(self, api_key: str, model: str, ledger: TokenLedger):
        self.api_key = api_key
        self.model = model
        self.ledger = ledger
        self._client = httpx.Client(timeout=httpx.Timeout(120.0, connect=20.0))

    def chat(
        self,
        messages: list[dict],
        *,
        agent: str,
        candidate: str,
        run: int,
        mode: str,
        max_tokens: int = 1500,
        temperature: float = 0.0,
    ) -> str:
        """One metered chat completion. Temperature 0 keeps verdicts deterministic."""
        started = time.monotonic()
        resp = self._client.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
        )
        latency_ms = int((time.monotonic() - started) * 1000)
        resp.raise_for_status()
        data = resp.json()
        usage = data.get("usage", {})
        self.ledger.add(
            CallRecord(
                agent=agent,
                candidate=candidate,
                run=run,
                mode=mode,
                model=self.model,
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                latency_ms=latency_ms,
            )
        )
        return data["choices"][0]["message"]["content"]

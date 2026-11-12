"""LLM access with per-call token accounting and retry-on-overload.

Two free-tier providers are supported, selected per run:
- Groq (GROQ_API_KEY, e.g. llama-3.3-70b-versatile)
- Google AI Studio Gemini (GEMINI_API_KEY, e.g. gemini-2.5-flash), via the
  OpenAI-compatible endpoint. The free tier 503s/429s under load, so every
  call retries with exponential backoff.

Every successful call is recorded in a TokenLedger with the exact
prompt/completion token counts returned by the provider, so the benchmark
never estimates: it sums what the provider metered.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import httpx

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"


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


class LLM:
    """One metered chat-completions client for either free-tier provider."""

    def __init__(self, provider: str, api_key: str, model: str, ledger: TokenLedger):
        assert provider in {"groq", "gemini"}
        self.provider = provider
        self.api_key = api_key
        self.model = model
        self.ledger = ledger
        self._url = GROQ_URL if provider == "groq" else GEMINI_URL
        self._client = httpx.Client(timeout=httpx.Timeout(45.0, connect=10.0))

    @classmethod
    def from_env(cls, ledger: TokenLedger) -> "LLM":
        import os

        provider = os.environ.get("LLM_PROVIDER", "gemini")
        if provider == "groq":
            return cls(provider, os.environ["GROQ_API_KEY"], os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile"), ledger)
        return cls(provider, os.environ["GEMINI_API_KEY"], os.environ.get("GEMINI_MODEL", "gemini-3.1-flash-lite"), ledger)

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
        """One metered chat completion with backoff on 429/5xx.
        Temperature 0 keeps verdicts deterministic across modes."""
        delay = 5.0
        last_err: Exception | None = None
        for attempt in range(6):
            started = time.monotonic()
            try:
                resp = self._client.post(
                    self._url,
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={"model": self.model, "messages": messages, "max_tokens": max_tokens, "temperature": temperature},
                )
                latency_ms = int((time.monotonic() - started) * 1000)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(f"transient {resp.status_code}", request=resp.request, response=resp)
                resp.raise_for_status()  # non-transient errors (404 etc.) surface immediately, no retry
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
            except httpx.HTTPStatusError as e:
                if e.response is not None and e.response.status_code == 404 and self.provider == "gemini" and self.model != "gemini-3.8-flash":
                    self.model = "gemini-3.8-flash"  # deprecated/renamed model: fall back once
                    continue
                if e.response is not None and e.response.status_code not in (429, 500, 502, 503, 504):
                    raise  # permanent error: fail fast instead of burning the retry budget
                last_err = e
                time.sleep(delay)
                delay = min(delay * 2, 90.0)
            except httpx.TransportError as e:
                # Read timeouts and connection errors: fail fast, and after two
                # consecutive stalls move to the fallback model - some prompts
                # stall one model but not another.
                last_err = e
                if attempt >= 1 and self.provider == "gemini" and self.model != "gemini-3.8-flash":
                    self.model = "gemini-3.8-flash"
                time.sleep(delay)
                delay = min(delay * 2, 90.0)
        raise RuntimeError(f"LLM call failed after retries ({self.provider}/{self.model}): {last_err}")


# Backwards-compatible alias.
GroqLLM = LLM

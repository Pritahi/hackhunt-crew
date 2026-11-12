"""Minimal MCP (Streamable HTTP) client for the Meko context engine.

Meko exposes one hosted endpoint for every account and datapack:
    https://mcp.mekodata.ai/mcp
Authentication is a user API key sent as `Authorization: Bearer <key>`.
A User-Agent header is required by the server. The datapack is selected per
tool call via the `datapack_id` argument, not via the URL.

Only what HackHunt Crew needs is implemented: initialize, tools/list and
tools/call, with both `application/json` and `text/event-stream` responses.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field

import httpx

PROTOCOL_VERSION = "2025-03-26"


@dataclass
class ToolCallResult:
    """Parsed result of a Meko MCP tool call."""

    text: str
    is_error: bool = False
    latency_ms: int = 0
    raw: dict = field(default_factory=dict)


class MekoClient:
    def __init__(self, api_key: str, datapack_id: str, base_url: str = "https://mcp.mekodata.ai/mcp"):
        self.api_key = api_key
        self.datapack_id = datapack_id
        self.base_url = base_url
        self._session_id: str | None = None
        self._next_id = 0
        self._client = httpx.Client(timeout=httpx.Timeout(60.0, connect=20.0))
        self.calls: list[dict] = []  # lightweight client-side audit log

    # -- transport ---------------------------------------------------------

    def _headers(self) -> dict:
        h = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "hackhunt-crew/1.0",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self._session_id:
            h["Mcp-Session-Id"] = self._session_id
        return h

    def _rpc(self, method: str, params: dict | None = None) -> dict:
        self._next_id += 1
        payload = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            payload["params"] = params
        started = time.monotonic()
        resp = self._client.post(self.base_url, headers=self._headers(), json=payload)
        latency_ms = int((time.monotonic() - started) * 1000)
        if sid := resp.headers.get("mcp-session-id"):
            self._session_id = sid
        resp.raise_for_status()
        body = self._parse_body(resp)
        self.calls.append({"method": method, "latency_ms": latency_ms, "ok": "error" not in body})
        if "error" in body:
            raise RuntimeError(f"MCP {method} failed: {body['error']}")
        return body.get("result", {})

    @staticmethod
    def _parse_body(resp: httpx.Response) -> dict:
        ctype = resp.headers.get("content-type", "")
        if "text/event-stream" in ctype:
            # SSE: concatenate data: lines of the terminal event.
            data = ""
            for line in resp.text.splitlines():
                if line.startswith("data:"):
                    data += line[5:].strip()
            return json.loads(data) if data else {}
        return resp.json() if resp.text else {}

    # -- public API --------------------------------------------------------

    def initialize(self) -> dict:
        return self._rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "hackhunt-crew", "version": "1.0.0"},
            },
        )

    def list_tools(self) -> list[dict]:
        return self._rpc("tools/list").get("tools", [])

    def call_tool(self, name: str, **arguments) -> ToolCallResult:
        arguments.setdefault("datapack_id", self.datapack_id)
        started = time.monotonic()
        result = self._rpc("tools/call", {"name": name, "arguments": arguments})
        latency_ms = int((time.monotonic() - started) * 1000)
        parts = result.get("content", [])
        text = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
        return ToolCallResult(text=text, is_error=bool(result.get("isError")), latency_ms=latency_ms, raw=result)

    # -- convenience wrappers used by the crew ------------------------------

    def context_search(self, query: str, agent_id: str, conversation_id: str | None = None, limit: int = 8) -> str:
        args: dict = {"query": query, "agent_id": agent_id, "limit": limit}
        if conversation_id:
            args["conversation_id"] = conversation_id
        return self.call_tool("context_search", **args).text

    def memory_add(self, text: str, agent_id: str, conversation_id: str | None = None) -> str:
        args: dict = {"text": text, "agent_id": agent_id}
        if conversation_id:
            args["conversation_id"] = conversation_id
        return self.call_tool("memory_add", **args).text

    def memory_search(self, query: str, agent_id: str, limit: int = 8) -> str:
        return self.call_tool("memory_search", query=query, agent_id=agent_id, limit=limit).text

    def knowledge_upload(self, filename: str, content_base64: str, agent_id: str) -> str:
        return self.call_tool(
            "knowledgebase_upload_document", filename=filename, content_base64=content_base64, agent_id=agent_id
        ).text

    def knowledge_search(self, query: str, agent_id: str, limit: int = 5) -> str:
        return self.call_tool("knowledgebase_search", query=query, agent_id=agent_id, limit=limit).text

    def conversation_create(self, agent_id: str, title: str, session_id: str, metadata: dict | None = None) -> str:
        result = self.call_tool(
            "conversation_create", agent_id=agent_id, title=title, session_id=session_id, metadata=metadata or {}
        )
        # The tool returns the new conversation id inside its text payload as JSON.
        try:
            return json.loads(result.text).get("conversation_id", "")
        except (json.JSONDecodeError, AttributeError):
            return result.text.strip().strip('"')

    def conversation_add_message(
        self,
        conversation_id: str,
        agent_id: str,
        input_text: str,
        output_text: str,
        reasoning: str = "",
        plan: list[str] | None = None,
        metadata: dict | None = None,
    ) -> None:
        self.call_tool(
            "conversation_add_message",
            conversation_id=conversation_id,
            agent_id=agent_id,
            input=input_text,
            output=output_text,
            reasoning=reasoning,
            plan=plan or [],
            metadata=metadata or {},
        )

    def artifact_store(self, filename: str, content_base64: str, agent_id: str, content_type: str = "application/json") -> str:
        return self.call_tool(
            "artifact_store", filename=filename, content_base64=content_base64, agent_id=agent_id, content_type=content_type
        ).text

    def track_token_usage(self, conversation_id: str, agent_id: str, usage: dict) -> None:
        """Attribute LLM token spend to a conversation trace (decision tracing)."""
        self.call_tool(
            "track_token_usage",
            conversation_id=conversation_id,
            agent_id=agent_id,
            **{k: v for k, v in usage.items() if k in {"prompt_tokens", "completion_tokens", "total_tokens", "model"}},
        )

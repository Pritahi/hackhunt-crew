"""Minimal MCP (Streamable HTTP) client for the Meko context engine.

Meko exposes one hosted endpoint for every account and datapack:
    https://mcp.mekodata.ai/mcp
Authentication is a user API key sent as `Authorization: Bearer <key>`.
A User-Agent header is required by the server. The datapack is selected per
tool call via the `datapack_id` argument, not via the URL.

Verified against the live cloud endpoint on 2026-11-12:
- conversation_* tools are owner-scoped: only the agent_id that created a
  conversation may append to it. The crew therefore keeps one conversation
  per agent per run.
- knowledgebase_upload_document is two-step: the tool returns a presigned S3
  POST target, and the document bytes must be POSTed there to finish.
- track_token_usage takes (conversation_id, name, model, input_tokens,
  output_tokens, total_tokens).
- Artifacts use artifact_put (filename, content_base64, content_type,
  conversation_id).
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from dataclasses import dataclass, field

import httpx

PROTOCOL_VERSION = "2025-03-26"


@dataclass
class ToolCallResult:
    text: str
    is_error: bool = False
    latency_ms: int = 0
    raw: dict = field(default_factory=dict)

    def json(self) -> dict:
        try:
            return json.loads(self.text)
        except (json.JSONDecodeError, TypeError):
            return {}


class MekoClient:
    def __init__(self, api_key: str, datapack_id: str, base_url: str = "https://mcp.mekodata.ai/mcp"):
        self.api_key = api_key
        self.datapack_id = datapack_id
        self.base_url = base_url
        self._session_id: str | None = None
        self._next_id = 0
        self._client = httpx.Client(timeout=httpx.Timeout(60.0, connect=20.0))
        self.calls: list[dict] = []

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
            data = ""
            for line in resp.text.splitlines():
                if line.startswith("data:"):
                    data += line[5:].strip()
            return json.loads(data) if data else {}
        return resp.json() if resp.text else {}

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

    def call_tool(self, tool: str, **arguments) -> ToolCallResult:
        arguments.setdefault("datapack_id", self.datapack_id)
        started = time.monotonic()
        result = self._rpc("tools/call", {"name": tool, "arguments": arguments})
        latency_ms = int((time.monotonic() - started) * 1000)
        parts = result.get("content", [])
        text = "\n".join(p.get("text", "") for p in parts if p.get("type") == "text")
        return ToolCallResult(text=text, is_error=bool(result.get("isError")), latency_ms=latency_ms, raw=result)

    # -- conversations -----------------------------------------------------

    def conversation_create(self, agent_id: str, title: str, session_id: str, metadata: dict | None = None) -> str:
        """Returns the new conversation id. Only `agent_id` may append to it."""
        args: dict = {"agent_id": agent_id, "title": title, "session_id": session_id}
        if metadata:
            args["metadata"] = json.dumps(metadata)  # server expects a string
        r = self.call_tool("conversation_create", **args)
        cid = r.json().get("id")
        if not cid:
            raise RuntimeError(f"conversation_create returned no id: {r.text[:300]}")
        return cid

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
        args: dict = {
            "conversation_id": conversation_id,
            "agent_id": agent_id,
            "input": input_text,
            "output": output_text,
            "reasoning": reasoning,
            "plan": plan or [],
        }
        if metadata:
            args["metadata"] = json.dumps(metadata)  # server expects a string
        self.call_tool("conversation_add_message", **args)

    # -- memory --------------------------------------------------------------

    def memory_add(self, text: str, conversation_id: str, agent_id: str) -> None:
        self.call_tool("memory_add", text=text, conversation_id=conversation_id, agent_id=agent_id)

    def memory_search(self, query: str, conversation_id: str, agent_id: str, limit: int = 8) -> str:
        return self.call_tool(
            "memory_search", query=query, conversation_id=conversation_id, agent_id=agent_id, limit=limit
        ).text

    def context_search(self, query: str, conversation_id: str, agent_id: str, limit: int = 8) -> str:
        return self.call_tool(
            "context_search", query=query, conversation_id=conversation_id, agent_id=agent_id, limit=limit
        ).text

    # -- knowledge base --------------------------------------------------------

    def knowledge_upload(self, filename: str, content: bytes, conversation_id: str, agent_id: str) -> None:
        """Two-step upload: MCP tool returns a presigned POST, then the bytes go to S3."""
        init = self.call_tool(
            "knowledgebase_upload_document",
            filename=filename,
            size=len(content),
            content_hash=hashlib.sha256(content).hexdigest(),
            conversation_id=conversation_id,
            content_head_base64=base64.b64encode(content[:65536]).decode(),
            agent_id=agent_id,
        ).json()
        if init.get("already_uploaded"):
            return  # same content already in the datapack: nothing to do
        url, fields = init.get("url"), init.get("fields")
        if not url or not fields:
            raise RuntimeError(f"knowledgebase_upload_document init failed: {json.dumps(init)[:300]}")
        resp = self._client.post(url, data=fields, files={"file": (filename, content)})
        if resp.status_code >= 300:
            raise RuntimeError(f"knowledge S3 upload failed: {resp.status_code} {resp.text[:200]}")

    def knowledge_search(self, query: str, conversation_id: str, agent_id: str, limit: int = 5) -> str:
        return self.call_tool(
            "knowledgebase_search", query=query, conversation_id=conversation_id, agent_id=agent_id, limit=limit
        ).text

    # -- artifacts and token accounting -----------------------------------------

    def artifact_put(self, filename: str, content: bytes, content_type: str, conversation_id: str, agent_id: str) -> None:
        self.call_tool(
            "artifact_put",
            filename=filename,
            content_base64=base64.b64encode(content).decode(),
            content_type=content_type,
            conversation_id=conversation_id,
            agent_id=agent_id,
        )

    def track_token_usage(
        self, conversation_id: str, name: str, model: str, input_tokens: int, output_tokens: int, total_tokens: int
    ) -> None:
        """Attach metered LLM spend to a conversation trace (decision tracing)."""
        self.call_tool(
            "track_token_usage",
            conversation_id=conversation_id,
            name=name,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )

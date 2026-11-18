"""Optional language-model client for any OpenAI-compatible endpoint.

Works with a local server (Ollama, llama.cpp, vLLM), so privileged documents never have to
leave the machine. Configure with environment variables:

    RECONCILER_LLM_BASE_URL   e.g. http://localhost:11434/v1
    RECONCILER_LLM_MODEL      a model that supports tool calling, for the investigator
    RECONCILER_LLM_API_KEY    optional
    RECONCILER_REVIEW_MODEL   optional: a different model to act as second reviewer of clearances
    RECONCILER_LLM_TIMEOUT    optional: seconds to wait for one reply (default 900). Raise it if
                              models are swapped in and out of GPU memory between calls.
"""
from __future__ import annotations

import json
import os
import urllib.request


def configured() -> bool:
    return bool(os.environ.get("RECONCILER_LLM_BASE_URL") and os.environ.get("RECONCILER_LLM_MODEL"))


class Client:
    def __init__(self, base_url: str | None = None, model: str | None = None,
                 api_key: str | None = None, timeout: int | None = None):
        self.base = (base_url or os.environ["RECONCILER_LLM_BASE_URL"]).rstrip("/")
        self.model = model or os.environ["RECONCILER_LLM_MODEL"]
        self.key = api_key or os.environ.get("RECONCILER_LLM_API_KEY")
        self.timeout = timeout or int(os.environ.get("RECONCILER_LLM_TIMEOUT", "900"))

    def complete(self, messages: list[dict], tools: list[dict] | None = None,
                 temperature: float = 0, seed: int | None = None) -> dict:
        """One chat turn. Returns the assistant message (which may contain tool_calls)."""
        body = {"model": self.model, "temperature": temperature, "messages": messages}
        if seed is not None:
            body["seed"] = seed
        if tools:
            body["tools"] = tools
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = f"Bearer {self.key}"
        req = urllib.request.Request(f"{self.base}/chat/completions",
                                     data=json.dumps(body).encode(), headers=headers)
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return json.load(resp)["choices"][0]["message"]


def reviewer_client() -> Client | None:
    """A client for the second reviewer, if a separate model is configured."""
    model = os.environ.get("RECONCILER_REVIEW_MODEL")
    return Client(model=model) if model else None


def chat(system: str, user: str) -> str:
    msg = Client().complete([{"role": "system", "content": system}, {"role": "user", "content": user}])
    return (msg.get("content") or "").strip()

"""Explicit-call Anthropic Messages client using urllib."""

import json
import os
from urllib.request import Request, urlopen


def anthropic_llm(api_key, model=os.environ.get("WARMOPEN_LLM_MODEL", "claude-haiku-5-5")):
    """Return a text callable; credentials remain in memory and HTTP headers."""
    def complete(prompt):
        payload = {"model": model, "max_tokens": 700,
                   "messages": [{"role": "user", "content": prompt}]}
        request = Request("https://api.anthropic.com/v1/messages",
                          data=json.dumps(payload).encode("utf-8"),
                          headers={"x-api-key": api_key, "anthropic-version": "2023-06-01",
                                   "Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=8.0) as response:
            answer = json.load(response)
        return "".join(block["text"] for block in answer["content"] if block["type"] == "text")

    return complete

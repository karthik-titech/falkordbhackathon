"""Explicit-call urllib client for the JEV decision endpoint."""

import json
from urllib.request import Request, urlopen


def jev_client(api_key, url="https://api.typesafe.ai/v1/systemone", timeout=8.0):
    """Return a callable; importing or constructing it performs no network I/O."""
    def decide(payload):
        request = Request(url, data=json.dumps(payload, allow_nan=False).encode("utf-8"),
                          headers={"Authorization": "Bearer " + api_key,
                                   "Content-Type": "application/json"}, method="POST")
        with urlopen(request, timeout=timeout) as response:
            return json.load(response)

    return decide

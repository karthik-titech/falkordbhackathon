"""Run once to probe JEV's confirmed criteria-map choice shape."""

import json
import os
from pathlib import Path
import sys

# Support `python3 scripts/jev_probe.py` without installing this package.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from warmopen.jev import jev_client


def main():
    key = os.environ.get("TYPESAFE_JEV_API_KEY")
    if not key:
        print("No TYPESAFE_JEV_API_KEY in this environment; probe not run.")
        return 1
    payload = {
        "model": "jev-latest", "state": {"evidence_count": 3, "gaps_count": 0},
        "questions": {"fit": {
            "type": "choice",
            "instructions": "Choose high or low fit from the abstract counts.",
            "criteria": {
                "high": "Evidence count exceeds gaps count.",
                "low": "Evidence count does not exceed gaps count.",
            },
        }},
    }
    record = {"request": {"url": "https://api.typesafe.ai/v1/systemone",
                          "headers": {"Authorization": "Bearer [REDACTED]"}, "body": payload}}
    try:
        record["response"] = jev_client(key)(payload)
    except Exception as error:
        record["error"] = type(error).__name__

    def redact(value):
        if isinstance(value, str):
            return value.replace(key, "[REDACTED]")
        if isinstance(value, dict):
            return {redact(k): redact(v) for k, v in value.items()}
        if isinstance(value, list):
            return [redact(item) for item in value]
        return value

    destination = Path(__file__).resolve().parents[1] / "docs" / "jev-probe.json"
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(redact(record), indent=2) + "\n", encoding="utf-8")
    print("Probe attempted once; redacted result saved to docs/jev-probe.json.")
    return 0 if "response" in record else 1


if __name__ == "__main__":
    raise SystemExit(main())

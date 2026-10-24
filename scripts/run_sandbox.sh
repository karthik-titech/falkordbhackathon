#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
: "${FALKORDB_HOST:?Set FALKORDB_HOST to the sandbox FalkorDB host}"
python3 - <<'PY'
import json
import os
from pathlib import Path
from warmopen.graphstore import GraphStore
from warmopen.seed import load_seed

store = GraphStore.connect()
with store.lock:
    empty = store.query(store.event(), "MATCH (n) RETURN count(n)").result_set[0][0] == 0
if empty:
    path = Path(os.environ.get("WARMOPEN_SEED", "data/seed.json"))
    if not path.is_file():
        raise SystemExit("Missing curated seed: supply data/seed.json or set WARMOPEN_SEED to a seed file.")
    print(json.dumps(load_seed(store, json.loads(path.read_text(encoding="utf-8"))), sort_keys=True))
PY
exec python3 -m warmopen.cli serve --host 0.0.0.0 --port "${PORT:-8080}" "$@"

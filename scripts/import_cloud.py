"""Merge the local public event graph into cloud in bounded batches."""

from collections import defaultdict
import os
from pathlib import Path
import re
import shlex

from warmopen.graphstore import GraphStore


def main():
    for line in Path(os.environ.get("CONFERENCE_ENV_FILE", ".env")).read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and key.strip() == "FALKORDB_URL":
            os.environ["FALKORDB_URL"] = shlex.split(value)[0]
    source = GraphStore.connect(host=os.environ.get("FALKORDB_HOST", "graph"),
                                port=int(os.environ.get("FALKORDB_PORT", "6379")))
    if not os.environ.get("FALKORDB_URL", "").startswith("falkors://"):
        raise ValueError("A cloud TLS URL is required")
    destination = GraphStore.connect()
    nodes = source.query("event", "MATCH (n) RETURN id(n), labels(n), properties(n)").result_set
    edges = source.query("event", "MATCH (a)-[r]->(b) RETURN id(a), type(r), properties(r), id(b)").result_set
    identities = {}
    node_groups, edge_groups = defaultdict(list), defaultdict(list)
    for internal_id, labels, properties in nodes:
        assert len(labels) == 1 and isinstance(properties.get("id"), str)
        label = labels[0]
        assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", label)
        identities[internal_id] = (label, properties["id"])
        node_groups[label].append({"id": properties["id"], "properties": properties})
    for first, kind, properties, last in edges:
        assert re.fullmatch(r"[A-Z_]+", kind)
        start_label, start_id = identities[first]
        end_label, end_id = identities[last]
        edge_groups[start_label, kind, end_label].append(
            {"start": start_id, "end": end_id, "properties": properties})
    for label, records in node_groups.items():
        for offset in range(0, len(records), 200):
            destination.query("event", f"UNWIND $rows AS row MERGE (n:{label} {{id: row.id}}) SET n += row.properties",
                              {"rows": records[offset:offset + 200]})
        print("Imported", len(records), label, "nodes", flush=True)
    for (start, kind, end), records in edge_groups.items():
        for offset in range(0, len(records), 200):
            destination.query("event", f"UNWIND $rows AS row MATCH (a:{start} {{id: row.start}}), "
                              f"(b:{end} {{id: row.end}}) MERGE (a)-[r:{kind}]->(b) SET r += row.properties",
                              {"rows": records[offset:offset + 200]})
        print("Imported", len(records), kind, "relationships", flush=True)
    for store in (source, destination):
        print("Graph counts:", store.query("event", "MATCH (n) RETURN count(n)").result_set,
              store.query("event", "MATCH ()-[r]->() RETURN count(r)").result_set, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"Cloud import failed: {type(exc).__name__}") from None

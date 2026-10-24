"""FalkorDB handles and deterministic graph inspection."""

import json
import os
import re
import threading


class GraphStore:
    """Keep shared and owner graphs under one nonempty namespace."""

    def __init__(self, client, prefix):
        if not isinstance(prefix, str) or not prefix:
            raise ValueError("A nonempty graph prefix is required")
        self.client = client
        self.prefix = prefix
        self.lock = threading.Lock()

    @classmethod
    def connect(cls, host=None, port=None, prefix="wo_"):
        from falkordb import FalkorDB

        return cls(FalkorDB(
            host=host if host is not None else os.environ.get("FALKORDB_HOST", "localhost"),
            port=int(port if port is not None else os.environ.get("FALKORDB_PORT", "6379")),
        ), prefix)

    def event(self):
        return self.client.select_graph(self.prefix + "event")

    def private(self, owner_id):
        if not isinstance(owner_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", owner_id):
            raise ValueError("Invalid private graph owner id")
        return self.client.select_graph(self.prefix + "p_" + owner_id)

    def query(self, graph_name_or_handle, cypher, params=None):
        graph = graph_name_or_handle
        if isinstance(graph, str):
            graph = self.event() if graph == "event" else self.client.select_graph(graph)
        if not graph.name.startswith(self.prefix):
            raise ValueError("Graph is outside this store's namespace")
        return graph.query(cypher, params=params or {})

    def dump(self, graph="event"):
        nodes = self.query(graph, "MATCH (n) RETURN labels(n), properties(n)").result_set
        edges = self.query(
            graph,
            "MATCH (a)-[r]->(b) RETURN type(r), properties(r), id(a), id(b)",
        ).result_set
        rows = [{"label": labels[0] if labels else None, "properties": props}
                for labels, props in nodes]
        rows.extend({"type": kind, "properties": props, "from": source, "to": target}
                    for kind, props, source, target in edges)
        return sorted(rows, key=lambda row: json.dumps(row, sort_keys=True))

    def drop_all(self):
        with self.lock:
            for name in self.client.list_graphs():
                if name.startswith(self.prefix):
                    self.client.select_graph(name).delete()

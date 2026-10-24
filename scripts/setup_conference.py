"""Create and verify a small synthetic conference graph using a private .env."""

import os
from pathlib import Path
import shlex
import sys

from falkordb import FalkorDB


PATH_QUERY = """
MATCH p=(a:Attendee {id: 'ptc_demo_attendee'})-[:INTERESTED_IN]->(:Topic)
        <-[:ABOUT]-(:Talk)<-[:PRESENTS]-(s:Speaker)
RETURN p
"""


def main():
    env_file = Path(os.environ.get("CONFERENCE_ENV_FILE", ".env"))
    for line in env_file.read_text().splitlines():
        key, separator, value = line.removeprefix("export ").partition("=")
        if separator and key.strip() == "FALKORDB_URL":
            parts = shlex.split(value, comments=True)
            if len(parts) == 1:
                os.environ["FALKORDB_URL"] = parts[0]
    url = os.environ.get("FALKORDB_URL", "")
    if not url.startswith("falkors://"):
        raise ValueError("A full falkors:// TLS URL is required")
    db = FalkorDB.from_url(url, socket_connect_timeout=15, socket_timeout=30)
    graph = db.select_graph("conference")
    assert graph.query("RETURN 1").result_set == [[1]]
    print("PASS Connection: TLS connection; RETURN 1 succeeded")
    graph.query("""
        MERGE (a:Attendee {id: 'ptc_demo_attendee'}) SET a.name = 'Alex (demo)', a.synthetic = true
        MERGE (b:Attendee {id: 'ptc_demo_peer'}) SET b.name = 'Sam (demo)', b.synthetic = true
        MERGE (s:Speaker {id: 'ptc_demo_speaker'}) SET s.name = 'Morgan (demo)', s.synthetic = true
        MERGE (t:Talk {id: 'ptc_demo_talk'}) SET t.title = 'Building AI agents with graphs', t.synthetic = true
        MERGE (topic:Topic {id: 'ptc_demo_topic'}) SET topic.name = 'AI agents', topic.synthetic = true
        MERGE (r:Room {id: 'ptc_demo_room'}) SET r.name = 'Demo room', r.synthetic = true
        MERGE (s)-[:PRESENTS]->(t)
        MERGE (t)-[:ABOUT]->(topic)
        MERGE (t)-[:IN_ROOM]->(r)
        MERGE (a)-[:INTERESTED_IN]->(topic)
        MERGE (a)-[:MET]->(b)
    """)
    node_counts = graph.query("MATCH (n) RETURN labels(n), count(n)").result_set
    edge_counts = graph.query("MATCH ()-[e]->() RETURN type(e), count(e)").result_set
    assert all(any(label in row[0] and row[1] > 0 for row in node_counts)
               for label in ("Talk", "Speaker", "Topic", "Room", "Attendee"))
    assert all(any(row[0] == kind and row[1] > 0 for row in edge_counts)
               for kind in ("PRESENTS", "ABOUT", "IN_ROOM", "INTERESTED_IN", "MET"))
    print("PASS Data:", sum(row[1] for row in node_counts), "nodes;",
          sum(row[1] for row in edge_counts), "edges")
    print("Nodes by label:", node_counts)
    print("Edges by type:", edge_counts)
    paths = graph.query(PATH_QUERY).result_set
    assert paths and paths[0][0].edge_count() >= 3
    print("PASS Path query:", len(paths), "path(s)")
    for (path,) in paths:
        nodes, edges = path.nodes(), path.edges()
        rendered = nodes[0].properties.get("name", "Attendee")
        for index, edge in enumerate(edges):
            target = nodes[index + 1]
            name = target.properties.get("name", target.properties.get("title", "Node"))
            link = f"-[:{edge.relation}]->" if edge.src_node == nodes[index].id else f"<-[:{edge.relation}]-"
            rendered += f" {link} {name}"
        print(rendered)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Provider exceptions can include connection credentials; print type only.
        print(f"FAIL Setup: {type(exc).__name__}", file=sys.stderr)
        sys.exit(1)

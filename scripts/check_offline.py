"""Socket-free checks for the HTTP boundary; run with python3 -S -m scripts.check_offline."""

import hashlib
import io
import json
import secrets
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock, patch

from warmopen.app import _live, _presentation, _request_view, make_server


class MemoryConnection:
    def __init__(self, request):
        self.input = io.BytesIO(request)
        self.output = io.BytesIO()

    def makefile(self, *args):
        return self.input

    def sendall(self, data):
        self.output.write(data)


class MemoryServer:
    def __init__(self, address, handler):
        self.server_address = address
        self.handler = handler


class OfflineChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="warmopen-check-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.factory = patch("warmopen.app.ThreadingHTTPServer", MemoryServer)
        self.factory.start()
        self.addCleanup(self.factory.stop)

    def server(self, **kwargs):
        return make_server(None, mode="recorded", recordings_dir=self.directory, **kwargs)

    def save(self, number, method, path, body=None, status=200, response=None):
        (self.directory / f"{number:04d}.json").write_text(json.dumps({
            "method": method, "path": path, "request_body": body, "status": status,
            "body": {"mode": "live", **(response or {})}}), encoding="utf-8")

    def call(self, server, method, path, body=None, raw=None, headers=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else b"")
        lines = [f"{method} {path} HTTP/1.0", "Host: memory", f"Content-Length: {len(data)}"]
        lines += [f"{key}: {value}" for key, value in (headers or {}).items()]
        connection = MemoryConnection(("\r\n".join(lines) + "\r\n\r\n").encode() + data)
        server.handler(connection, ("memory", 0), server)
        head, payload = connection.output.getvalue().split(b"\r\n\r\n", 1)
        return int(head.split()[1]), json.loads(payload) if path.startswith("/api/") else payload.decode()

    def test_static_and_traversal(self):
        server = self.server()
        status, html = self.call(server, "GET", "/")
        self.assertEqual(status, 200)
        for element in ("path-view", "agent-timeline", "mode-banner"):
            self.assertIn(f'id="{element}"', html)
        self.assertIn("Approve reveal", self.call(server, "GET", "/owner")[1])
        for path in ("/static/../app.py", "/static/%2e%2e/app.py", "/static/%2fetc/passwd", "/static/"):
            self.assertEqual(self.call(server, "GET", path)[0], 404)
        for path in ("app.js", "owner.js", "style.css"):
            self.assertEqual(self.call(server, "GET", "/static/" + path)[0], 200)

    def test_replay_body_match_and_finite_response(self):
        self.save(1, "POST", "/api/grants", {"scope": "reveal", "owner": "owner"},
                  response={"grant_id": "saved"})
        server = self.server()
        self.assertEqual(self.call(server, "POST", "/api/grants", {"scope": "reachability", "owner": "owner"})[0], 404)
        status, body = self.call(server, "POST", "/api/grants", {"owner": "owner", "scope": "reveal"})
        self.assertEqual((status, body), (200, {"mode": "recorded", "grant_id": "saved"}))
        self.assertEqual(self.call(server, "POST", "/api/grants", {"owner": "owner", "scope": "reveal"})[0], 404)

    def test_polling_is_sticky_but_targets_are_finite(self):
        for number in (1, 2):
            self.save(number, "GET", "/api/requests/saved", response={"events": [number]})
        self.save(3, "GET", "/api/targets", response={"items": [{"id": "speaker"}]})
        server = self.server()
        for expected in ([1], [2], [2]):
            self.assertEqual(self.call(server, "GET", "/api/requests/saved")[1]["events"], expected)
        self.assertEqual(self.call(server, "GET", "/api/requests/saved", {})[0], 404)
        self.assertEqual(self.call(server, "GET", "/api/targets")[1],
                         {"items": [{"id": "speaker"}], "mode": "recorded"})
        self.assertEqual(self.call(server, "GET", "/api/targets")[0], 404)

    def test_absent_body_differs_from_empty_object(self):
        self.save(1, "POST", "/api/requests/saved/send", response={"state": "requested"})
        server = self.server()
        self.assertEqual(self.call(server, "POST", "/api/requests/saved/send", {})[0], 404)
        self.assertEqual(self.call(server, "POST", "/api/requests/saved/send")[0], 200)
        self.assertEqual(self.call(server, "POST", "/api/requests/saved/send")[0], 404)

    def test_error_mapping_and_recording(self):
        from warmopen.errors import NotFound
        from warmopen.requests import StateError

        server = make_server(object(), record_dir=self.directory)
        for error, expected in [(StateError("stale"), 409), (PermissionError("denied"), 403),
                                (NotFound("missing"), 404), (ValueError("invalid"), 400),
                                (RuntimeError("internal detail"), 500)]:
            with patch("warmopen.app._live", side_effect=error):
                status, body = self.call(server, "POST", "/api/test")
            self.assertEqual(status, expected)
            self.assertEqual(body["mode"], "live")
            self.assertNotIn("internal detail", json.dumps(body))
        self.assertEqual(len(list(self.directory.glob("*.json"))), 5)

    def test_record_counter_under_concurrent_calls_and_restart(self):
        self.save(7, "GET", "/api/old")
        server = make_server(object(), record_dir=self.directory)
        with patch("warmopen.app._live", side_effect=lambda store, method, path, body, *args: {"echo": body}):
            with ThreadPoolExecutor(max_workers=8) as pool:
                responses = list(pool.map(lambda n: self.call(server, "POST", "/api/test", {"n": n}), range(24)))
        self.assertTrue(all(status == 200 for status, _ in responses))
        files = sorted(self.directory.glob("*.json"))
        self.assertEqual([p.name for p in files], ["0007.json"] + [f"{n:04d}.json" for n in range(8, 32)])
        for path in files[1:]:
            record = json.loads(path.read_text())
            self.assertEqual(record["request_body"], record["body"]["echo"])

    def test_malformed_json_is_recorded_as_error(self):
        server = make_server(object(), record_dir=self.directory)
        for body in (b"{", b'{"n": NaN}', b'{"n": 1e999}', b"\xff"):
            status, response = self.call(server, "POST", "/api/test", raw=body)
            self.assertEqual(status, 400)
            self.assertEqual(response["mode"], "live")
        self.assertEqual(len(list(self.directory.glob("*.json"))), 4)

    def test_missing_or_wrong_owner_token_creates_no_grant(self):
        store = Mock(lock=threading.Lock())
        digest = hashlib.sha256(secrets.token_bytes(32)).hexdigest()

        def query(graph, cypher, params=None):
            if "RETURN properties(p)" in cypher:
                return Mock(result_set=[[{"consented": True}]])
            if "RETURN c.token_sha256" in cypher:
                return Mock(result_set=[[digest]])
            self.fail("Denied grant attempted another graph query: " + cypher)

        store.query.side_effect = query
        server = make_server(store)
        grant = {"owner": "owner", "requester": "requester", "request_id": "request", "scope": "reveal"}
        for headers in ({}, {"X-Owner-Token": "wrong"}):
            self.assertEqual(self.call(server, "POST", "/api/grants", grant, headers=headers)[0], 403)

    def test_presentation_removes_private_evidence_and_snapshot(self):
        store = Mock()
        route = {"route_id": "revealed_1", "persons": ["owner", "hidden"],
                 "edges": [{"from": "owner", "to": "hidden", "evidence_id": "private-evidence"}]}
        store.query.side_effect = [Mock(result_set=[["owner", "Owner"], ["hidden", "Revealed Name"]]),
                                   Mock(result_set=[])]
        payload = _presentation(store, route, [route])
        self.assertNotIn("private-evidence", json.dumps(payload))
        self.assertEqual(route["edges"][0]["evidence_id"], "private-evidence")
        self.assertEqual(payload["people"]["hidden"], "Revealed Name")
        with patch("warmopen.requests.get_request", return_value={"id": "r", "requester": "a", "target": "b", "state": "draft", "revealed_route": "private snapshot"}), \
             patch("warmopen.paths.public_paths", return_value=[]), \
             patch("warmopen.broker.revealed_route", return_value=None), \
             patch("warmopen.agentlog.events", return_value=[]):
            self.assertNotIn("private snapshot", json.dumps(_request_view(store, "r")))

    def test_direct_send_then_repeat_conflicts(self):
        from warmopen.requests import StateError

        state = {"id": "request", "state": "draft"}
        store = Mock(lock=threading.Lock())

        def query(graph, cypher, params=None):
            if "SET r.state" in cypher:
                state["state"] = params["state"]
            return Mock(result_set=[[state.copy()]])

        store.query.side_effect = query
        self.assertEqual(_live(store, "POST", "/api/requests/request/send", None, None, None, None), {"state": "requested"})
        with self.assertRaises(StateError):
            _live(store, "POST", "/api/requests/request/send", None, None, None, None)

    def test_cli_replay_imports_no_live_stack(self):
        code = """
import sys
from unittest.mock import Mock, patch
from warmopen.cli import main
server = Mock(server_address=('127.0.0.1', 8080))
server.serve_forever.side_effect = KeyboardInterrupt
with patch('warmopen.app.ThreadingHTTPServer', return_value=server):
    main(['serve', '--replay', sys.argv[1]])
assert not any(name in sys.modules for name in ('falkordb', 'warmopen.graphstore', 'warmopen.jev', 'warmopen.llm'))
assert server.server_close.called
"""
        result = subprocess.run([sys.executable, "-S", "-c", code, str(self.directory)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Recorded run", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)

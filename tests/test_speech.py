"""Voice isolates free text from decisions, recordings, and provider errors."""
import json
import threading
from urllib.request import Request, urlopen
from urllib.error import HTTPError

import pytest
from warmopen.speech import speech_client
from warmopen.app import make_server


def test_speech_adapter_bounds_text_and_uses_fixed_endpoint():
    calls = []
    class Response:
        headers = {"Content-Type": "audio/mpeg"}
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self, limit): return b"ID3audio"
    def transport(request, timeout):
        calls.append(request)
        assert timeout == 30
        return Response()
    client = speech_client("test-credential", transport)
    assert client("Hello conference") == b"ID3audio"
    payload = json.loads(calls[0].data)
    assert payload["input"] == "Hello conference"
    assert payload["response_format"] == "mp3"
    assert calls[0].full_url == "https://api.openai.com/v1/audio/speech"
    with pytest.raises(ValueError): client("x" * 801)
    assert len(calls) == 1


def test_speech_provider_details_are_never_exposed():
    def broken(*_, **__): raise RuntimeError("private provider payload")
    with pytest.raises(RuntimeError, match="Voice is unavailable") as exc:
        speech_client("test-credential", broken)("Hello")
    assert "private provider payload" not in str(exc.value)


def test_voice_http_is_not_recorded_and_rejects_bad_requests(loaded, tmp_path):
    calls = []
    server = make_server(loaded, record_dir=tmp_path, speech=lambda text: calls.append(text) or b"ID3audio")
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{server.server_address[1]}/api/speech"
    def request(body, **headers):
        return urlopen(Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", **headers}), timeout=3)
    try:
        with request({"text": "Hello attendee"}) as response:
            assert response.headers["Content-Type"] == "audio/mpeg"
            assert response.headers["Cache-Control"] == "no-store"
            assert response.read() == b"ID3audio"
        with pytest.raises(HTTPError) as exc: request({"text": "x" * 801})
        assert exc.value.code == 400
        with pytest.raises(HTTPError) as exc: request({"text": "Hello"}, Origin="https://unrelated.example")
        assert exc.value.code == 403
        assert calls == ["Hello attendee"]
        assert list(tmp_path.glob("*.json")) == []
    finally:
        server.shutdown(); server.server_close(); thread.join()

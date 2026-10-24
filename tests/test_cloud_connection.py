"""Cloud URL selection must preserve TLS and isolated local test overrides."""

from unittest.mock import patch

import pytest

from warmopen.graphstore import GraphStore


def test_cloud_connection_uses_full_tls_url(monkeypatch):
    url = "falkors://example.invalid:54599"
    monkeypatch.setenv("FALKORDB_URL", url)
    with patch("falkordb.FalkorDB") as client:
        store = GraphStore.connect()
        client.from_url.assert_called_once_with(
            url, socket_connect_timeout=15, socket_timeout=60)
        assert store.client is client.from_url.return_value
        assert store.event().name is not None


def test_explicit_local_test_connection_does_not_use_cloud(monkeypatch):
    monkeypatch.setenv("FALKORDB_URL", "falkors://example.invalid:54599")
    with patch("falkordb.FalkorDB") as client:
        GraphStore.connect(host="graph", port=6379, prefix="isolated_")
        client.from_url.assert_not_called()
        client.assert_called_once_with(host="graph", port=6379)


def test_cloud_connection_rejects_non_tls_url_without_exposing_value(monkeypatch):
    monkeypatch.setenv("FALKORDB_URL", "redis://example.invalid:6379")
    with pytest.raises(ValueError, match="full falkors:// TLS URL"):
        GraphStore.connect()

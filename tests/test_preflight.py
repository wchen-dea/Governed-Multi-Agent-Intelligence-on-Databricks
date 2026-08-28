"""Tests for local runtime preflight contract checks."""

from operations import preflight


def test_check_health_accepts_server_ok_status(monkeypatch):
    class Response:
        def read(self):
            return b'{"status": "ok"}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(preflight.urllib.request, "urlopen", lambda *args, **kwargs: Response())

    assert preflight.check_health("http://localhost:8000") is True
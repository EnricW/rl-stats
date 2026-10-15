"""Tests del cliente de ballchasing: reintentos sin romper la subida."""

import pytest

from pipeline import ballchasing
from pipeline.ballchasing import BallchasingClient, BallchasingError


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}
        self.text = ""

    def json(self):
        return self._payload


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(ballchasing.time, "sleep", lambda s: None)
    return BallchasingClient("token", min_interval=0)


def test_upload_reintento_reenvia_el_archivo_entero(client, tmp_path, monkeypatch):
    """Tras un 429, el reintento debe subir el archivo completo, no vacío
    (el bug original: el file object ya estaba leído hasta el final)."""
    replay = tmp_path / "x.replay"
    replay.write_bytes(b"contenido del replay")

    bodies = []
    responses = [FakeResponse(429, headers={"Retry-After": "0"}), FakeResponse(201, {"id": "abc"})]

    def fake_request(method, url, timeout=None, **kwargs):
        bodies.append(kwargs["files"]["file"].read())
        return responses.pop(0)

    monkeypatch.setattr(client.session, "request", fake_request)
    replay_id, existed = client.upload(replay)
    assert (replay_id, existed) == ("abc", False)
    assert bodies == [b"contenido del replay", b"contenido del replay"]


def test_retry_after_en_formato_fecha_no_revienta(client, monkeypatch):
    responses = [
        FakeResponse(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}),
        FakeResponse(200, {"ok": True}),
    ]
    monkeypatch.setattr(client.session, "request", lambda *a, **k: responses.pop(0))
    assert client._request("GET", "http://x").json() == {"ok": True}


def test_reintenta_ante_5xx(client, monkeypatch):
    responses = [FakeResponse(503), FakeResponse(200, {"ok": True})]
    monkeypatch.setattr(client.session, "request", lambda *a, **k: responses.pop(0))
    assert client._request("GET", "http://x").json() == {"ok": True}


def test_rate_limit_persistente_lanza_error(monkeypatch):
    monkeypatch.setattr(ballchasing.time, "sleep", lambda s: None)
    client = BallchasingClient("token", min_interval=0, max_retries=2)
    monkeypatch.setattr(client.session, "request", lambda *a, **k: FakeResponse(429))
    with pytest.raises(BallchasingError):
        client._request("GET", "http://x")


def test_upload_duplicado(client, tmp_path, monkeypatch):
    replay = tmp_path / "x.replay"
    replay.write_bytes(b"x")
    monkeypatch.setattr(client.session, "request", lambda *a, **k: FakeResponse(409, {"id": "dup"}))
    assert client.upload(replay) == ("dup", True)

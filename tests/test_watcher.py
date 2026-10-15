"""Tests del watcher: protección del estado (un uploaded.json corrupto no
puede significar "sube la carpeta Demos entera") y clasificación de errores
de subida (permanentes vs transitorios)."""

import importlib.util
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "watcher", Path(__file__).resolve().parent.parent / "watcher" / "watcher.py"
)
watcher = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(watcher)


@pytest.fixture
def state_file(tmp_path, monkeypatch):
    path = tmp_path / "uploaded.json"
    monkeypatch.setattr(watcher, "STATE_FILE", path)
    return path


def test_load_state_sin_archivo_es_primer_arranque(state_file):
    assert watcher.load_state() == (set(), True)


def test_save_y_load_state(state_file):
    watcher.save_state({"b.replay", "a.replay"})
    assert watcher.load_state() == ({"a.replay", "b.replay"}, False)
    # atómico: no queda ningún temporal al lado
    assert [p.name for p in state_file.parent.iterdir()] == ["uploaded.json"]


def test_state_corrupto_reaplica_la_proteccion(state_file):
    state_file.write_text("{corrupto", encoding="utf-8")
    state, first_run = watcher.load_state()
    # un estado ilegible NUNCA es "no hay nada subido": vuelve el modo
    # primer arranque (que marca lo existente como visto, sin subirlo)
    assert state == set()
    assert first_run is True
    # el archivo roto queda apartado como .bak para inspección
    assert not state_file.exists()
    assert (state_file.parent / "uploaded.json.bak").exists()


class _Resp:
    def __init__(self, status, headers=None):
        self.status_code = status
        self.headers = headers or {}
        self.text = "cuerpo"

    def json(self):
        return {"id": "r1"}


def _patch_post(monkeypatch, resp):
    monkeypatch.setattr(watcher.requests, "post", lambda *a, **k: resp)


@pytest.mark.parametrize("status,expected", [
    (201, "ok"),       # subido
    (409, "ok"),       # duplicado: ballchasing ya lo tenía
    (400, "fail"),     # replay corrupto: reintentarlo cada 30 s es inútil
    (429, "retry"),    # rate limit: transitorio
    (503, "retry"),    # caída del servicio: transitorio
    (401, "retry"),    # token caducado: no es culpa del replay
])
def test_upload_clasifica_errores(tmp_path, monkeypatch, status, expected):
    replay = tmp_path / "x.replay"
    replay.write_bytes(b"datos")
    _patch_post(monkeypatch, _Resp(status))
    monkeypatch.setattr(watcher.time, "sleep", lambda s: None)  # sin esperas reales
    assert watcher.upload(replay) == expected

"""Tests de las utilidades compartidas (funciones puras y escritura de JSON)."""

import json

import pytest

from pipeline.util import (
    mode_from_playlist,
    read_env_file,
    write_json,
    write_json_if_changed,
    write_text_atomic,
)


def test_mode_from_playlist():
    assert mode_from_playlist("ranked-standard") == "3v3"
    assert mode_from_playlist("unranked-doubles") == "2v2"
    assert mode_from_playlist("algo-raro") == "algo-raro"
    assert mode_from_playlist(None) == "desconocido"


def test_read_env_file(tmp_path):
    env = tmp_path / ".env"
    env.write_text(
        "# comentario\n"
        "TOKEN=abc123\n"
        "CON_COMILLAS='entre comillas'\n"
        "  ESPACIOS =  con espacios  \n"
        "linea sin igual\n",
        encoding="utf-8",
    )
    values = read_env_file(env)
    assert values == {
        "TOKEN": "abc123",
        "CON_COMILLAS": "entre comillas",
        "ESPACIOS": "con espacios",
    }
    assert read_env_file(tmp_path / "no-existe") == {}


def test_write_json_estable_y_legible(tmp_path):
    out = tmp_path / "sub" / "x.json"
    write_json(out, {"b": 1, "a": [1.5, None]})
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n")
    assert json.loads(text) == {"a": [1.5, None], "b": 1}
    assert text.index('"a"') < text.index('"b"')  # sort_keys: diffs estables


def test_write_json_compact(tmp_path):
    out = tmp_path / "x.json"
    write_json(out, {"a": [1, 2, 3]}, compact=True)
    assert out.read_text(encoding="utf-8") == '{"a":[1,2,3]}\n'


def test_write_json_rechaza_nan(tmp_path):
    out = tmp_path / "x.json"
    with pytest.raises(ValueError):
        write_json(out, {"v": float("nan")})
    # la escritura es atómica: el archivo destino no queda a medias
    assert not out.exists()
    # y el .tmp no queda huérfano (acabaría commiteado por "git add data")
    assert list(tmp_path.iterdir()) == []


def test_write_text_atomic(tmp_path):
    out = tmp_path / "sub" / "informe.md"
    write_text_atomic(out, "# Informe\n")
    assert out.read_text(encoding="utf-8") == "# Informe\n"
    assert list(out.parent.glob("*.tmp")) == []


def test_write_json_if_changed_ignora_volatiles(tmp_path):
    out = tmp_path / "x.json"
    assert write_json_if_changed(out, {"generated_at": "t1", "a": 1}) is True
    before = out.read_text(encoding="utf-8")
    # solo cambia la marca de tiempo: no se reescribe (sin commits de ruido)
    assert write_json_if_changed(out, {"generated_at": "t2", "a": 1}) is False
    assert out.read_text(encoding="utf-8") == before
    # cambia el contenido real: sí se reescribe
    assert write_json_if_changed(out, {"generated_at": "t3", "a": 2}) is True
    assert json.loads(out.read_text(encoding="utf-8"))["a"] == 2

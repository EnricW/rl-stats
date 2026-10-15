"""Tests de las utilidades compartidas (funciones puras y escritura de JSON)."""

import json

import pytest

from pipeline.util import mode_from_playlist, read_env_file, write_json


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

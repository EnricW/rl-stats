"""Tests de report.main: qué informes genera y qué estado deja en el
manifiesto (es el módulo que cuesta dinero: cada llamada de más se paga)."""

import sys
from datetime import UTC, datetime, timedelta

import pytest

import pipeline.manifest as mf
import pipeline.report as report
from pipeline.util import read_json, write_json

SETTINGS = {
    "timezone": "Europe/Madrid",
    "reports": {
        "match_model": "haiku-test",
        "trend_model": "sonnet-test",
        "trend_effort": "high",
        "session_gap_hours": 5,
        "session_min_games": 1,
        "max_player_reports_per_run": 6,
        "team_report_every_days": 7,
        "prompt_history_games": 20,
        "max_tokens": 100,
    },
}


def _ago(hours):
    return (datetime.now(UTC) - timedelta(hours=hours)).isoformat(timespec="seconds")


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """data/ de mentira + ask_claude de mentira: main() corre entero en local."""
    dirs = {}
    for name in ("matches", "players", "reports", "events", "frames"):
        d = tmp_path / name
        d.mkdir()
        dirs[name] = d
    monkeypatch.setattr(report, "DATA_DIR", tmp_path)
    monkeypatch.setattr(report, "MATCHES_DIR", dirs["matches"])
    monkeypatch.setattr(report, "PLAYERS_DIR", dirs["players"])
    monkeypatch.setattr(report, "REPORTS_DIR", dirs["reports"])
    monkeypatch.setattr(report, "EVENTS_DIR", dirs["events"])
    monkeypatch.setattr(mf, "MANIFEST_FILE", tmp_path / "manifest.json")
    monkeypatch.setattr(mf, "MATCHES_DIR", dirs["matches"])
    monkeypatch.setattr(mf, "REPORTS_DIR", dirs["reports"])
    monkeypatch.setattr(mf, "EVENTS_DIR", dirs["events"])
    monkeypatch.setattr(mf, "FRAMES_DIR", dirs["frames"])
    monkeypatch.setattr(report, "load_settings", lambda: SETTINGS)
    monkeypatch.setattr(sys, "argv", ["report"])

    calls, payloads, efforts = [], [], []

    def fake_ask(model, system_prompt, payload_text, reports_cfg, effort=None):
        calls.append(model)
        payloads.append(payload_text)
        efforts.append(effort)
        return "# informe de prueba"

    monkeypatch.setattr(report, "ask_claude", fake_ask)

    state = {"n": 0}

    def add_match(date, player="Enric"):
        """Añade una partida y la refleja en el histórico del jugador."""
        state["n"] += 1
        mid = f"{state['n']:08d}-cccc-dddd-eeee-ffff00001111"
        write_json(dirs["matches"] / f"{mid}.json", {
            "id": mid, "date": date, "mode": "3v3", "duration": 300,
            "players": [{"name": player, "roster": True}],
            "teams": {"blue": {"goals": 1, "stats": {}}, "orange": {"goals": 0, "stats": {}}},
        })
        path = dirs["players"] / f"{player}.json"
        data = read_json(path) if path.exists() else {
            "name": player,
            "modes": {"3v3": {"games": 0, "winrate": 1.0, "averages": {},
                              "last10_averages": {}}},
            "history": [],
        }
        data["history"].append({"match_id": mid, "date": date, "mode": "3v3",
                                "result": "win", "goals": 1})
        data["modes"]["3v3"]["games"] = len(data["history"])
        write_json(path, data)
        return mid

    return {"dirs": dirs, "calls": calls, "payloads": payloads,
            "efforts": efforts, "add_match": add_match}


def test_main_genera_y_registra(sandbox):
    """Una sesión cerrada: informe de partida + informe de tendencia + equipo."""
    sandbox["add_match"](_ago(30))
    report.main()

    assert sandbox["calls"] == ["haiku-test", "sonnet-test", "sonnet-test"]
    # trend_effort solo aplica a las tendencias, no al informe de partida
    assert sandbox["efforts"] == [None, "high", "high"]

    manifest = read_json(mf.MANIFEST_FILE)
    item = manifest["reports"]["players"]["Enric"][0]
    assert item["games"] == 1
    assert item["session_id"] and item["session_id"].startswith(item["date"])
    assert (sandbox["dirs"]["reports"] / f"player-Enric-{item['session_id']}.md").exists()
    assert item["path"] == f"reports/player-Enric-{item['session_id']}.md"
    # el contador por partidas desapareció con el esquema v2
    assert "player_reports_state" not in manifest


def test_no_informa_la_sesion_en_curso(sandbox):
    """El test que protege el dinero: mientras la sesión está abierta, los
    avisos del watcher (uno por partida) no generan informes de tendencia."""
    sandbox["add_match"](_ago(0.2))   # hace 12 minutos: la noche sigue
    report.main()
    # se genera el informe de la partida y el de equipo (nunca hubo), pero
    # NINGUNA tendencia: su payload es el único que lleva la clave "sesion"
    assert [p for p in sandbox["payloads"] if '"sesion"' in p] == []
    assert sandbox["calls"] == ["haiku-test", "sonnet-test"]
    assert read_json(mf.MANIFEST_FILE)["reports"]["players"] == {}


def test_una_tendencia_por_sesion_cerrada(sandbox):
    sandbox["add_match"](_ago(50))    # sesión A (anteayer)
    report.main()
    n = len(sandbox["calls"])

    sandbox["add_match"](_ago(26))    # sesión B (ayer)
    report.main()
    nuevos = sandbox["calls"][n:]
    # una partida nueva + una tendencia nueva; el equipo no (es de hoy)
    assert nuevos == ["haiku-test", "sonnet-test"]
    items = read_json(mf.MANIFEST_FILE)["reports"]["players"]["Enric"]
    assert len(items) == 2
    assert items[0]["session_id"] < items[1]["session_id"]  # orden cronológico


def test_es_idempotente(sandbox):
    sandbox["add_match"](_ago(30))
    report.main()
    n = len(sandbox["calls"])
    report.main()
    assert len(sandbox["calls"]) == n


def test_payload_lleva_la_sesion_y_el_informe_anterior(sandbox):
    sandbox["add_match"](_ago(50))
    report.main()
    primero = [p for p in sandbox["payloads"] if '"sesion"' in p][0]
    assert '"partidas": 1' in primero
    assert "informe_anterior" not in primero   # es el primero de la serie

    sandbox["add_match"](_ago(26))
    report.main()
    segundo = [p for p in sandbox["payloads"] if '"sesion"' in p][-1]
    assert "informe_anterior" in segundo       # continuidad con el anterior
    assert "# informe de prueba" in segundo


def test_la_sesion_no_ve_partidas_posteriores(sandbox):
    """El informe de una sesión antigua no puede hablar del futuro."""
    viejo = sandbox["add_match"](_ago(50))
    nuevo = sandbox["add_match"](_ago(26))
    report.main()
    tendencias = [p for p in sandbox["payloads"] if '"sesion"' in p]
    primera = next(p for p in tendencias if viejo in p)
    assert nuevo not in primera


def test_respeta_el_minimo_de_partidas(sandbox, monkeypatch):
    monkeypatch.setitem(SETTINGS["reports"], "session_min_games", 3)
    try:
        sandbox["add_match"](_ago(30))
        sandbox["add_match"](_ago(30))
        report.main()
        assert [p for p in sandbox["payloads"] if '"sesion"' in p] == []
        sandbox["add_match"](_ago(30))   # tercera: ya merece informe
        report.main()
        assert len([p for p in sandbox["payloads"] if '"sesion"' in p]) == 1
    finally:
        SETTINGS["reports"]["session_min_games"] = 1


def test_tope_por_pasada(sandbox, monkeypatch):
    monkeypatch.setitem(SETTINGS["reports"], "max_player_reports_per_run", 1)
    try:
        sandbox["add_match"](_ago(80))
        sandbox["add_match"](_ago(50))
        sandbox["add_match"](_ago(26))
        report.main()
        assert len([p for p in sandbox["payloads"] if '"sesion"' in p]) == 1
    finally:
        SETTINGS["reports"]["max_player_reports_per_run"] = 6


def test_team_report_recibe_el_anterior(sandbox):
    sandbox["add_match"](_ago(30))
    report.main()
    manifest = read_json(mf.MANIFEST_FILE)
    manifest["reports"]["team"][-1]["date"] = (
        datetime.now(UTC).date() - timedelta(days=8)
    ).isoformat()
    write_json(mf.MANIFEST_FILE, manifest)

    report.main()
    assert "informe_anterior" in sandbox["payloads"][-1]

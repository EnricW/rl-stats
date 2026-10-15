"""Tests de report.main: qué informes genera y qué estado deja en el
manifiesto (es el módulo que cuesta dinero: cada llamada de más se paga)."""

import sys
from datetime import UTC, datetime, timedelta

import pytest

import pipeline.manifest as mf
import pipeline.report as report
from pipeline.util import read_json, write_json

MATCH_ID = "aaaabbbb-cccc-dddd-eeee-ffff00001111"

SETTINGS = {
    "reports": {
        "match_model": "haiku-test",
        "trend_model": "sonnet-test",
        "player_report_every": 2,
        "team_report_every_days": 7,
        "prompt_history_games": 20,
        "max_tokens": 100,
    }
}


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

    calls = []
    payloads = []

    def fake_ask(model, system_prompt, payload_text, reports_cfg):
        calls.append(model)
        payloads.append(payload_text)
        return "# informe de prueba"

    monkeypatch.setattr(report, "ask_claude", fake_ask)

    write_json(dirs["matches"] / f"{MATCH_ID}.json", {
        "id": MATCH_ID,
        "date": "2026-10-14T20:00:00+02:00",
        "mode": "3v3",
        "players": [{"name": "Enric", "roster": True}],
        "teams": {"blue": {"goals": 1, "stats": {}}, "orange": {"goals": 0, "stats": {}}},
    })
    write_json(dirs["players"] / "Enric.json", {
        "name": "Enric",
        "modes": {"3v3": {"games": 2, "winrate": 1.0,
                          "averages": {}, "last10_averages": {}}},
        "history": [{"mode": "3v3"}, {"mode": "3v3"}],
    })
    return {"dirs": dirs, "calls": calls, "payloads": payloads}


def test_main_genera_y_registra(sandbox):
    report.main()

    # partida (haiku) + tendencia de Enric (2 partidas, every=2) + equipo
    # (nunca hubo): tres llamadas, ni una más
    assert sandbox["calls"] == ["haiku-test", "sonnet-test", "sonnet-test"]

    reports_dir = sandbox["dirs"]["reports"]
    assert (reports_dir / f"{MATCH_ID}.md").exists()
    date = report._report_date()
    assert (reports_dir / f"player-Enric-{date}.md").exists()
    assert (reports_dir / f"team-{date}.md").exists()

    manifest = read_json(mf.MANIFEST_FILE)
    assert manifest["matches"][MATCH_ID]["report"]["model"] == "haiku-test"
    assert manifest["player_reports_state"] == {"Enric": 2}
    assert [i["date"] for i in manifest["reports"]["team"]] == [date]
    assert manifest["reports"]["players"]["Enric"][0]["path"] == f"reports/player-Enric-{date}.md"


def test_main_es_idempotente(sandbox):
    report.main()
    n = len(sandbox["calls"])
    # segunda pasada inmediata: informe de partida ya existe, Enric no ha
    # sumado partidas nuevas y el de equipo es de hoy -> cero llamadas (coste)
    report.main()
    assert len(sandbox["calls"]) == n


def test_team_report_recibe_el_anterior(sandbox):
    """El informe de equipo nuevo recibe el anterior para darle continuidad."""
    report.main()
    # el primero no tiene nada que repasar
    assert all("informe_anterior" not in p for p in sandbox["payloads"])

    # fuerza que vuelva a tocar: el último informe pasa a tener 8 días
    manifest = read_json(mf.MANIFEST_FILE)
    manifest["reports"]["team"][-1]["date"] = (
        datetime.now(UTC).date() - timedelta(days=8)
    ).isoformat()
    write_json(mf.MANIFEST_FILE, manifest)

    report.main()
    assert sandbox["calls"][-1] == "sonnet-test"  # solo se regeneró el de equipo
    assert "informe_anterior" in sandbox["payloads"][-1]
    assert "# informe de prueba" in sandbox["payloads"][-1]  # el markdown viaja


def test_main_umbral_de_jugador(sandbox):
    report.main()
    n = len(sandbox["calls"])
    # una partida más (3 en total): no llega al siguiente ciclo de 2 desde
    # el estado (2 + 2 = 4), así que no se regenera todavía
    data = read_json(sandbox["dirs"]["players"] / "Enric.json")
    data["history"].append({"mode": "3v3"})
    write_json(sandbox["dirs"]["players"] / "Enric.json", data)
    report.main()
    assert len(sandbox["calls"]) == n

    # con la cuarta partida toca informe nuevo
    data["history"].append({"mode": "3v3"})
    write_json(sandbox["dirs"]["players"] / "Enric.json", data)
    report.main()
    assert sandbox["calls"][n:] == ["sonnet-test"]
    manifest = read_json(mf.MANIFEST_FILE)
    assert manifest["player_reports_state"] == {"Enric": 4}

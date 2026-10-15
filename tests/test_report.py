"""Tests de las partes puras de report.py (sin tocar la API de Claude)."""

from datetime import datetime, timedelta, timezone

import pipeline.report as report
from pipeline.report import slim_match, slim_player


def test_slim_match_cura_los_equipos():
    match = {
        "id": "m1",
        "mode": "3v3",
        "players": [],
        "teams": {
            "blue": {
                "goals": 3,
                "stats": {
                    "core": {"shots": 10, "shots_against": 4, "saves": 2, "score": 999},
                    "ball": {"possession_time": 160.5, "time_in_side": 120.0},
                    "demo": {"inflicted": 1},
                },
            },
            "orange": {"goals": 1, "stats": {}},
        },
    }
    slim = slim_match(match)
    # el resto de la partida pasa tal cual; los equipos, curados
    assert slim["id"] == "m1" and slim["mode"] == "3v3"
    blue = slim["teams"]["blue"]
    assert blue == {
        "goals": 3,
        "shots": 10,
        "shots_against": 4,
        "saves": 2,
        "possession_time_s": 160.5,
        "time_ball_in_own_side_s": 120.0,
        "demos_inflicted": 1,
    }
    # nunca se cuelan los bloques de stats en bruto (coste en tokens)
    assert "stats" not in blue
    assert slim["teams"]["orange"]["goals"] == 1
    # el original no se muta
    assert "stats" in match["teams"]["blue"]


def test_slim_player_recorta_el_historico():
    data = {"name": "Enric", "modes": {"3v3": {}}, "history": list(range(50))}
    slim = slim_player(data, 20)
    assert slim["history"] == list(range(30, 50))  # las últimas 20
    assert slim["modes"] == {"3v3": {}}
    assert len(data["history"]) == 50  # el original no se muta


def test_team_report_due():
    """El informe de equipo se decide por la fecha del último, no por el cron."""
    today = datetime.now(timezone.utc).date()
    manifest = {"reports": {"team": []}}

    assert report._team_report_due(manifest, 7) is True  # nunca hubo informe

    manifest["reports"]["team"] = [
        {"date": (today - timedelta(days=2)).isoformat(), "path": "x", "model": None}
    ]
    assert report._team_report_due(manifest, 7) is False  # reciente: aún no toca

    manifest["reports"]["team"] = [
        {"date": (today - timedelta(days=7)).isoformat(), "path": "x", "model": None}
    ]
    assert report._team_report_due(manifest, 7) is True  # cumplió la semana

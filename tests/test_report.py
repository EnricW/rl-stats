"""Tests de las partes puras de report.py (sin tocar la API de Claude)."""

from datetime import datetime, timedelta, timezone

import pipeline.report as report
from pipeline.report import slim_match
from pipeline.util import write_json


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


def test_team_report_due(tmp_path, monkeypatch):
    """El informe de equipo se decide por la fecha del último, no por el cron."""
    index = tmp_path / "index.json"
    monkeypatch.setattr(report, "INDEX_FILE", index)
    today = datetime.now(timezone.utc).date()

    assert report._team_report_due(7) is True  # nunca hubo informe

    write_json(index, {"team": [(today - timedelta(days=2)).isoformat()]})
    assert report._team_report_due(7) is False  # reciente: aún no toca

    write_json(index, {"team": [(today - timedelta(days=7)).isoformat()]})
    assert report._team_report_due(7) is True  # cumplió la semana

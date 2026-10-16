"""Tests de las funciones puras de aggregate.py."""

from pipeline.aggregate import averages, extract_event_metrics, extract_metrics


def test_extract_metrics():
    stats = {
        "core": {"goals": 2, "score": 512, "shooting_percentage": 33.333},
        "boost": {"bpm": 350.7},
        "positioning": {"percent_behind_ball": 61.22},
    }
    out = extract_metrics(stats)
    assert out["goals"] == 2
    assert out["shooting_pct"] == 33.33  # redondeo a 2 decimales
    assert out["bpm"] == 350.7
    assert out["pct_behind_ball"] == 61.22
    assert "saves" not in out  # métrica ausente: no se inventa


def test_extract_metrics_ignora_no_numericos():
    assert extract_metrics({"core": {"goals": "dos"}}) == {}
    assert extract_metrics({}) == {}


def test_extract_event_metrics():
    events = {
        "kickoff_players": {"Enric": {"taken": 4, "first_touches": 3}},
        "rotation": {"Enric": {"pct_first_man": 35.1, "pct_third_man": 30.0}},
    }
    out = extract_event_metrics(events, "Enric")
    assert out["kickoff_ft_pct"] == 75.0
    assert out["pct_first_man"] == 35.1
    assert out["pct_third_man"] == 30.0
    assert extract_event_metrics(events, "Otro") == {}


def test_averages():
    rows = [
        {"goals": 1, "saves": 2},
        {"goals": 3},  # sin saves: la media de saves usa solo las filas que lo tienen
    ]
    out = averages(rows)
    assert out["goals"] == 2.0
    assert out["saves"] == 2.0
    assert averages([]) == {}


def test_sessions_view_y_reports_view():
    """La vista que consume la web: sesiones y sus informes."""
    from datetime import UTC, datetime, timedelta

    from pipeline.aggregate import reports_view, sessions_view

    anoche = (datetime.now(UTC) - timedelta(hours=30)).isoformat(timespec="seconds")
    ahora = (datetime.now(UTC) - timedelta(minutes=10)).isoformat(timespec="seconds")
    settings = {"timezone": "Europe/Madrid", "reports": {"session_gap_hours": 5}}
    sessions = sessions_view([
        {"id": "a", "date": anoche, "duration": 300},
        {"id": "b", "date": ahora, "duration": 300},
    ], settings)

    # la más reciente primero, y es la que sigue abierta
    assert len(sessions) == 2
    assert sessions[0]["open"] is True and sessions[1]["open"] is False

    manifest = {"reports": {
        "team": [{"date": "2026-10-15", "path": "reports/team-2026-10-15.md", "model": "o"}],
        "players": {"Enric": [
            {"session_id": sessions[1]["id"], "date": sessions[1]["date"], "games": 1,
             "path": "reports/player-Enric-x.md", "model": "o"},
            # informe de una sesión que ya no existe: no debe publicarse (si no,
            # la web ofrecería un enlace roto)
            {"session_id": "1999-01-01-0000", "date": "1999-01-01", "games": 3,
             "path": "reports/fantasma.md", "model": "o"},
        ]},
    }}
    view = reports_view(manifest, {s["id"] for s in sessions})
    assert [i["session_id"] for i in view["players"]["Enric"]["items"]] == [sessions[1]["id"]]
    assert view["players"]["Enric"]["items"][0]["games"] == 1
    assert len(view["team"]) == 1
    # la vista ya no publica el umbral de partidas ni el contador
    assert "every" not in view
    assert "games_at_last" not in view["players"]["Enric"]

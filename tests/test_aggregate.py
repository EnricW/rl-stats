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

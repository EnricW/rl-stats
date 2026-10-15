"""Tests de events.extract con una salida sintética de subtr-actor.

El caso cubre el riesgo principal: un rival cuyo nick visible coincide con el
nombre de alguien del roster no debe contaminar los contadores de saques
(el join es por id de plataforma, no por nombre).
"""

import pipeline.events as events

ROSTER = {("steam", "111"): "Enric", ("steam", "222"): "Ray"}


def _rid(pid):
    return {"Steam": pid}


FRAMES_DATA = {
    "frame_data": {
        "metadata_frames": [{"time": 10.0}, {"time": 10.5}, {"time": 11.0}],
    },
    "goal_events": [
        {"time": 11.0, "player": _rid("111"), "scoring_team_is_team_0": True,
         "team_zero_score": 1, "team_one_score": 0},
    ],
    "player_stat_events": [
        {"frame": 1, "kind": "Shot", "player": _rid("111"), "is_team_0": True,
         "shot": {"ball_speed_toward_goal": 120.4, "distance_to_goal_center": 300.2}},
        {"frame": 2, "kind": "Save", "player": _rid("999"), "is_team_0": False},
    ],
}

SUMMED = {
    "replay_meta": {
        "team_zero": [
            {"name": "Reiben", "remote_id": _rid("111")},
            {"name": "Scotaiel", "remote_id": _rid("222")},
        ],
        # rival con el MISMO nick visible que alguien del roster
        "team_one": [{"name": "Enric", "remote_id": _rid("999")}],
    },
    "modules": {
        "kickoff": {
            "events": [{
                "start_time": 10.0,
                "kickoff_type": "standard",
                "team_zero_taker": {"player": _rid("111")},
                "team_one_taker": {"player": _rid("999")},
                "first_touch_player": _rid("999"),
                "first_touch_team_is_team_0": False,
                "outcome": "team_one_win",
                "scoring_team_is_team_0": None,
            }],
            "player_stats": [
                {"player_id": _rid("111"), "stats": {
                    "count": 1, "fakes": 0,
                    "cumulative_boost_after": 66.0, "boost_after_sample_count": 1,
                }},
                {"player_id": _rid("999"), "stats": {"count": 1}},
            ],
        },
        "rotation": {"player_stats": [
            {"player_id": _rid("111"), "stats": {
                "active_game_time": 100.0, "time_first_man": 30.0,
                "time_second_man": 30.0, "time_third_man": 40.0,
                "became_first_man_count": 5,
            }},
        ]},
        "player_possession": {"events": [
            {"player_id": _rid("111"), "duration": 3.0, "is_team_0": True},
            {"player_id": _rid("999"), "duration": 2.0, "is_team_0": False},
        ]},
    },
}


def test_extract(monkeypatch, tmp_path):
    monkeypatch.setattr(events.subtr_actor, "get_summed_stats", lambda *a, **k: SUMMED)
    out = events.extract(tmp_path / "x.replay", ROSTER, FRAMES_DATA)

    # tiempos relativos a t0 = 10.0; el goleador del roster sale con su nombre
    assert out["goals"] == [{"t": 1.0, "name": "Enric", "team": 0, "score": [1, 0]}]
    kinds = {(e["kind"], e["name"], e["t"]) for e in out["stat_events"]}
    assert ("shot", "Enric", 0.5) in kinds
    assert ("save", "Enric", 1.0) in kinds  # el rival homónimo, por su nick

    # el rival "Enric" NO contamina los contadores del roster (join por id):
    # tiró su propio saque y tocó primero, pero eso no suma al Enric nuestro
    kp = out["kickoff_players"]
    assert set(kp) == {"Enric"}  # solo roster
    assert kp["Enric"] == {
        "kickoffs": 1, "taken": 1, "first_touches": 0, "fakes": 0, "avg_boost_after": 66.0,
    }

    k = out["kickoffs"][0]
    assert k["first_touch"] == "Enric"  # nick visible (cronología), rival
    assert k["first_touch_team"] == 1
    assert k["outcome"] == 1

    assert out["rotation"]["Enric"] == {
        "pct_first_man": 30.0, "pct_second_man": 30.0, "pct_third_man": 40.0,
        "became_first_man": 5,
    }
    assert out["sustained_possession_s"] == {"Enric": 3.0}
    assert out["sustained_possession_teams_s"] == {"0": 3.0, "1": 2.0}

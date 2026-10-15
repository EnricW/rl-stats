"""Tests de sync.normalize: deducción de our_team/result y privacidad."""

from pipeline.sync import normalize

ROSTER = {
    ("steam", "111"): "Enric",
    ("steam", "222"): "Ray",
    ("xbox", "333"): "Eric",
}


def _player(platform, pid, name, goals=0, mvp=False):
    return {
        "id": {"platform": platform, "id": pid},
        "name": name,
        "car_name": "Octane",
        "rank": {"id": "diamond-2", "tier": 16, "division": 3},
        "stats": {"core": {"goals": goals, "mvp": mvp}},
    }


def _replay(blue_goals=3, orange_goals=1):
    return {
        "id": "aaaabbbb-cccc-dddd-eeee-ffff00001111",
        "date": "2026-10-14T20:00:00+02:00",
        "playlist_id": "ranked-standard",
        "map_name": "DFH Stadium",
        "duration": 300,
        "overtime": False,
        "blue": {
            "name": "BLUE",
            "stats": {"core": {"goals": blue_goals}},
            "players": [
                _player("Steam", "111", "Reiben", goals=2, mvp=True),
                _player("Steam", "222", "Scotaiel"),
                _player("Xbox", "333", "saPbe", goals=1),
            ],
        },
        "orange": {
            "name": "ORANGE",
            "stats": {"core": {"goals": orange_goals}},
            "players": [_player("Steam", "999", "Rival1"), _player("Epic", "888", "Rival2")],
        },
    }


def test_normalize_basico():
    m = normalize(_replay(), ROSTER)
    assert m["mode"] == "3v3"
    assert m["our_team"] == "blue"
    assert m["result"] == "win"
    assert m["score"] == {"blue": 3, "orange": 1}
    enric = next(p for p in m["players"] if p["name"] == "Enric")
    assert enric["roster"] is True
    assert enric["in_game_name"] == "Reiben"
    assert enric["mvp"] is True


def test_normalize_privacidad():
    m = normalize(_replay(), ROSTER)
    assert "ballchasing_url" not in m
    for p in m["players"]:
        if p["roster"]:
            # los IDs del roster sí se publican (ya constan en players.yml)
            assert p["platform_id"]
        else:
            # los de rivales, nunca
            assert "platform_id" not in p and "platform" not in p


def test_normalize_derrota_y_empate():
    assert normalize(_replay(1, 2), ROSTER)["result"] == "loss"
    empate = normalize(_replay(2, 2), ROSTER)
    assert empate["result"] is None


def test_normalize_sin_equipo_claro():
    # mismo número de jugadores del roster en ambos lados -> our_team ambiguo
    replay = _replay()
    replay["orange"]["players"] = replay["blue"]["players"][:]
    m = normalize(replay, ROSTER)
    assert m["our_team"] is None
    assert m["result"] is None

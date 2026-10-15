"""Extrae eventos con timestamp de los .replay archivados (subtr-actor).

Complementa a frames.py (trayectorias para el visor) con un JSON ligero por
partida: tiros/paradas/asistencias con su tiempo exacto, saques iniciales
(kickoffs), reparto de roles de rotación y posesión por jugador. Lo consumen
la web (cronología rica, secciones de saques y rotación), aggregate.py
(métricas derivadas) y report.py (contexto de eventos para la IA).

Para cada partida con .replay en replays/archive/ y sin data/events/<id>.json.
"""

import math

import subtr_actor

from pipeline.manifest import EVENTS_VERSION, run_stage
from pipeline.util import EVENTS_DIR, load_roster


def _pid(obj):
    """{'Steam': '7656...'} -> '7656...' (vale cualquier plataforma)."""
    return str(next(iter(obj.values()))) if obj else ""


def _r(value, digits=1):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits)


def extract(replay_path, roster):
    data = subtr_actor.get_replay_frames_data(str(replay_path))
    summed = subtr_actor.get_summed_stats(
        str(replay_path), module_names=["kickoff", "rotation", "player_possession"]
    )
    meta = summed["replay_meta"]
    modules = summed["modules"]

    # id de plataforma -> {nombre, equipo, roster}; el roster manda sobre el nick
    players = {}
    for team_key, team in (("team_zero", 0), ("team_one", 1)):
        for p in meta.get(team_key) or []:
            rid = p.get("remote_id") or {}
            platform, pid = next(iter(rid.items())) if rid else ("", "")
            name = roster.get((str(platform).lower(), str(pid)))
            players[str(pid)] = {
                "name": name or p.get("name"),
                "team": team,
                "roster": name is not None,
            }

    def who(obj):
        return players.get(_pid(obj)) or {"name": "?", "team": None, "roster": False}

    # Base temporal: el mismo t0 que frames.py, para que todos los eventos
    # compartan eje con las trayectorias y los goles del visor.
    meta_frames = (data.get("frame_data") or {}).get("metadata_frames") or []
    t0 = meta_frames[0]["time"] if meta_frames else 0.0

    def frame_time(frame):
        if 0 <= frame < len(meta_frames):
            return round(float(meta_frames[frame]["time"]) - t0, 2)
        return None

    goals = []
    for g in data.get("goal_events") or []:
        p = who(g.get("player"))
        goals.append({
            "t": round(float(g["time"]) - t0, 2),
            "name": p["name"],
            "team": 0 if g.get("scoring_team_is_team_0") else 1,
            "score": [g.get("team_zero_score", 0), g.get("team_one_score", 0)],
        })

    # Tiros, paradas y asistencias (de ambos equipos, para la cronología).
    stat_events = []
    for e in data.get("player_stat_events") or []:
        p = who(e.get("player"))
        row = {
            "t": frame_time(e.get("frame", -1)),
            "kind": str(e.get("kind", "")).lower(),
            "name": p["name"],
            "team": 0 if e.get("is_team_0") else 1,
        }
        shot = e.get("shot") or {}
        if shot:
            row["speed_to_goal"] = _r(shot.get("ball_speed_toward_goal"), 0)
            row["dist_to_goal"] = _r(shot.get("distance_to_goal_center"), 0)
        stat_events.append(row)
    stat_events.sort(key=lambda r: (r["t"] is None, r["t"]))

    # Saques iniciales: un evento por kickoff + resumen por jugador del roster.
    kickoffs = []
    _OUTCOMES = {"team_zero_win": 0, "team_one_win": 1}
    for k in modules.get("kickoff", {}).get("events") or []:
        takers = {}
        for key, team in (("team_zero_taker", 0), ("team_one_taker", 1)):
            taker = k.get(key) or {}
            if taker.get("player"):
                takers[str(team)] = who(taker["player"])["name"]
        ft = who(k.get("first_touch_player")) if k.get("first_touch_player") else None
        kickoffs.append({
            "t": round(float(k["start_time"]) - t0, 2),
            "type": k.get("kickoff_type"),
            "takers": takers,
            "first_touch": ft["name"] if ft else None,
            "first_touch_team": (
                0 if k.get("first_touch_team_is_team_0")
                else 1 if k.get("first_touch_team_is_team_0") is False else None
            ),
            "outcome": _OUTCOMES.get(k.get("outcome")),  # null = neutral
            "goal_team": (
                0 if k.get("scoring_team_is_team_0")
                else 1 if k.get("scoring_team_is_team_0") is False else None
            ),
        })

    kickoff_players = {}
    for ps in modules.get("kickoff", {}).get("player_stats") or []:
        p = who(ps.get("player_id"))
        if not p["roster"]:
            continue
        s = ps.get("stats") or {}
        samples = s.get("boost_after_sample_count") or 0
        taken = sum(
            1 for k in kickoffs
            if p["name"] in (k["takers"] or {}).values()
        )
        kickoff_players[p["name"]] = {
            "kickoffs": s.get("count", 0),
            "taken": taken,
            "first_touches": sum(1 for k in kickoffs if k["first_touch"] == p["name"]),
            "fakes": s.get("fakes", 0),
            "avg_boost_after": _r((s.get("cumulative_boost_after") or 0) / samples) if samples else None,
        }

    # Rotación: % del tiempo activo como 1.º/2.º/3.er hombre (roster).
    rotation = {}
    for ps in modules.get("rotation", {}).get("player_stats") or []:
        p = who(ps.get("player_id"))
        if not p["roster"]:
            continue
        s = ps.get("stats") or {}
        active = s.get("active_game_time") or 0

        def pct(key):
            return _r((s.get(key) or 0) / active * 100) if active else None

        rotation[p["name"]] = {
            "pct_first_man": pct("time_first_man"),
            "pct_second_man": pct("time_second_man"),
            "pct_third_man": pct("time_third_man"),
            "became_first_man": s.get("became_first_man_count"),
        }

    # Posesión individual: suma de los tramos de posesión de cada jugador.
    possession_players, possession_teams = {}, {"0": 0.0, "1": 0.0}
    for span in modules.get("player_possession", {}).get("events") or []:
        p = who(span.get("player_id"))
        secs = float(span.get("duration") or 0)
        possession_teams["0" if span.get("is_team_0") else "1"] += secs
        if p["roster"]:
            possession_players[p["name"]] = possession_players.get(p["name"], 0.0) + secs
    possession_players = {n: round(s, 1) for n, s in possession_players.items()}
    possession_teams = {t: round(s, 1) for t, s in possession_teams.items()}

    return {
        "goals": goals,
        "stat_events": stat_events,
        "kickoffs": kickoffs,
        "kickoff_players": kickoff_players,
        "rotation": rotation,
        "sustained_possession_s": possession_players,
        "sustained_possession_teams_s": possession_teams,
    }


def main():
    run_stage(
        "events", EVENTS_VERSION, EVENTS_DIR, extract, load_roster(),
        describe=lambda p: (
            f"{len(p['stat_events'])} tiros/paradas/asist., {len(p['kickoffs'])} kickoffs"
        ),
    )


if __name__ == "__main__":
    main()

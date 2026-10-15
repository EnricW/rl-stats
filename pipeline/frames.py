"""Extrae trayectorias de los .replay archivados para el visor 3D de la web.

Para cada partida con .replay en replays/archive/ y sin data/frames/<id>.json,
parsea el replay con subtr-actor y escribe un JSON compacto: posiciones y
rotaciones de bola y coches a FPS fijos, boost, reloj del partido y goles con
su tiempo exacto. La web lo carga bajo demanda en la página de partida.
"""

import math

# OJO: numpy no se importa aquí, pero sigue en requirements.txt porque el
# ndarray que devuelve subtr-actor lo necesita en tiempo de ejecución.
import subtr_actor

from pipeline.util import ARCHIVE_DIR, FRAMES_DIR, MATCHES_DIR, load_roster, write_json

FPS = 10

# Columnas del ndarray de subtr-actor: 12 globales (bola) + 14 por jugador.
BALL_COLS = 12
PLAYER_COLS = 14


def _round(value, digits=0):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits) if digits else int(round(float(value)))


def extract(replay_path, roster):
    info, arr = subtr_actor.get_ndarray_with_info_from_replay_filepath(
        str(replay_path), fps=FPS
    )
    events = subtr_actor.get_replay_frames_data(str(replay_path))
    meta = info["replay_meta"]

    # Jugadores en el orden de las columnas: primero team 0, luego team 1.
    players, ids = [], []
    for team_key, team in (("team_zero", 0), ("team_one", 1)):
        for p in meta.get(team_key) or []:
            rid = p.get("remote_id") or {}
            platform, pid = (next(iter(rid.items())) if rid else ("", ""))
            name = roster.get((str(platform).lower(), str(pid))) or p.get("name")
            players.append({"name": name, "team": team})
            ids.append(str(pid))

    # Base de tiempos: el reloj interno del replay (los goles usan el mismo).
    meta_frames = (events.get("frame_data") or {}).get("metadata_frames") or []
    t0 = meta_frames[0]["time"] if meta_frames else 0.0
    n = arr.shape[0]

    # seconds_remaining y fase de juego remuestreados a FPS.
    # replicated_game_state_name: 0 = cuenta atrás, 2 = juego, 3 = gol/repetición.
    _PHASES = {0: 0, 2: 1, 3: 2}  # -> 0 countdown, 1 play, 2 goal/replay
    clock, phase, j = [], [], 0
    for i in range(n):
        t = t0 + i / FPS
        while j + 1 < len(meta_frames) and meta_frames[j + 1]["time"] <= t:
            j += 1
        frame = meta_frames[j] if meta_frames else {}
        clock.append(int(frame.get("seconds_remaining") or 0))
        phase.append(_PHASES.get(frame.get("replicated_game_state_name"), 1))

    goals = []
    for g in events.get("goal_events") or []:
        rid = g.get("player") or {}
        pid = str(next(iter(rid.values()))) if rid else ""
        idx = ids.index(pid) if pid in ids else None
        goals.append({
            "t": round(float(g["time"]) - t0, 2),
            "name": players[idx]["name"] if idx is not None else "?",
            "team": 0 if g.get("scoring_team_is_team_0") else 1,
            "score": [g.get("team_zero_score", 0), g.get("team_one_score", 0)],
        })

    ball = [[_round(arr[i][0]), _round(arr[i][1]), _round(arr[i][2])] for i in range(n)]
    cars = []
    for p in range(len(players)):
        base = BALL_COLS + p * PLAYER_COLS
        rows = []
        for i in range(n):
            boost = arr[i][base + 12]
            rows.append([
                _round(arr[i][base]), _round(arr[i][base + 1]), _round(arr[i][base + 2]),
                _round(arr[i][base + 3], 2), _round(arr[i][base + 4], 2), _round(arr[i][base + 5], 2),
                None if math.isnan(boost) else int(round(boost / 2.55)),
            ])
        cars.append(rows)

    pads = [
        [int(p["position"]["x"]), int(p["position"]["y"]), 1 if p.get("size") == "Big" else 0]
        for p in events.get("boost_pads") or []
    ]

    return {
        "fps": FPS,
        "players": players,
        "goals": goals,
        "clock": clock,
        "phase": phase,
        "pads": pads,
        "ball": ball,
        "cars": cars,
    }


def main():
    roster = load_roster()
    done, skipped = 0, 0
    for match_file in sorted(MATCHES_DIR.glob("*.json")):
        replay_id = match_file.stem
        out = FRAMES_DIR / f"{replay_id}.json"
        replay = ARCHIVE_DIR / f"{replay_id}.replay"
        if out.exists():
            continue
        if not replay.exists():
            skipped += 1
            continue
        try:
            payload = extract(replay, roster)
        except Exception as exc:  # un replay corrupto no debe parar el pipeline
            print(f"  · {replay_id}: no se pudo parsear ({exc})")
            skipped += 1
            continue
        payload["id"] = replay_id
        # compact: a ~5k frames por partida, la indentación multiplica el
        # tamaño por ~3 y este archivo se descarga entero en la web
        write_json(out, payload, compact=True)
        done += 1
        print(f"  + frames de {replay_id}: {len(payload['ball'])} frames, {len(payload['goals'])} goles")
    print(f"frames: {done} generados, {skipped} sin replay o con error")


if __name__ == "__main__":
    main()

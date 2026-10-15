"""Sincroniza el grupo de ballchasing con data/matches/.

Para cada replay nuevo del grupo descarga las stats completas, las normaliza
a nuestro esquema y (opcionalmente) archiva el .replay original.

Uso: python -m pipeline.sync [--no-archive] [--refetch]
  --refetch: re-descarga y re-normaliza también las partidas ya existentes
  (backfill tras añadir campos nuevos a normalize(); no re-descarga .replay).
(requiere BALLCHASING_TOKEN en el .env de la raíz)
"""

import argparse

from pipeline.ballchasing import BallchasingClient
from pipeline.util import (
    ARCHIVE_DIR,
    EVENTS_DIR,
    FRAMES_DIR,
    MATCHES_DIR,
    load_roster,
    load_settings,
    mode_from_playlist,
    require_secret,
    write_json,
)


def normalize(replay, roster):
    """Convierte la respuesta de GET /api/replays/{id} a data/matches/<id>.json.

    Los bloques de stats por jugador (core/boost/movement/positioning/demo) se
    guardan tal cual los devuelve ballchasing: el esquema lo dicta su API.
    """
    teams = {}
    players = []
    for color in ("blue", "orange"):
        team = replay.get(color) or {}
        teams[color] = {
            "name": team.get("name"),
            "goals": ((team.get("stats") or {}).get("core") or {}).get("goals", 0),
            "stats": team.get("stats") or {},
        }
        for p in team.get("players") or []:
            pid = p.get("id") or {}
            platform = str(pid.get("platform", "")).lower()
            platform_id = str(pid.get("id", ""))
            roster_name = roster.get((platform, platform_id))
            player = {
                "name": roster_name or p.get("name"),
                "in_game_name": p.get("name"),
                "roster": roster_name is not None,
                "team": color,
                "mvp": bool((p.get("stats") or {}).get("core", {}).get("mvp")),
                "car": p.get("car_name"),
                "rank": p.get("rank"),  # {id, tier, division, name} o null
                "stats": p.get("stats") or {},
            }
            # Privacidad: los IDs de plataforma solo se publican para el roster
            # (ya constan en config/players.yml); los de rivales, nunca.
            if roster_name is not None:
                player["platform"] = platform
                player["platform_id"] = platform_id
            players.append(player)

    roster_by_team = {c: sum(1 for p in players if p["team"] == c and p["roster"]) for c in teams}
    our_team = None
    if roster_by_team["blue"] != roster_by_team["orange"]:
        our_team = max(roster_by_team, key=roster_by_team.get)

    result = None
    if our_team:
        rival = "orange" if our_team == "blue" else "blue"
        if teams[our_team]["goals"] != teams[rival]["goals"]:
            result = "win" if teams[our_team]["goals"] > teams[rival]["goals"] else "loss"

    return {
        "id": replay["id"],
        "date": replay.get("date"),
        "playlist": replay.get("playlist_id"),
        "mode": mode_from_playlist(replay.get("playlist_id")),
        "map": replay.get("map_name") or replay.get("map_code"),
        "duration": replay.get("duration"),
        "overtime": bool(replay.get("overtime")),
        "min_rank": replay.get("min_rank"),  # rango del lobby, si es competitiva
        "max_rank": replay.get("max_rank"),
        "score": {c: teams[c]["goals"] for c in teams},
        "our_team": our_team,
        "result": result,
        # Privacidad: la URL de ballchasing (unlisted) no se publica en la web.
        "teams": teams,
        "players": players,
    }


def main():
    parser = argparse.ArgumentParser(description="Sincroniza el grupo de ballchasing con data/matches/")
    parser.add_argument("--no-archive", action="store_true", help="no descargar el .replay original")
    parser.add_argument("--refetch", action="store_true",
                        help="re-normalizar también las partidas ya existentes")
    args = parser.parse_args()
    archive = not args.no_archive
    refetch = args.refetch
    settings = load_settings()
    group = (settings.get("ballchasing") or {}).get("group") or ""
    if not group:
        raise SystemExit("Configura ballchasing.group en config/settings.yml")
    if settings["ballchasing"].get("archive_replays") is False:
        archive = False

    client = BallchasingClient(require_secret("BALLCHASING_TOKEN"))
    roster = load_roster()
    known = {p.stem for p in MATCHES_DIR.glob("*.json")}

    new, skipped = 0, 0
    for entry in client.iter_group_replays(group):
        replay_id = entry["id"]
        dest = ARCHIVE_DIR / f"{replay_id}.replay"
        if replay_id in known and not refetch:
            # Los .replay no se versionan y el runner de CI es efímero: si a
            # una partida conocida aún le falta un derivado (frames/events,
            # p. ej. porque su parseo falló en una pasada anterior o tras un
            # backfill que los borró), re-descarga el replay para reintentarlo.
            if archive and not dest.exists() and (
                not (FRAMES_DIR / f"{replay_id}.json").exists()
                or not (EVENTS_DIR / f"{replay_id}.json").exists()
            ):
                client.download_replay(replay_id, dest)
            continue
        full = client.get_replay(replay_id)
        if full.get("status") != "ok":
            print(f"  · {replay_id}: estado '{full.get('status')}', se reintentará")
            skipped += 1
            continue
        write_json(MATCHES_DIR / f"{replay_id}.json", normalize(full, roster))
        if archive and not dest.exists():
            client.download_replay(replay_id, dest)
        new += 1
        print(f"  + {replay_id}: {full.get('playlist_id')} {full.get('date')}")

    print(f"sync: {new} partidas nuevas, {skipped} pendientes, {len(known)} ya existentes")


if __name__ == "__main__":
    main()

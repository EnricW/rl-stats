"""Recalcula los agregados a partir de data/matches/:

- data/players/<nombre>.json: histórico por partida y medias por modo.
- data/summary.json: índice de partidas y balance del equipo para la portada.

Uso: python -m pipeline.aggregate
"""

from datetime import datetime, timezone

from pipeline import manifest as mf
from pipeline.util import (
    DATA_DIR,
    EVENTS_DIR,
    FRAMES_DIR,
    PLAYERS_DIR,
    REPORTS_DIR,
    load_matches,
    load_settings,
    read_json,
    write_json_if_changed,
)

# métrica de la web -> ruta dentro del bloque stats de ballchasing
METRICS = {
    "goals": ("core", "goals"),
    "assists": ("core", "assists"),
    "saves": ("core", "saves"),
    "shots": ("core", "shots"),
    "score": ("core", "score"),
    "shooting_pct": ("core", "shooting_percentage"),
    "bpm": ("boost", "bpm"),
    "bcpm": ("boost", "bcpm"),
    "avg_boost": ("boost", "avg_amount"),
    "pct_zero_boost": ("boost", "percent_zero_boost"),
    "boost_stolen": ("boost", "amount_stolen"),
    "boost_overfill": ("boost", "amount_overfill"),
    "avg_speed": ("movement", "avg_speed"),
    "pct_supersonic": ("movement", "percent_supersonic_speed"),
    "pct_ground": ("movement", "percent_ground"),
    "pct_low_air": ("movement", "percent_low_air"),
    "pct_high_air": ("movement", "percent_high_air"),
    "pct_defensive_third": ("positioning", "percent_defensive_third"),
    "pct_neutral_third": ("positioning", "percent_neutral_third"),
    "pct_offensive_third": ("positioning", "percent_offensive_third"),
    "pct_behind_ball": ("positioning", "percent_behind_ball"),
    "pct_most_back": ("positioning", "percent_most_back"),
    "pct_most_forward": ("positioning", "percent_most_forward"),
    "avg_dist_to_mates": ("positioning", "avg_distance_to_mates"),
    "ga_last_defender": ("positioning", "goals_against_while_last_defender"),
    "demos_inflicted": ("demo", "inflicted"),
    "demos_taken": ("demo", "taken"),
}


# métricas derivadas de data/events/<id>.json (si la partida tiene eventos)
EVENT_METRICS = ("kickoff_ft_pct", "pct_first_man", "pct_third_man")


def extract_metrics(stats):
    out = {}
    for key, (block, field) in METRICS.items():
        value = (stats.get(block) or {}).get(field)
        if isinstance(value, (int, float)):
            out[key] = round(float(value), 2)
    return out


def extract_event_metrics(events, name):
    """Métricas del jugador derivadas de los eventos de la partida."""
    out = {}
    kp = (events.get("kickoff_players") or {}).get(name)
    if kp and kp.get("taken"):
        out["kickoff_ft_pct"] = round(kp["first_touches"] / kp["taken"] * 100, 2)
    rot = (events.get("rotation") or {}).get(name) or {}
    for key, src in (("pct_first_man", "pct_first_man"), ("pct_third_man", "pct_third_man")):
        if rot.get(src) is not None:
            out[key] = rot[src]
    return out


def averages(rows):
    """Media por métrica sobre una lista de dicts de métricas."""
    out = {}
    for key in (*METRICS, *EVENT_METRICS):
        values = [r[key] for r in rows if key in r]
        if values:
            out[key] = round(sum(values) / len(values), 2)
    return out


def main():
    matches = load_matches()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # ---- por jugador (solo roster) ----
    histories = {}
    for match in matches:
        events_path = EVENTS_DIR / f"{match['id']}.json"
        events = read_json(events_path) if events_path.exists() else None
        for p in match["players"]:
            if not p["roster"]:
                continue
            row = {
                "match_id": match["id"],
                "date": match["date"],
                "mode": match["mode"],
                "result": match["result"],
                "mvp": p["mvp"],
                **extract_metrics(p["stats"]),
            }
            if isinstance(p.get("rank"), dict):
                # rango competitivo del jugador en esa partida (para evolución)
                row["rank_id"] = p["rank"].get("id")
                row["rank_tier"] = p["rank"].get("tier")
                row["rank_division"] = p["rank"].get("division")
            if events:
                row.update(extract_event_metrics(events, p["name"]))
            histories.setdefault(p["name"], []).append(row)

    for name, history in histories.items():
        modes = {}
        for mode in sorted({r["mode"] for r in history}):
            rows = [r for r in history if r["mode"] == mode]
            wins = sum(1 for r in rows if r["result"] == "win")
            modes[mode] = {
                "games": len(rows),
                "wins": wins,
                "winrate": round(wins / len(rows), 3) if rows else None,
                "averages": averages(rows),
                "last10_averages": averages(rows[-10:]),
            }
        write_json_if_changed(
            PLAYERS_DIR / f"{name}.json",
            {"name": name, "generated_at": now, "modes": modes, "history": history},
        )

    # ---- índice para la portada ----
    team_modes = {}
    index = []
    for match in matches:
        if match["result"]:
            tm = team_modes.setdefault(match["mode"], {"games": 0, "wins": 0})
            tm["games"] += 1
            tm["wins"] += 1 if match["result"] == "win" else 0
        index.append(
            {
                "id": match["id"],
                "date": match["date"],
                "mode": match["mode"],
                "map": match["map"],
                "score": match["score"],
                "our_team": match["our_team"],
                "result": match["result"],
                "overtime": match["overtime"],
                # disponibilidad de derivados: la web solo pide lo que existe
                "has_report": (REPORTS_DIR / f"{match['id']}.md").exists(),
                "has_frames": (FRAMES_DIR / f"{match['id']}.json").exists(),
                "has_events": (EVENTS_DIR / f"{match['id']}.json").exists(),
                "players": [
                    {
                        "name": p["name"],
                        "mvp": p["mvp"],
                        **{
                            k: extract_metrics(p["stats"]).get(k)
                            for k in ("goals", "assists", "saves", "shots", "score")
                        },
                    }
                    for p in match["players"]
                    if p["roster"]
                ],
            }
        )
    index.sort(key=lambda m: m["date"] or "", reverse=True)

    # Vista para la web del histórico de informes (rutas incluidas: la web ya
    # no reconstruye nombres de archivo a mano) y del progreso hacia el
    # siguiente informe de tendencia de cada jugador.
    manifest = mf.load()
    settings = load_settings()
    reports_view = {
        "every": int(settings["reports"].get("player_report_every", 10)),
        "team": [{"date": i["date"], "path": i["path"]} for i in manifest["reports"]["team"]],
        "players": {
            name: {
                "items": [{"date": i["date"], "path": i["path"]} for i in items],
                "games_at_last": int(manifest["player_reports_state"].get(name, 0)),
            }
            for name, items in manifest["reports"]["players"].items()
        },
    }

    write_json_if_changed(
        DATA_DIR / "summary.json",
        {
            "generated_at": now,
            "team": {"modes": team_modes},
            "players": sorted(histories),
            "matches": index,
            "reports": reports_view,
        },
    )
    print(f"aggregate: {len(matches)} partidas, {len(histories)} jugadores")


if __name__ == "__main__":
    main()

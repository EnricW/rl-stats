"""Genera informes con la API de Claude a partir de los JSON ya calculados.

- Informe de partida: para cada partida sin informe (modelo rápido).
- Informe de jugador: cada N partidas del jugador (modelo de tendencias).
- Informe de equipo: con --team (lo dispara el cron semanal).

Claude nunca ve el .replay: solo JSON con números reales.

Uso: python -m pipeline.report [--team] [--match <id>]
(requiere ANTHROPIC_API_KEY en el .env de la raíz; plantilla en .env.example)
"""

import argparse
import json
from datetime import datetime, timezone

import anthropic

from pipeline.util import (
    EVENTS_DIR,
    MATCHES_DIR,
    PLAYERS_DIR,
    PROMPTS_DIR,
    REPORTS_DIR,
    load_settings,
    read_json,
    require_secret,
    write_json,
    write_text_atomic,
)

# Cliente perezoso: así importar este módulo (p. ej. desde los tests) no exige
# tener la clave, y se puede sustituir por un doble en las pruebas.
_client = None


def get_client():
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=require_secret("ANTHROPIC_API_KEY"))
    return _client


def ask_claude(model, system_prompt, payload_text):
    kwargs = {}
    if model.startswith("claude-sonnet-5-5"):
        # Fallback automático de servidor ante un refusal del clasificador.
        kwargs = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    # El thinking adaptativo (activo por defecto) también consume max_tokens.
    response = get_client().beta.messages.create(
        model=model,
        max_tokens=16000,
        system=system_prompt,
        messages=[{"role": "user", "content": payload_text}],
        **kwargs,
    )
    if response.stop_reason not in ("end_turn", "stop_sequence"):
        raise RuntimeError(f"Respuesta incompleta ({response.stop_reason})")
    text = "".join(b.text for b in response.content if b.type == "text")
    footer = (
        f"\n\n---\n*Informe generado por {model} el "
        f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.*\n"
    )
    return text.strip() + footer


def prompt(name):
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def slim_match(match):
    """Versión compacta de la partida para el prompt: de los equipos pasa un
    resumen curado (nunca los bloques de stats en bruto, por tokens)."""
    slim = {k: v for k, v in match.items() if k != "teams"}
    teams = {}
    for color, t in match["teams"].items():
        stats = t.get("stats") or {}
        core = stats.get("core") or {}
        ball = stats.get("ball") or {}
        demo = stats.get("demo") or {}
        teams[color] = {
            "goals": t.get("goals"),
            "shots": core.get("shots"),
            "shots_against": core.get("shots_against"),
            "saves": core.get("saves"),
            "possession_time_s": ball.get("possession_time"),
            "time_ball_in_own_side_s": ball.get("time_in_side"),
            "demos_inflicted": demo.get("inflicted"),
        }
    slim["teams"] = teams
    return slim


def match_events(match_id):
    """Eventos de la partida (si el replay se pudo parsear): cronología de
    goles/tiros/paradas, kickoffs, rotación y posesión sostenida."""
    path = EVENTS_DIR / f"{match_id}.json"
    if not path.exists():
        return None
    ev = read_json(path)
    keys = (
        "goals", "stat_events", "kickoffs", "kickoff_players",
        "rotation", "sustained_possession_s",
    )
    return {k: ev[k] for k in keys if ev.get(k)}


def player_context(name, mode):
    """Medias históricas del jugador en ese modo, si existen."""
    path = PLAYERS_DIR / f"{name}.json"
    if not path.exists():
        return None
    data = read_json(path)
    mode_data = (data.get("modes") or {}).get(mode)
    if not mode_data:
        return None
    return {
        "games": mode_data["games"],
        "winrate": mode_data["winrate"],
        "averages": mode_data["averages"],
        "last10_averages": mode_data["last10_averages"],
    }


def match_report(match, settings):
    context = {
        "partida": slim_match(match),
        "medias_historicas_por_jugador": {
            p["name"]: player_context(p["name"], match["mode"])
            for p in match["players"]
            if p["roster"]
        },
    }
    events = match_events(match["id"])
    if events:
        context["eventos"] = events
    text = ask_claude(
        settings["reports"]["match_model"],
        prompt("match.md"),
        json.dumps(context, ensure_ascii=False, indent=1),
    )
    out = REPORTS_DIR / f"{match['id']}.md"
    write_text_atomic(out, text)
    print(f"  informe de partida: {out.name}")


def player_report(name, settings):
    data = read_json(PLAYERS_DIR / f"{name}.json")
    text = ask_claude(
        settings["reports"]["trend_model"],
        prompt("player.md"),
        json.dumps(data, ensure_ascii=False, indent=1),
    )
    date = _report_date()
    out = REPORTS_DIR / f"player-{name}-{date}.md"
    write_text_atomic(out, text)
    _register_report("players", date, name)
    print(f"  informe de jugador: {out.name}")


def team_report(settings):
    context = {
        "jugadores": {
            p.stem: read_json(p) for p in sorted(PLAYERS_DIR.glob("*.json"))
        }
    }
    text = ask_claude(
        settings["reports"]["trend_model"],
        prompt("team.md"),
        json.dumps(context, ensure_ascii=False, indent=1),
    )
    date = _report_date()
    out = REPORTS_DIR / f"team-{date}.md"
    write_text_atomic(out, text)
    _register_report("team", date)
    print(f"  informe de equipo: {out.name}")


# Estado de los informes de jugador: con cuántas partidas se generó el último.
# Sin esto, "games % every == 0" regeneraría (y cobraría) el mismo informe en
# cada pasada del cron hasta que el jugador jugase otra partida.
STATE_FILE = REPORTS_DIR / "player_reports_state.json"

# Histórico de informes: los de tendencia y equipo se guardan fechados
# (player-<nombre>-<fecha>.md, team-<fecha>.md) y este índice dice a la web
# qué fechas existen (un sitio estático no puede listar directorios).
INDEX_FILE = REPORTS_DIR / "index.json"


def _load_state():
    return read_json(STATE_FILE) if STATE_FILE.exists() else {}


def _report_date():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _register_report(kind, date, name=None):
    """Apunta un informe fechado en index.json (kind: 'team' | 'players')."""
    idx = read_json(INDEX_FILE) if INDEX_FILE.exists() else {"team": [], "players": {}}
    dates = idx.setdefault("players", {}).setdefault(name, []) if name else idx.setdefault("team", [])
    if date not in dates:
        dates.append(date)
        dates.sort()
    write_json(INDEX_FILE, idx)


def main():
    parser = argparse.ArgumentParser(description="Genera informes IA de los JSON ya calculados")
    parser.add_argument("--team", action="store_true", help="informe semanal de equipo")
    parser.add_argument("--match", metavar="ID", help="regenerar el informe de una partida")
    args = parser.parse_args()
    settings = load_settings()
    every = int(settings["reports"].get("player_report_every", 10))

    if args.team:
        team_report(settings)
        return

    if args.match:
        # el id viene de la línea de comandos y acaba en una ruta: solo UUID
        if not all(c in "0123456789abcdef-" for c in args.match.lower()):
            parser.error(f"id de partida no válido: {args.match}")
        match_report(read_json(MATCHES_DIR / f"{args.match}.json"), settings)
        return

    failures = 0

    # Partidas sin informe (en orden cronológico). Un informe que falle no
    # bloquea los demás ni el commit/deploy de los datos ya sincronizados:
    # al no escribirse su .md, se reintenta en la siguiente pasada.
    matches = sorted(MATCHES_DIR.glob("*.json"))
    pending = [m for m in matches if not (REPORTS_DIR / f"{m.stem}.md").exists()]
    for path in pending:
        try:
            match_report(read_json(path), settings)
        except Exception as exc:
            failures += 1
            print(f"  ! informe de {path.stem} falló (se reintentará): {exc}")

    # Informe de tendencia cuando un jugador suma N partidas desde el último
    state = _load_state()
    for path in sorted(PLAYERS_DIR.glob("*.json")):
        data = read_json(path)
        games = len(data.get("history") or [])
        if games >= every and games - int(state.get(data["name"], 0)) >= every:
            try:
                player_report(data["name"], settings)
            except Exception as exc:
                failures += 1
                print(f"  ! informe de {data['name']} falló (se reintentará): {exc}")
            else:
                state[data["name"]] = games
                write_json(STATE_FILE, state)

    if failures:
        print(f"report: {failures} informes fallidos (se reintentarán en la siguiente pasada)")
    elif not pending:
        print("report: nada pendiente")


if __name__ == "__main__":
    main()

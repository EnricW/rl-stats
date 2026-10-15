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
from datetime import UTC, datetime

import anthropic

from pipeline import manifest as mf
from pipeline.util import (
    DATA_DIR,
    EVENTS_DIR,
    MATCHES_DIR,
    PLAYERS_DIR,
    PROMPTS_DIR,
    REPORTS_DIR,
    load_settings,
    read_json,
    require_secret,
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


def ask_claude(model, system_prompt, payload_text, reports_cfg, effort=None):
    kwargs = {}
    prefixes = tuple(reports_cfg.get("server_fallback_prefixes") or [])
    if prefixes and model.startswith(prefixes):
        # Fallback automático de servidor ante un refusal del clasificador.
        kwargs = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    if effort:
        kwargs["output_config"] = {"effort": effort}
    # Streaming: el thinking adaptativo también consume max_tokens, así que el
    # límite es alto y un informe con razonamiento largo superaría el timeout
    # HTTP de una petición normal. get_final_message() devuelve el mensaje
    # completo igual que create().
    with get_client().beta.messages.stream(
        model=model,
        max_tokens=int(reports_cfg.get("max_tokens", 32000)),
        system=system_prompt,
        messages=[{"role": "user", "content": payload_text}],
        **kwargs,
    ) as stream:
        response = stream.get_final_message()
    if response.stop_reason not in ("end_turn", "stop_sequence"):
        raise RuntimeError(f"Respuesta incompleta ({response.stop_reason})")
    text = "".join(b.text for b in response.content if b.type == "text")
    footer = (
        f"\n\n---\n*Informe generado por {model} el "
        f"{datetime.now(UTC).strftime('%Y-%m-%d %H:%M UTC')}.*\n"
    )
    return text.strip() + footer


def prompt(name):
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def slim_player(data, keep):
    """Recorta el histórico del jugador para los prompts de tendencia/equipo:
    las medias (modes) ya resumen la temporada entera y, sin recorte, el coste
    en tokens crecía sin límite con cada partida jugada."""
    slim = dict(data)
    slim["history"] = (data.get("history") or [])[-keep:]
    return slim


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


def match_report(match, settings, manifest):
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
    model = settings["reports"]["match_model"]
    text = ask_claude(model, prompt("match.md"),
                      json.dumps(context, ensure_ascii=False, indent=1), settings["reports"])
    out = REPORTS_DIR / f"{match['id']}.md"
    write_text_atomic(out, text)
    mf.record_match_report(manifest, match["id"], f"reports/{out.name}", model)
    mf.save(manifest)
    print(f"  informe de partida: {out.name}")


def player_report(name, settings, manifest):
    keep = int(settings["reports"].get("prompt_history_games", 20))
    data = slim_player(read_json(PLAYERS_DIR / f"{name}.json"), keep)
    model = settings["reports"]["trend_model"]
    text = ask_claude(model, prompt("player.md"),
                      json.dumps(data, ensure_ascii=False, indent=1), settings["reports"],
                      effort=settings["reports"].get("trend_effort"))
    date = _report_date()
    out = REPORTS_DIR / f"player-{name}-{date}.md"
    write_text_atomic(out, text)
    mf.register_report(manifest, date, f"reports/{out.name}", model, name=name)
    mf.save(manifest)
    print(f"  informe de jugador: {out.name}")


def _previous_team_report(manifest):
    """Último informe de equipo generado, si existe: se le pasa al siguiente
    para darle continuidad (evaluar si las prioridades marcadas se cumplieron),
    porque cada informe parte de cero sobre los números."""
    items = manifest["reports"]["team"]
    if not items:
        return None
    last = items[-1]
    path = DATA_DIR / last["path"]
    if not path.exists():
        return None
    return {"fecha": last["date"], "markdown": path.read_text(encoding="utf-8")}


def team_report(settings, manifest):
    keep = int(settings["reports"].get("prompt_history_games", 20))
    context = {
        "jugadores": {
            p.stem: slim_player(read_json(p), keep)
            for p in sorted(PLAYERS_DIR.glob("*.json"))
        }
    }
    previous = _previous_team_report(manifest)
    if previous:
        context["informe_anterior"] = previous
    model = settings["reports"]["trend_model"]
    text = ask_claude(model, prompt("team.md"),
                      json.dumps(context, ensure_ascii=False, indent=1), settings["reports"],
                      effort=settings["reports"].get("trend_effort"))
    date = _report_date()
    out = REPORTS_DIR / f"team-{date}.md"
    write_text_atomic(out, text)
    mf.register_report(manifest, date, f"reports/{out.name}", model)
    mf.save(manifest)
    print(f"  informe de equipo: {out.name}")


# El estado de los informes (histórico fechado, con qué nº de partidas se
# generó el último de cada jugador, modelo usado) vive en data/manifest.json.


def _report_date():
    return datetime.now(UTC).strftime("%Y-%m-%d")


def _team_report_due(manifest, every_days):
    """True si toca informe de equipo: nunca hubo o el último tiene N días.

    Se decide por estado (el manifiesto) y no por el evento que disparó el
    job: GitHub solo mantiene una ejecución en cola por grupo de concurrencia,
    así que el cron del lunes puede perderse si lo sustituye un aviso del
    watcher. Con esto, la siguiente pasada (sea cual sea) lo recupera.
    """
    items = manifest["reports"]["team"]
    if not items:
        return True
    last = datetime.strptime(items[-1]["date"], "%Y-%m-%d").date()
    return (datetime.now(UTC).date() - last).days >= every_days


def main():
    parser = argparse.ArgumentParser(description="Genera informes IA de los JSON ya calculados")
    parser.add_argument("--team", action="store_true", help="informe semanal de equipo")
    parser.add_argument("--match", metavar="ID", help="regenerar el informe de una partida")
    args = parser.parse_args()
    settings = load_settings()
    every = int(settings["reports"].get("player_report_every", 10))
    manifest = mf.load()

    if args.team:
        # fuerza el informe de equipo ahora, sin mirar la fecha del último
        team_report(settings, manifest)
        return

    if args.match:
        # el id viene de la línea de comandos y acaba en una ruta: solo UUID
        if not all(c in "0123456789abcdef-" for c in args.match.lower()):
            parser.error(f"id de partida no válido: {args.match}")
        match_report(read_json(MATCHES_DIR / f"{args.match}.json"), settings, manifest)
        return

    failures = 0

    # Partidas sin informe (en orden cronológico). Un informe que falle no
    # bloquea los demás ni el commit/deploy de los datos ya sincronizados:
    # al no escribirse su .md, se reintenta en la siguiente pasada.
    matches = sorted(MATCHES_DIR.glob("*.json"))
    pending = [m for m in matches if not (REPORTS_DIR / f"{m.stem}.md").exists()]
    for path in pending:
        try:
            match_report(read_json(path), settings, manifest)
        except Exception as exc:
            failures += 1
            print(f"  ! informe de {path.stem} falló (se reintentará): {exc}")

    # Informe de tendencia cuando un jugador suma N partidas desde el último
    state = manifest["player_reports_state"]
    for path in sorted(PLAYERS_DIR.glob("*.json")):
        data = read_json(path)
        games = len(data.get("history") or [])
        if games >= every and games - int(state.get(data["name"], 0)) >= every:
            try:
                player_report(data["name"], settings, manifest)
            except Exception as exc:
                failures += 1
                print(f"  ! informe de {data['name']} falló (se reintentará): {exc}")
            else:
                state[data["name"]] = games
                mf.save(manifest)

    # Informe de equipo periódico, decidido por estado (ver _team_report_due)
    team_days = int(settings["reports"].get("team_report_every_days", 7))
    if any(PLAYERS_DIR.glob("*.json")) and _team_report_due(manifest, team_days):
        try:
            team_report(settings, manifest)
        except Exception as exc:
            failures += 1
            print(f"  ! informe de equipo falló (se reintentará): {exc}")

    mf.save(manifest)

    if failures:
        print(f"report: {failures} informes fallidos (se reintentarán en la siguiente pasada)")
    elif not pending:
        print("report: nada pendiente")


if __name__ == "__main__":
    main()

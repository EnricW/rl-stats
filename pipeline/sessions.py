"""Sesiones de juego: agrupa las partidas en las "noches" en que se jugaron.

El equipo juega por tandas (13-15 partidas seguidas en una noche), así que la
unidad natural para los informes de tendencia es la sesión, no un ciclo fijo de
N partidas. Una sesión son partidas consecutivas separadas por menos de
`gap_hours`, aunque la tanda cruce la medianoche.

El agrupado es aritmética de instantes (inmune al horario de verano); la zona
horaria solo decide la FECHA con la que se etiqueta la sesión.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_GAP_HOURS = 5.0
# Partida sin `duration` en la respuesta de ballchasing: 5 min nominales.
NOMINAL_DURATION_S = 300


def local_tz(settings):
    """Zona horaria para las etiquetas (settings["timezone"]), UTC si falla."""
    name = (settings or {}).get("timezone")
    if not name:
        return UTC
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        print(f"  · aviso: zona horaria '{name}' no disponible, se usa UTC")
        return UTC


def _parse(iso):
    """Fecha ISO de ballchasing ("...Z" o con offset) a datetime con zona."""
    return datetime.fromisoformat(str(iso).replace("Z", "+00:00"))


def _duration(match):
    value = match.get("duration")
    return float(value) if isinstance(value, (int, float)) else float(NOMINAL_DURATION_S)


def _iso(dt):
    """UTC en formato "...Z": el mismo que usan los JSON publicados."""
    return dt.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def group_sessions(matches, gap_hours=DEFAULT_GAP_HOURS, tz=UTC):
    """Agrupa partidas (ordenadas por fecha ascendente, como las devuelve
    util.load_matches) en sesiones ascendentes:

        {id, date, start, end, games, match_ids}

    El id lleva la hora de inicio ("2026-10-14-1951") para que sea estable: si
    más tarde aparece un replay que crea otra sesión el mismo día, los ids ya
    informados no se desplazan. `date` es la fecha local de la primera partida
    (la que ve el usuario en la etiqueta).
    """
    gap = timedelta(hours=float(gap_hours))
    sessions = []
    for match in matches:
        if not match.get("date"):
            continue
        start = _parse(match["date"])
        end = start + timedelta(seconds=_duration(match))
        current = sessions[-1] if sessions else None
        # hueco desde el fin acumulado: las partidas de ballchasing pueden
        # solaparse unos segundos (date es el inicio y duration no siempre es
        # disjunta), y así el hueco nunca sale negativo
        if current is not None and max(start - current["_end"], timedelta(0)) < gap:
            current["_end"] = max(current["_end"], end)
            current["games"] += 1
            current["match_ids"].append(match["id"])
            continue
        local = start.astimezone(tz)
        sessions.append({
            "id": f"{local:%Y-%m-%d-%H%M}",
            "date": f"{local:%Y-%m-%d}",
            "_start": start,
            "_end": end,
            "games": 1,
            "match_ids": [match["id"]],
        })
    for s in sessions:
        s["start"] = _iso(s.pop("_start"))
        s["end"] = _iso(s.pop("_end"))
    return sessions


def is_closed(session, gap_hours=DEFAULT_GAP_HOURS, now=None):
    """True si la sesión ya terminó: sin partidas nuevas desde `gap_hours`.

    Mientras está abierta no se genera su informe; si no, cada aviso del watcher
    durante la noche regeneraría (y cobraría) el informe de la sesión en curso.
    """
    now = now or datetime.now(UTC)
    return now - _parse(session["end"]) >= timedelta(hours=float(gap_hours))


def session_of(sessions, match_id):
    """Sesión a la que pertenece una partida, o None."""
    for s in sessions:
        if match_id in s["match_ids"]:
            return s
    return None

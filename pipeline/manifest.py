"""Registro central del pipeline: data/manifest.json.

Hasta ahora el estado era "el archivo existe": nada registraba con qué versión
del extractor se generó cada derivado, qué parseos fallaron (se reintentaban
sin límite re-descargando el replay en cada pasada), ni con qué modelo y fecha
se generó cada informe. El manifiesto es la única fuente de ese estado:

  matches.<id>:
    match_guid    guid de la partida (dedup: dos compañeros subiendo su propio
                  replay de la misma partida producen ids distintos en
                  ballchasing)
    date, ingested_at
    duplicate_of  id canónico, si esta entrada es un duplicado descartado
    frames/events: {v, ok, attempts, error, at}   estado por etapa
    report:        {path, model, generated_at}    informe de la partida
  reports:
    team:    [{date, path, model}]                informes de equipo, fechados
    players: {nombre: [{session_id, date, games, path, model}]}
                  un informe de tendencia por SESIÓN de juego (ver
                  pipeline/sessions.py). `games` se guarda al generarlo, para
                  que la etiqueta de la web ("14 oct · 13 partidas") no
                  contradiga al cuerpo si la sesión crece después.

Las rutas son relativas a data/ (la web les antepone "data/").
Absorbe al antiguo reports/index.json, que se migra automáticamente la
primera vez.
"""

import copy
from datetime import UTC, datetime

from pipeline.util import (
    DATA_DIR,
    EVENTS_DIR,
    FRAMES_DIR,
    MATCHES_DIR,
    REPORTS_DIR,
    read_json,
    write_json,
)

MANIFEST_FILE = DATA_DIR / "manifest.json"
SCHEMA_VERSION = 2

# Versión de cada extractor: subirla regenera los derivados de todas las
# partidas en la siguiente pasada (antes había que borrar los archivos a mano).
FRAMES_VERSION = 1
EVENTS_VERSION = 1

# Intentos de parseo por etapa antes de desistir: un replay corrupto deja de
# re-descargarse y reintentarse en cada pasada (el error queda registrado).
MAX_ATTEMPTS = 3

_EMPTY = {
    "schema_version": SCHEMA_VERSION,
    "matches": {},
    "reports": {"team": [], "players": {}},
}


def _now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def load():
    if MANIFEST_FILE.exists():
        return _migrate_v1_to_v2(read_json(MANIFEST_FILE))
    return _migrate_legacy()


def _migrate_v1_to_v2(manifest):
    """v1 -> v2: los informes de jugador pasan de "cada N partidas" a "por
    sesión". Se descartan los items sin session_id (eran ciclos de 10 partidas,
    no sesiones) y el contador player_reports_state, que ya no hace falta: el
    estado es "qué sesiones tienen informe" y vive en los propios items."""
    if int(manifest.get("schema_version", 1)) >= 2:
        return manifest
    manifest.pop("player_reports_state", None)
    players = manifest.get("reports", {}).get("players") or {}
    for name, items in list(players.items()):
        kept = [i for i in items if i.get("session_id")]
        if len(kept) != len(items):
            print(f"  · manifiesto v2: {len(items) - len(kept)} informes de "
                  f"{name} descartados (eran por ciclo de partidas, no por sesión)")
        players[name] = kept
    manifest["schema_version"] = 2
    return manifest


def save(manifest):
    write_json(MANIFEST_FILE, manifest)


def match_entry(manifest, replay_id):
    return manifest["matches"].setdefault(replay_id, {})


def stage_pending(manifest, replay_id, stage, version):
    """True si hay que (re)generar esa etapa de la partida: no hay salida en
    disco, o se generó con una versión anterior del extractor. False si ya
    está al día o si se desistió (MAX_ATTEMPTS fallos con esta versión)."""
    out_dir = FRAMES_DIR if stage == "frames" else EVENTS_DIR
    st = manifest["matches"].get(replay_id, {}).get(stage) or {}
    up_to_date = st.get("v", 0) >= version
    if st.get("ok") and up_to_date and (out_dir / f"{replay_id}.json").exists():
        return False
    if not st.get("ok") and up_to_date and st.get("attempts", 0) >= MAX_ATTEMPTS:
        return False
    return True


def record_stage(manifest, replay_id, stage, version, ok, error=None):
    entry = match_entry(manifest, replay_id)
    prev = entry.get(stage) or {}
    # los intentos cuentan por versión: un extractor nuevo vuelve a intentarlo
    attempts = prev.get("attempts", 0) if prev.get("v") == version and not ok else 0
    entry[stage] = {
        "v": version,
        "ok": ok,
        "attempts": 1 if ok else attempts + 1,
        "error": None if ok else str(error)[:300],
        "at": _now(),
    }
    return entry[stage]


def record_ingest(manifest, replay_id, match_guid, date):
    entry = match_entry(manifest, replay_id)
    entry["match_guid"] = match_guid
    entry["date"] = date
    entry.setdefault("ingested_at", _now())


def known_guids(manifest):
    """{match_guid: id canónico} de las partidas ya ingestadas (sin duplicados)."""
    return {
        e["match_guid"]: rid
        for rid, e in manifest["matches"].items()
        if e.get("match_guid") and not e.get("duplicate_of")
    }


def record_match_report(manifest, replay_id, path, model):
    match_entry(manifest, replay_id)["report"] = {
        "path": path,
        "model": model,
        "generated_at": _now(),
    }


def register_report(manifest, date, path, model, name=None):
    """Apunta un informe de equipo fechado (los de jugador van por sesión:
    ver register_player_report)."""
    if name:
        return register_player_report(manifest, name, date, date, 0, path, model)
    items = manifest["reports"]["team"]
    items[:] = [i for i in items if i["date"] != date]
    items.append({"date": date, "path": path, "model": model})
    items.sort(key=lambda i: i["date"])


def register_player_report(manifest, name, session_id, date, games, path, model):
    """Apunta el informe de tendencia de un jugador para una sesión.

    Dedup por session_id (no por fecha: dos sesiones el mismo día tendrían el
    mismo nombre de archivo y se pisarían, que es el bug que esto arregla).
    El id lleva la hora de inicio, así que ordenar por id es ordenar
    cronológicamente.
    """
    items = manifest["reports"]["players"].setdefault(name, [])
    items[:] = [i for i in items if i.get("session_id") != session_id]
    items.append({
        "session_id": session_id,
        "date": date,
        "games": games,
        "path": path,
        "model": model,
    })
    items.sort(key=lambda i: i.get("session_id") or "")


def run_stages(specs, roster, load_shared):
    """Bucle común de frames/events: (re)genera los derivados de cada partida
    cuando el manifiesto dice que toca, y registra resultado, intentos y error.

    `load_shared(ruta)` es el parseo caro del .replay (get_replay_frames_data):
    se ejecuta UNA vez por partida y se pasa a todos los extract pendientes,
    en lugar de parsear el mismo replay dos veces (frames y luego events).

    Cada spec: {stage, version, out_dir, extract(replay, roster, shared),
    compact?, describe?(payload)}.
    """
    from pipeline.util import ARCHIVE_DIR

    manifest = load()
    counts = {s["stage"]: {"done": 0, "skipped": 0, "failed": 0} for s in specs}

    def _record_failure(spec, replay_id, exc):
        st = record_stage(manifest, replay_id, spec["stage"], spec["version"], ok=False, error=exc)
        reaction = "se desiste" if st["attempts"] >= MAX_ATTEMPTS else "se reintentará"
        print(f"  · {spec['stage']} de {replay_id}: no se pudo parsear ({exc}) — "
              f"intento {st['attempts']}/{MAX_ATTEMPTS}, {reaction}")
        counts[spec["stage"]]["failed"] += 1

    for match_file in sorted(MATCHES_DIR.glob("*.json")):
        replay_id = match_file.stem
        todo = [s for s in specs if stage_pending(manifest, replay_id, s["stage"], s["version"])]
        if not todo:
            continue
        replay = ARCHIVE_DIR / f"{replay_id}.replay"
        if not replay.exists():
            for spec in todo:
                counts[spec["stage"]]["skipped"] += 1
            continue
        try:
            shared = load_shared(str(replay))
        except Exception as exc:  # un replay corrupto no debe parar el pipeline
            for spec in todo:
                _record_failure(spec, replay_id, exc)
            continue
        for spec in todo:
            try:
                payload = spec["extract"](replay, roster, shared)
            except Exception as exc:
                _record_failure(spec, replay_id, exc)
                continue
            payload["id"] = replay_id
            write_json(spec["out_dir"] / f"{replay_id}.json", payload,
                       compact=spec.get("compact", False))
            record_stage(manifest, replay_id, spec["stage"], spec["version"], ok=True)
            counts[spec["stage"]]["done"] += 1
            describe = spec.get("describe")
            print(f"  + {spec['stage']} de {replay_id}"
                  + (f": {describe(payload)}" if describe else ""))
    save(manifest)
    for stage, c in counts.items():
        print(f"{stage}: {c['done']} generados, {c['skipped']} sin replay, {c['failed']} con error")


def _migrate_legacy():
    """Primera ejecución: reconstruye el manifiesto a partir de los archivos
    que ya existen en data/ y absorbe los índices antiguos."""
    manifest = copy.deepcopy(_EMPTY)
    for path in sorted(MATCHES_DIR.glob("*.json")):
        rid = path.stem
        match = read_json(path)
        entry = match_entry(manifest, rid)
        entry["match_guid"] = None  # se rellena con sync --refetch
        entry["date"] = match.get("date")
        entry["ingested_at"] = None
        for stage, out_dir in (("frames", FRAMES_DIR), ("events", EVENTS_DIR)):
            if (out_dir / f"{rid}.json").exists():
                entry[stage] = {"v": 1, "ok": True, "attempts": 1, "error": None, "at": None}
        if (REPORTS_DIR / f"{rid}.md").exists():
            entry["report"] = {"path": f"reports/{rid}.md", "model": None, "generated_at": None}

    legacy_index = REPORTS_DIR / "index.json"
    if legacy_index.exists():
        idx = read_json(legacy_index)
        manifest["reports"]["team"] = [
            {"date": d, "path": f"reports/team-{d}.md", "model": None}
            for d in idx.get("team") or []
        ]
        for name, dates in (idx.get("players") or {}).items():
            manifest["reports"]["players"][name] = [
                {"date": d, "path": f"reports/player-{name}-{d}.md", "model": None}
                for d in dates
            ]
    return manifest

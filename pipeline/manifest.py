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
    team:    [{date, path, model}]                informes fechados
    players: {nombre: [{date, path, model}]}
  player_reports_state: {nombre: partidas que tenía al generar su último informe}

Las rutas son relativas a data/ (la web les antepone "data/").
Absorbe a los antiguos reports/index.json y reports/player_reports_state.json,
que se migran automáticamente la primera vez.
"""

import copy
from datetime import datetime, timezone

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
SCHEMA_VERSION = 1

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
    "player_reports_state": {},
}


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load():
    if MANIFEST_FILE.exists():
        return read_json(MANIFEST_FILE)
    return _migrate_legacy()


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
    """Apunta un informe fechado de equipo (name=None) o de jugador."""
    if name:
        items = manifest["reports"]["players"].setdefault(name, [])
    else:
        items = manifest["reports"]["team"]
    items[:] = [i for i in items if i["date"] != date]
    items.append({"date": date, "path": path, "model": model})
    items.sort(key=lambda i: i["date"])


def run_stage(stage, version, out_dir, extract, roster, compact=False, describe=None):
    """Bucle común de frames/events: (re)genera el derivado de cada partida
    cuando el manifiesto dice que toca, y registra resultado, intentos y error."""
    from pipeline.util import ARCHIVE_DIR

    manifest = load()
    done, skipped, failed = 0, 0, 0
    for match_file in sorted(MATCHES_DIR.glob("*.json")):
        replay_id = match_file.stem
        if not stage_pending(manifest, replay_id, stage, version):
            continue
        replay = ARCHIVE_DIR / f"{replay_id}.replay"
        if not replay.exists():
            skipped += 1
            continue
        try:
            payload = extract(replay, roster)
        except Exception as exc:  # un replay corrupto no debe parar el pipeline
            st = record_stage(manifest, replay_id, stage, version, ok=False, error=exc)
            reaction = "se desiste" if st["attempts"] >= MAX_ATTEMPTS else "se reintentará"
            print(f"  · {replay_id}: no se pudo parsear ({exc}) — "
                  f"intento {st['attempts']}/{MAX_ATTEMPTS}, {reaction}")
            failed += 1
            continue
        payload["id"] = replay_id
        write_json(out_dir / f"{replay_id}.json", payload, compact=compact)
        record_stage(manifest, replay_id, stage, version, ok=True)
        done += 1
        print(f"  + {stage} de {replay_id}" + (f": {describe(payload)}" if describe else ""))
    save(manifest)
    print(f"{stage}: {done} generados, {skipped} sin replay, {failed} con error")


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
    legacy_state = REPORTS_DIR / "player_reports_state.json"
    if legacy_state.exists():
        manifest["player_reports_state"] = read_json(legacy_state)
    return manifest

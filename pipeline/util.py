"""Utilidades compartidas del pipeline: rutas, configuración e identidad."""

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
MATCHES_DIR = DATA_DIR / "matches"
EVENTS_DIR = DATA_DIR / "events"
FRAMES_DIR = DATA_DIR / "frames"
PLAYERS_DIR = DATA_DIR / "players"
REPORTS_DIR = DATA_DIR / "reports"
ARCHIVE_DIR = ROOT / "replays" / "archive"
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def read_env_file(path):
    """Parsea un archivo .env (NOMBRE=valor por línea, # comenta) a un dict."""
    path = Path(path)
    values = {}
    if not path.exists():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        values[name.strip()] = value.strip().strip("'\"")
    return values


# Única fuente de claves del pipeline: el .env de la raíz (plantilla: .env.example).
SECRETS = read_env_file(ROOT / ".env")

# playlist de ballchasing -> modo que usamos en la web
_PLAYLIST_MODES = {
    "ranked-duels": "1v1",
    "unranked-duels": "1v1",
    "ranked-doubles": "2v2",
    "unranked-doubles": "2v2",
    "ranked-standard": "3v3",
    "unranked-standard": "3v3",
    "private": "privada",
    "tournament": "torneo",
}


def load_settings():
    with open(CONFIG_DIR / "settings.yml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_roster():
    """Devuelve {(platform, platform_id): nombre} a partir de players.yml."""
    with open(CONFIG_DIR / "players.yml", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    roster = {}
    for player in cfg.get("players") or []:
        for pid in player.get("ids") or []:
            roster[(str(pid["platform"]).lower(), str(pid["id"]))] = player["name"]
    return roster


def mode_from_playlist(playlist_id):
    return _PLAYLIST_MODES.get(playlist_id, playlist_id or "desconocido")


def require_secret(name):
    value = SECRETS.get(name, "").strip()
    if not value:
        raise SystemExit(f"Falta {name} en {ROOT / '.env'} (plantilla: .env.example)")
    return value


def read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, payload, compact=False):
    """Escritura atómica (tmp + rename): un corte a medias nunca deja un JSON
    corrupto que rompa load_matches(). allow_nan=False: un NaN colado (p. ej.
    de subtr-actor) debe fallar aquí, no en el JSON.parse del navegador.
    compact=True para archivos grandes (frames): sin indentación ni espacios.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fmt = {"separators": (",", ":")} if compact else {"indent": 2}
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, sort_keys=True, allow_nan=False, **fmt)
            f.write("\n")
    except BaseException:
        # sin esto, el .tmp huérfano acabaría en "git add data" y publicado
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(path)


def write_text_atomic(path, text):
    """Escritura atómica de texto (informes .md): la existencia del archivo es
    la marca de "informe hecho", así que uno truncado a medias nunca debe
    quedar en disco (no se regeneraría)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(text, encoding="utf-8")
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    tmp.replace(path)


def write_json_if_changed(path, payload, volatile=("generated_at",)):
    """Como write_json, pero no reescribe si solo cambian campos volátiles
    de primer nivel (generated_at): evita commits de "actualización
    automática" que solo tocan marcas de tiempo. Devuelve True si escribió."""
    path = Path(path)
    if path.exists():
        def _strip(doc):
            return {k: v for k, v in doc.items() if k not in volatile}
        try:
            if _strip(read_json(path)) == _strip(payload):
                return False
        except (OSError, ValueError):
            pass  # ilegible: se reescribe
    write_json(path, payload)
    return True


def load_matches():
    """Todas las partidas normalizadas, ordenadas por fecha ascendente."""
    matches = [read_json(p) for p in sorted(MATCHES_DIR.glob("*.json"))]
    matches.sort(key=lambda m: m.get("date") or "")
    return matches

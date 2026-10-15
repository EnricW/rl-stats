"""Watcher para el PC de juego (Windows): vigila la carpeta de replays de
Rocket League y sube cada .replay nuevo a ballchasing.com. Después avisa al
repositorio de GitHub (repository_dispatch) para que el pipeline procese la
partida al momento.

Requisitos en el PC: Python 3.9+ y `pip install requests`.

Configuración: un archivo `.env` junto a este script (copia `.env.example`):
  BALLCHASING_TOKEN   token de https://ballchasing.com/upload  (obligatorio)
  BALLCHASING_GROUP   id del grupo del equipo                  (obligatorio)
  RL_REPLAY_DIR       carpeta de replays (por defecto, la estándar de Windows)
  GITHUB_REPO         usuario/repositorio, p. ej. "enric/rl-stats" (opcional)
  GITHUB_PAT          token fino con permiso Contents:RW solo en ese repo (opcional)

Registro: watcher.log junto al script (rotativo). Imprescindible porque el
arranque recomendado es pythonw.exe, que no tiene consola.

Ver watcher/README.md para dejarlo arrancando con Windows.
"""

import json
import logging
import sys
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

import requests

POLL_SECONDS = 30
VISIBILITY = "unlisted"

log = logging.getLogger("watcher")


def setup_logging():
    log.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S")
    file_handler = RotatingFileHandler(
        Path(__file__).with_name("watcher.log"),
        maxBytes=512_000, backupCount=2, encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    log.addHandler(file_handler)
    console = logging.StreamHandler()
    console.setFormatter(fmt)
    log.addHandler(console)


def read_env_file(path):
    """Parsea un archivo .env (NOMBRE=valor por línea, # comenta) a un dict."""
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


CONFIG = read_env_file(Path(__file__).with_name(".env"))

TOKEN = CONFIG.get("BALLCHASING_TOKEN", "")
GROUP = CONFIG.get("BALLCHASING_GROUP", "")
GITHUB_REPO = CONFIG.get("GITHUB_REPO", "")
GITHUB_PAT = CONFIG.get("GITHUB_PAT", "")
REPLAY_DIR = Path(
    CONFIG.get("RL_REPLAY_DIR")
    or Path.home() / "Documents" / "My Games" / "Rocket League" / "TAGame" / "Demos"
)
# Nombres de replay ya tratados (subidos o con error permanente): no se tocan más.
STATE_FILE = Path(__file__).with_name("uploaded.json")
# Marca persistente de "hay un aviso a GitHub pendiente": si notify falla (o el
# PC se apaga justo después de subir), se reintenta en cada pasada hasta llegar.
NOTIFY_FLAG = Path(__file__).with_name("pending_notify")


def load_state():
    """Devuelve (nombres ya tratados, es_primer_arranque).

    Un estado corrupto NUNCA puede significar "no hay nada subido": sin esta
    protección, un uploaded.json ilegible haría resubir la carpeta Demos
    entera (años de replays ajenos al equipo) al grupo.
    """
    if not STATE_FILE.exists():
        return set(), True
    try:
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8"))), False
    except (ValueError, OSError) as exc:
        bak = STATE_FILE.with_name("uploaded.json.bak")
        try:
            STATE_FILE.replace(bak)
        except OSError:
            pass
        log.warning(
            "uploaded.json ilegible (%s): guardado como %s y se re-aplica la "
            "protección de primer arranque", exc, bak.name,
        )
        return set(), True


def save_state(state):
    # atómico (tmp + replace): un corte a medias no deja el estado corrupto
    tmp = STATE_FILE.with_name("uploaded.json.tmp")
    tmp.write_text(json.dumps(sorted(state), indent=1), encoding="utf-8")
    tmp.replace(STATE_FILE)


def file_is_stable(path):
    """Evita subir un replay que el juego aún está escribiendo."""
    size = path.stat().st_size
    time.sleep(2)
    return path.stat().st_size == size and size > 0


def upload(path):
    """Sube un replay. Devuelve:
    - "ok":    subido (o ya existía en ballchasing); no volver a tocarlo.
    - "fail":  error permanente (4xx: replay corrupto, token inválido…);
               reintentarlo cada 30 s sería inútil, se apunta y no se toca más.
    - "retry": error transitorio (429/5xx/red); se reintenta en otra pasada.
    """
    with open(path, "rb") as f:
        resp = requests.post(
            "https://ballchasing.com/api/v2/upload",
            headers={"Authorization": TOKEN},
            params={"visibility": VISIBILITY, "group": GROUP},
            files={"file": f},
            timeout=120,
        )
    if resp.status_code in (201, 409):  # creado o duplicado: ambos valen
        replay_id = resp.json().get("id", "?")
        log.info("%s -> https://ballchasing.com/replay/%s", path.name, replay_id)
        return "ok"
    if resp.status_code == 429 or resp.status_code >= 500:
        retry_after = min(int(resp.headers.get("Retry-After") or 0), 300)
        log.warning("%s: HTTP %s, se reintentará", path.name, resp.status_code)
        if retry_after:
            time.sleep(retry_after)
        return "retry"
    # 4xx permanente: con 401/403 conviene gritar más (token caducado afecta a todo)
    if resp.status_code in (401, 403):
        log.error("HTTP %s de ballchasing: revisa BALLCHASING_TOKEN en el .env", resp.status_code)
        return "retry"  # no es culpa del replay: al arreglar el token, se subirá
    log.error(
        "%s: HTTP %s %s — error permanente, no se reintentará",
        path.name, resp.status_code, resp.text[:200],
    )
    return "fail"


def notify_github():
    """Avisa al pipeline. True si el aviso llegó (o no hay nada configurado)."""
    if not (GITHUB_REPO and GITHUB_PAT):
        return True
    try:
        resp = requests.post(
            f"https://api.github.com/repos/{GITHUB_REPO}/dispatches",
            headers={
                "Authorization": f"Bearer {GITHUB_PAT}",
                "Accept": "application/vnd.github+json",
            },
            json={"event_type": "new-replay"},
            timeout=30,
        )
        if resp.status_code == 204:
            log.info("pipeline de GitHub avisado")
            return True
        # PAT caducado, repo mal escrito… que no pase en silencio
        log.warning(
            "GitHub respondió HTTP %s (se reintentará; si persiste, revisa el "
            "PAT; mientras tanto el cron del lunes recoge las partidas)",
            resp.status_code,
        )
        return False
    except requests.RequestException as exc:
        log.warning("no se pudo avisar a GitHub (se reintentará): %s", exc)
        return False


def main():
    setup_logging()
    if not TOKEN or not GROUP:
        sys.exit(
            "Rellena BALLCHASING_TOKEN y BALLCHASING_GROUP en el .env junto a "
            "watcher.py (copia .env.example)"
        )
    if not REPLAY_DIR.is_dir():
        sys.exit(f"No existe la carpeta de replays: {REPLAY_DIR}")

    uploaded, first_run = load_state()

    # Primer arranque: los replays que ya hubiera en la carpeta se marcan como
    # vistos y NO se suben (podrían ser años de partidas ajenas al equipo).
    # Para subir también el historial existente: python watcher.py --backfill
    if first_run and "--backfill" not in sys.argv[1:]:
        existing = {p.name for p in REPLAY_DIR.glob("*.replay")}
        uploaded |= existing
        save_state(uploaded)
        if existing:
            log.info(
                "primer arranque: %d replays ya existentes ignorados "
                "(usa --backfill para subirlos también)", len(existing),
            )

    log.info("Vigilando %s (%d replays ya tratados)", REPLAY_DIR, len(uploaded))
    while True:
        pending = [
            p for p in REPLAY_DIR.glob("*.replay") if p.name not in uploaded
        ]
        any_uploaded = False
        for path in sorted(pending):
            try:
                if not file_is_stable(path):
                    continue  # aún se está escribiendo; siguiente pasada
                outcome = upload(path)
                if outcome == "ok":
                    uploaded.add(path.name)
                    save_state(uploaded)
                    any_uploaded = True
                elif outcome == "fail":
                    # permanente: se apunta como tratado para no insistir
                    uploaded.add(path.name)
                    save_state(uploaded)
            except requests.RequestException as exc:
                log.warning("sin conexión con ballchasing, reintento luego: %s", exc)
                break
            except Exception:  # un replay raro no debe tumbar el demonio
                log.exception("%s: error inesperado; se reintentará", path.name)
        if any_uploaded:
            NOTIFY_FLAG.touch()
        if NOTIFY_FLAG.exists() and notify_github():
            NOTIFY_FLAG.unlink()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()

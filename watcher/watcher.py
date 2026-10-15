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

Ver watcher/README.md para dejarlo arrancando con Windows.
"""

import json
import sys
import time
from pathlib import Path

import requests

POLL_SECONDS = 30
VISIBILITY = "unlisted"


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
STATE_FILE = Path(__file__).with_name("uploaded.json")


def load_state():
    if STATE_FILE.exists():
        try:
            return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
        except (ValueError, OSError) as exc:
            print(f"[aviso] uploaded.json ilegible, se empieza de cero: {exc}")
    return set()


def save_state(state):
    STATE_FILE.write_text(json.dumps(sorted(state), indent=1), encoding="utf-8")


def file_is_stable(path):
    """Evita subir un replay que el juego aún está escribiendo."""
    size = path.stat().st_size
    time.sleep(2)
    return path.stat().st_size == size and size > 0


def upload(path):
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
        print(f"[ok] {path.name} -> https://ballchasing.com/replay/{replay_id}")
        return True
    print(f"[error] {path.name}: HTTP {resp.status_code} {resp.text[:200]}")
    return False


def notify_github():
    if not (GITHUB_REPO and GITHUB_PAT):
        return
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
            print("[ok] pipeline de GitHub avisado")
        else:  # PAT caducado, repo mal escrito… que no pase en silencio
            print(f"[aviso] GitHub respondió HTTP {resp.status_code} (el cron lo recogerá)")
    except requests.RequestException as exc:
        print(f"[aviso] no se pudo avisar a GitHub (el cron lo recogerá): {exc}")


def main():
    if not TOKEN or not GROUP:
        sys.exit(
            "Rellena BALLCHASING_TOKEN y BALLCHASING_GROUP en el .env junto a "
            "watcher.py (copia .env.example)"
        )
    if not REPLAY_DIR.is_dir():
        sys.exit(f"No existe la carpeta de replays: {REPLAY_DIR}")

    uploaded = load_state()

    # Primer arranque: los replays que ya hubiera en la carpeta se marcan como
    # vistos y NO se suben (podrían ser años de partidas ajenas al equipo).
    # Para subir también el historial existente: python watcher.py --backfill
    if not STATE_FILE.exists() and "--backfill" not in sys.argv[1:]:
        existing = {p.name for p in REPLAY_DIR.glob("*.replay")}
        if existing:
            uploaded |= existing
            save_state(uploaded)
            print(
                f"[aviso] primer arranque: {len(existing)} replays ya existentes "
                "ignorados (usa --backfill para subirlos también)"
            )

    print(f"Vigilando {REPLAY_DIR} ({len(uploaded)} replays ya subidos)")
    while True:
        pending = [
            p for p in REPLAY_DIR.glob("*.replay") if p.name not in uploaded
        ]
        any_uploaded = False
        for path in sorted(pending):
            try:
                if not file_is_stable(path):
                    continue  # aún se está escribiendo; siguiente pasada
                if upload(path):
                    uploaded.add(path.name)
                    save_state(uploaded)
                    any_uploaded = True
            except requests.RequestException as exc:
                print(f"[aviso] sin conexión con ballchasing, reintento luego: {exc}")
                break
            except Exception as exc:  # un replay raro no debe tumbar el demonio
                print(f"[aviso] {path.name}: {exc}; se reintentará")
        if any_uploaded:
            notify_github()
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()

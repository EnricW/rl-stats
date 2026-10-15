"""Sube a ballchasing los .replay dejados a mano en replays/inbox/ y los borra
(el pipeline los re-descargará a replays/archive/ con su id canónico).

Uso: python -m pipeline.upload_inbox
(requiere BALLCHASING_TOKEN en el .env de la raíz)
"""

from pipeline.ballchasing import BallchasingClient
from pipeline.util import ROOT, load_settings, require_secret

INBOX = ROOT / "replays" / "inbox"


def main():
    settings = load_settings()["ballchasing"]
    if not settings.get("group"):
        raise SystemExit("Configura ballchasing.group en config/settings.yml")
    client = BallchasingClient(require_secret("BALLCHASING_TOKEN"))

    replays = sorted(INBOX.glob("*.replay"))
    for path in replays:
        replay_id, existed = client.upload(
            path,
            visibility=settings.get("visibility", "unlisted"),
            group=settings["group"],
        )
        print(f"  {path.name} -> {replay_id}{' (ya existía)' if existed else ''}")
        path.unlink()
    print(f"upload_inbox: {len(replays)} replays subidos")


if __name__ == "__main__":
    main()

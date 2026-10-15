"""Cliente mínimo de la API de ballchasing.com (https://ballchasing.com/doc/api).

Respeta los límites del tier gratuito: espacia las llamadas y reintenta con
backoff ante HTTP 429.
"""

import time

import requests

API = "https://ballchasing.com/api"


class BallchasingError(RuntimeError):
    pass


class BallchasingClient:
    def __init__(self, token, min_interval=0.6, max_retries=5):
        self.session = requests.Session()
        self.session.headers["Authorization"] = token
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._last_call = 0.0

    def _request(self, method, url, **kwargs):
        for attempt in range(self.max_retries + 1):
            # Un reintento con `files` debe reenviar el archivo desde el
            # principio: si no, el segundo POST sube un archivo vacío.
            for f in (kwargs.get("files") or {}).values():
                f.seek(0)
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            try:
                resp = self.session.request(method, url, timeout=60, **kwargs)
            except requests.RequestException as exc:
                self._last_call = time.monotonic()
                if attempt == self.max_retries:
                    raise BallchasingError(f"Error de red persistente en {url}: {exc}") from exc
                time.sleep(min(2 ** attempt, 60))
                continue
            self._last_call = time.monotonic()
            if resp.status_code != 429 and resp.status_code not in (500, 502, 503, 504):
                return resp
            try:
                retry_after = float(resp.headers.get("Retry-After") or 2 ** attempt)
            except ValueError:  # Retry-After en formato fecha HTTP
                retry_after = 2 ** attempt
            time.sleep(min(retry_after, 60))
        raise BallchasingError(f"Rate limit o error persistente en {url}")

    def ping(self):
        resp = self._request("GET", API)
        resp.raise_for_status()
        return resp.json()

    def iter_group_replays(self, group_id):
        """Itera los replays de un grupo (listado básico, sin stats completas)."""
        url = f"{API}/replays"
        params = {"group": group_id, "count": 200, "sort-by": "replay-date", "sort-dir": "asc"}
        while url:
            resp = self._request("GET", url, params=params)
            resp.raise_for_status()
            payload = resp.json()
            yield from payload.get("list") or []
            url = payload.get("next")
            params = None  # "next" ya lleva los parámetros

    def get_replay(self, replay_id):
        """Stats completas de un replay (bloques core/boost/movement/positioning/demo)."""
        resp = self._request("GET", f"{API}/replays/{replay_id}")
        resp.raise_for_status()
        return resp.json()

    def download_replay(self, replay_id, dest_path):
        resp = self._request("GET", f"{API}/replays/{replay_id}/file")
        resp.raise_for_status()
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        dest_path.write_bytes(resp.content)

    def upload(self, file_path, visibility="unlisted", group=None):
        """Sube un .replay. Devuelve (id, ya_existia)."""
        params = {"visibility": visibility}
        if group:
            params["group"] = group
        with open(file_path, "rb") as f:
            resp = self._request(
                "POST", f"{API}/v2/upload", params=params, files={"file": f}
            )
        if resp.status_code == 201:
            return resp.json()["id"], False
        if resp.status_code == 409:  # duplicado: ballchasing ya lo tiene
            return resp.json()["id"], True
        raise BallchasingError(f"Subida fallida ({resp.status_code}): {resp.text[:300]}")

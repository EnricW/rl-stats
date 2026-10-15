# RL Stats — estadísticas del equipo de Rocket League

Web estática con las estadísticas e informes de coach (IA) del equipo, generada
automáticamente: juegas una partida, el watcher del PC sube el replay a
ballchasing.com y GitHub Actions actualiza la web en unos minutos.

## Cómo funciona

```
PC de juego ── watcher.py ──> ballchasing.com (grupo del equipo, replays unlisted)
                                   │
GitHub Actions (ingest.yml) <──────┘  repository_dispatch + cron cada 6 h
  sync          stats completas de la API -> data/matches/<id>.json
                .replay original -> replays/archive/ (solo en el runner, no se versiona)
  frames        trayectorias del .replay (subtr-actor) -> data/frames/<id>.json
                (alimenta el visor 3D/2D, la cronología y el mapa de calor)
  events        tiros/paradas, kickoffs, rotación y posesión -> data/events/<id>.json
  aggregate     data/players/<nombre>.json + data/summary.json
  report        informes con la API de Claude -> data/reports/
  aggregate     segunda pasada: el índice refleja los informes recién creados
  deploy        site/ + data/ -> GitHub Pages
```

Las stats agregadas las calcula ballchasing (aquí solo se normalizan y comentan);
los `.replay` archivados se parsean con [subtr-actor](https://github.com/rlrml/subtr-actor)
para extraer trayectorias (visor) y eventos con timestamp (cronología, saques,
rotación), que también alimentan los informes IA.

## Puesta en marcha

1. **ballchasing**: crea tu token en [ballchasing.com/upload](https://ballchasing.com/upload)
   y un grupo para el equipo; apunta el id del grupo en `config/settings.yml`.
2. **Identidad**: rellena `config/players.yml` con los IDs de plataforma de cada
   miembro (se ven en el perfil de cada jugador en ballchasing).
3. **Watcher**: instala `watcher/` en el PC de juego → ver `watcher/README.md`.
4. **Secrets del repo** (Settings → Secrets and variables → Actions):
   `BALLCHASING_TOKEN` y `ANTHROPIC_API_KEY`.
5. **GitHub Pages**: Settings → Pages → Source: *GitHub Actions*.

Vía manual de respaldo: arrastra un `.replay` a `replays/inbox/` desde github.com
(*Add file → Upload files*) y el pipeline lo sube y procesa solo.

## Ejecutar en local

```bash
pip install -r requirements.txt
cp .env.example .env           # y rellena BALLCHASING_TOKEN (y ANTHROPIC_API_KEY para informes)
python -m pipeline.sync
python -m pipeline.frames            # trayectorias para el visor
python -m pipeline.events            # tiros, kickoffs, rotación, posesión
python -m pipeline.aggregate
python -m pipeline.report            # informes pendientes
python -m pipeline.report --team     # informe de equipo
```

Para ver la web en local con los datos, sirve una carpeta que contenga `site/` y
`data/` juntos (igual que hace el deploy):

```bash
mkdir -p /tmp/_site && cp -r site/* /tmp/_site/ && cp -r data /tmp/_site/data
python -m http.server -d /tmp/_site 8000
```

## Tests y lint

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

CI (`.github/workflows/ci.yml`) ejecuta ambos en cada push a `main` y en PRs.

## Privacidad

Este repo es **público** y la web también, así que todo lo que hay en `data/` y
`replays/` queda publicado. Qué se publica y qué no:

- Los replays se suben a ballchasing como `unlisted`, y su URL **no** se incluye
  en los JSON de la web.
- De los rivales solo se publican su nick en partida y sus stats; sus IDs de
  plataforma **no** se publican. De los miembros del equipo se publica lo que ya
  consta en `config/players.yml` (nombre elegido e IDs de plataforma): usa nicks
  ahí si no quieres nombres reales.
- Los `.replay` originales **no** se versionan en el repo (contienen los nicks
  e IDs de todos los jugadores de cada partida): el almacén es ballchasing, el
  pipeline los descarga al vuelo cuando necesita parsearlos, y las copias
  locales de `replays/archive/` están en `.gitignore`.

Si el equipo prefiere datos totalmente privados: repo privado + Cloudflare
Pages (gratis) en lugar de GitHub Pages.

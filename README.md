# RL Stats — estadísticas del equipo de Rocket League

Web estática con las estadísticas e informes de coach (IA) del equipo, generada
automáticamente: juegas una partida, el watcher del PC sube el replay a
ballchasing.com y GitHub Actions actualiza la web en unos minutos.

## Cómo funciona

```
PC de juego ── watcher.py ──> ballchasing.com (grupo del equipo, replays unlisted)
                                   │
GitHub Actions (ingest.yml) <──────┘  repository_dispatch + cron (03:23 y 07:41)
  sync          stats completas de la API -> data/matches/<id>.json
                .replay original -> replays/archive/ (solo en el runner, no se versiona)
  derive        parsea el .replay una vez (subtr-actor) y genera:
                  frames: trayectorias -> data/frames/<id>.json
                          (visor 3D/2D, cronología y mapa de calor)
                  events: tiros/paradas, kickoffs, rotación -> data/events/<id>.json
  aggregate     data/players/<nombre>.json + data/summary.json
  report        informes con la API de Claude -> data/reports/
                  por partida; por jugador tras cada sesión de juego (una
                  noche de partidas); de equipo cada 7 días
  aggregate     segunda pasada: el índice refleja los informes recién creados
  deploy        site/ + data/ -> GitHub Pages
```

El estado del pipeline vive en `data/manifest.json` (registro central): qué
partidas se ingirieron (con dedup por `match_guid`), el estado de cada derivado
(versión del extractor, intentos y último error: un replay corrupto se reintenta
3 veces y se desiste), y el histórico de informes con fecha, ruta y modelo.

Las **sesiones de juego** (`pipeline/sessions.py`) agrupan las partidas en las
noches en que se jugaron: partidas consecutivas separadas por menos de
`session_gap_hours`, aunque la tanda cruce la medianoche. Cada sesión cerrada
genera un informe de tendencia por jugador (`player-<nombre>-<id-sesión>.md`),
que la web etiqueta como "14 oct · 13 partidas". Mientras la sesión está en
curso no se genera nada, así que los avisos del watcher durante la noche no
disparan informes a medias.
La web no adivina rutas: lee la vista que `aggregate` publica en `summary.json`.

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

Vía manual de respaldo (si el watcher no está disponible): sube el `.replay` en
[ballchasing.com/upload](https://ballchasing.com/upload) al grupo del equipo (o
cópialo a `replays/inbox/` y ejecuta `python -m pipeline.upload_inbox` en local)
y lanza el workflow *Procesar partidas* desde la pestaña Actions. **Nunca subas
un `.replay` por commit**: quedaría para siempre en el historial público con los
IDs de los 6 jugadores.

## Ejecutar en local

```bash
pip install -r requirements.txt
cp .env.example .env           # y rellena BALLCHASING_TOKEN (y ANTHROPIC_API_KEY para informes)
python -m pipeline.sync
python -m pipeline.derive            # trayectorias del visor + eventos (parseo único)
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
- En los JSON de la web **no se publica ningún ID de plataforma**, ni de rivales
  ni del roster: de los rivales solo aparecen su nick en partida y sus stats; de
  los miembros del equipo, el nombre elegido en `config/players.yml` (usa nicks
  ahí si no quieres nombres reales; ten en cuenta que `players.yml` sí contiene
  los IDs y es público).
- Los `.replay` originales **no** se versionan en el repo (contienen los nicks
  e IDs de todos los jugadores de cada partida): el almacén es ballchasing, el
  pipeline los descarga al vuelo cuando necesita parsearlos, y las copias
  locales de `replays/archive/` están en `.gitignore`.

Si el equipo prefiere datos totalmente privados: repo privado + Cloudflare
Pages (gratis) en lugar de GitHub Pages.

# Watcher del PC de juego

Sube automáticamente cada replay nuevo a ballchasing.com y avisa al pipeline.
Se instala una vez en el PC de Windows donde corre Rocket League.

## Instalación

1. Instala [Python para Windows](https://www.python.org/downloads/) (marca "Add to PATH") y luego, en una terminal:
   ```
   pip install requests
   ```
2. Copia la carpeta `watcher/` a algún sitio del PC, p. ej. `C:\rl-watcher\`.
3. En esa carpeta, copia `.env.example` a `.env` y rellénalo:
   - `BALLCHASING_TOKEN`: tu token de https://ballchasing.com/upload
   - `BALLCHASING_GROUP`: el id del grupo del equipo (lo que va tras `/group/` en su URL)
   - Opcionales, para que la web se actualice al momento (sin ellos, el cron
     del lunes recoge las partidas de la semana):
     - `GITHUB_REPO`: `tuusuario/rl-stats`
     - `GITHUB_PAT`: token *fine-grained* creado en GitHub → Settings → Developer settings,
       con acceso SOLO a ese repositorio y permiso **Contents: Read and write**
       (repository_dispatch requiere ese permiso).

       ⚠️ Ese permiso también deja hacer *push* al repo: quien robe el PAT del PC
       podría alterar `pipeline/` (que CI ejecuta con los secrets). Guarda el PAT
       solo en ese `.env` y revócalo si el PC se ve comprometido. Alternativa de
       menor alcance: un workflow con `workflow_dispatch` y un PAT con solo
       **Actions: Read and write**.
4. Prueba en una terminal: `python C:\rl-watcher\watcher.py`
   Debe decir `Vigilando ...`. En el primer arranque, los replays que ya hubiera
   en la carpeta se marcan como vistos y **no** se suben (podrían ser años de
   partidas ajenas al equipo); para subir también el historial:
   `python watcher.py --backfill`.

## Arrancar con Windows

Programador de tareas (`taskschd.msc`) → "Crear tarea básica":

- Desencadenador: **Al iniciar sesión**.
- Acción: iniciar programa `pythonw.exe` con argumento `C:\rl-watcher\watcher.py`
  (`pythonw` lo deja corriendo sin ventana).

En Propiedades de la tarea, activa "Ejecutar la tarea lo antes posible después
de un inicio programado perdido".

## Notas

- El watcher escribe su registro en `watcher.log` (junto al script, rotativo):
  es el sitio donde mirar si algo no sube, porque `pythonw` no tiene consola.
- El fichero `uploaded.json` (junto al script) recuerda qué replays ya se
  trataron (subidos, o con error permanente que no tiene sentido reintentar);
  bórralo solo si quieres resubirlo todo (ballchasing deduplica, no pasa nada grave).
- Si el PC está sin conexión, o falla el aviso a GitHub, el watcher lo
  reintenta en cada pasada (el aviso pendiente se recuerda en `pending_notify`,
  incluso entre reinicios); en el peor caso, el cron del lunes recoge las
  partidas de la semana.
- Si un día no quieres subir una partida, borra su `.replay` de la carpeta Demos
  antes de que el watcher la detecte (ventana de ~30 s) o para la tarea antes de jugar.

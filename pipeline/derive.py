"""Genera los dos derivados del replay (frames y events) en una sola pasada.

El parseo del .replay con subtr-actor es el paso más caro del pipeline y
get_replay_frames_data lo necesitan los dos extractores: aquí se parsea una
vez por partida y se comparte, en lugar de ejecutar frames y events por
separado (que lo parseaban dos veces).

Uso: python -m pipeline.derive
(frames y events siguen siendo ejecutables por separado si hace falta)
"""

import subtr_actor

from pipeline import events, frames
from pipeline.manifest import run_stages
from pipeline.util import load_roster


def main():
    run_stages([frames.SPEC, events.SPEC], load_roster(), subtr_actor.get_replay_frames_data)


if __name__ == "__main__":
    main()

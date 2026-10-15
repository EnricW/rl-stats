"""Pipeline de rl-stats: sync -> frames/events -> aggregate -> report.

Cada módulo se ejecuta como script con `python -m pipeline.<módulo>` desde la
raíz del repo; se comunican solo a través de los archivos de data/.
"""

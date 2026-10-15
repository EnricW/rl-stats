# Informe de tendencia: Eric

## 1. Foto actual
Eric ha jugado **10 partidas, todas en 3v3**, con **4 victorias (40 % de winrate)**. Su perfil es el de un jugador **muy posicional y poco finalizador**: promedia 0,5 goles, 0,2 asistencias y 1,8 tiros por partido, con un 28,33 % de acierto. Juega mucho en campo propio (54,15 % en el tercio defensivo, solo 17,41 % en el ofensivo). Por ahora está **irregular, con una ligera mejoría en resultados**. Gana 3 de las últimas 5 partidas, frente a 1 de las 5 primeras.

## 2. Tendencias
Aquí hay una limitación: **`last10_averages` es idéntico a `averages`**, porque solo hay 10 partidas. No se puede hacer la comparación habitual de forma y media histórica. Como alternativa, comparo las **5 primeras partidas con las 5 últimas**. Son muestras muy pequeñas, así que tómalo como orientación y no como conclusión firme.

- **Tercio defensivo:** pasa de ~52,0 % a ~56,3 %. En paralelo, el ofensivo baja de ~18,7 % a ~16,1 %. Cada vez juega más atrás.
- **Score medio:** sube de ~229 a ~273, aunque los goles no acompañan: ~0,6 en las 5 primeras y ~0,4 en las 5 últimas. Los tiros bajan de 2,2 a 1,4 por partido. Suma puntos por defensa y presencia (paradas: 0,8 → 1,2), no por finalización.
- **Boost a cero:** baja de ~12,0 % a ~10,2 %. Es una mejora leve en gestión, aunque oscila mucho entre partidas (de 4,99 % a 16,19 %).

Un dato aparte: la distancia media a compañeros se dispara en las dos últimas partidas (4010 y 3888, frente a ~3050-3550 en el resto). Puede ser una señal de desconexión con el equipo.

## 3. Fortalezas consolidadas
- **Buen posicionamiento respecto al balón:** `pct_behind_ball` de 73,15 %, siempre entre 67,9 % y 78,6 %. Rara vez se deja superar.
- **Rotación equilibrada:** primer hombre 29,34 %, tercer hombre 30,62 %, último atrás 36,18 % y más adelantado 32,09 %. No se queda clavado en un rol.
- **Economía de boost correcta:** recoge 310 de bcpm y gasta 298 de bpm, con un boost medio de 48,38. Además roba 209,6 de boost por partida.
- **Juego mayoritariamente a ras de suelo:** 68,58 % en suelo y 29,66 % en aire bajo. Es un estilo estable y poco arriesgado (aire alto: 1,77 %).

## 4. Plan de práctica
1. **Saques (`kickoff_ft_pct` 24,07 %):** en muchas partidas tiene un 0 % de primeros toques en saques. Dedica 10 minutos de calentamiento a saques desde cada posición (diagonal, lateral y centro). Fija una decisión previa: ir a por la bola o cubrir de forma explícita. Mide cuántos primeros toques consigues sobre 20 saques.
2. **Finalización (1,8 tiros por partido, 28,33 % de acierto):** en entrenamiento libre o con packs de tiros, practica 15 minutos de remates tras recibir un pase o tras un rebote. Fíjate el objetivo de llegar a 3 tiros por partido, con intención de tirar al tercio ofensivo cuando recuperes y no solo despejar. Hoy el 54 % del tiempo en tu campo limita tus opciones.
3. **Boost y cercanía al equipo (`pct_zero_boost` 11,09 %, `boost_overfill` 282, `avg_dist_to_mates` de 3481,9):** haz rutina de recogida de pads pequeños durante la rotación, sin pisar pads grandes con más del 80 % de boost. Así bajas el desperdicio y el tiempo a cero. Apunta a quedarte siempre por debajo del 10 % a cero (ya lo logras en 4 de las 10 partidas). En las partidas, fija una referencia: mantente a una distancia de pase de tus compañeros, sobre todo al subir tras defender. Es el hábito que deberías vigilar tras las dos últimas partidas.

**Siguiente paso:** acumula 10 partidas más. Entonces `last10_averages` ya será comparable con la media histórica y podremos confirmar si estas tendencias se sostienen.

---
*Informe generado por claude-sonnet-5-5 el 2026-10-15 04:44 UTC.*

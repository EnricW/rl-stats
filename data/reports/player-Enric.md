# Informe de tendencia: Enric

## 1. Foto actual
Solo hay datos de **3v3**, con 10 partidas y un **winrate del 40 %** (4 victorias). El nivel es discreto, con poca producción ofensiva: 0,3 goles, 0,2 asistencias y 0,7 tiros por partido, con un score medio de 159,3. La fase es de **mejora tímida**: en las 5 primeras partidas ganó 1 y en las 5 últimas ganó 3, y el score medio pasa de ~118 a ~201. Con tan pocas partidas es una señal, no una certeza.

## 2. Tendencias
Con solo 10 partidas, `last10_averages` y `averages` son **idénticos**, así que no se puede comparar entre ellos. En su lugar he dividido el historial en las 5 primeras partidas y las 5 últimas (cálculo mío con los datos del JSON):

| Métrica | Primeras 5 | Últimas 5 |
|---|---|---|
| Score | ~117,6 | ~201,0 |
| Goles totales | 0 | 3 |
| % boost a cero | ~15,6 % | ~11,9 % |
| Boost recogido por minuto | ~243,8 | ~271,0 |
| % supersónico | ~3,2 % | ~4,1 % |
| % más atrás | ~32,5 % | ~37,9 % |
| % tercio ofensivo | ~19,3 % | ~14,7 % |
| Distancia a compañeros | ~3.415 | ~3.713 |

- **Más producción y mejor boost:** sube el score, aparecen los goles y recoge más boost con menos tiempo a cero.
- **Se ha vuelto más defensivo:** pasa más tiempo como último hombre y menos en el tercio ofensivo (de ~19 % a ~15 %).
- **Más separación del equipo:** en las dos últimas partidas la distancia a compañeros sube a 4.075 y 4.160, frente a una media de 3.564.

## 3. Fortalezas consolidadas
- **Estar por detrás del balón:** 70,5 % de media, y nunca baja del 63,9 % en ninguna partida. Es una base de posicionamiento sólida.
- **Gestión de boost:** `avg_boost` de 50,5, 13,8 % del tiempo a cero y 257 de boost recogido por minuto. Roba un promedio de 210 de boost por partida.
- **Saques:** 44 % de primeros toques de media. Tras dos partidas con 0 %, nunca baja del 33 % en las partidas con dato, y llega a 100 % y 66,7 % en las partidas 8 y 9.
- **Rotación equilibrada:** reparte el tiempo entre primer hombre (24,9 %) y tercer hombre (34,2 %) sin obsesionarse con ninguno.

## 4. Plan de práctica
1. **Convertir las llegadas en tiros.** Solo hay 7 tiros en 10 partidas y el tercio ofensivo apenas ocupa el 17 % del tiempo. Haz series de 10 min en entrenamiento libre o con packs de tiro a puerta, y en partida ponte el objetivo de 2-3 tiros por partido. Subir los tiros es lo que más puede mover el winrate.
2. **Revisar la posición del último hombre.** Encajó 7 goles siendo el último defensor, en las 5 partidas donde aparece ese dato, y pasa un 35 % del tiempo como el más atrás. Practica rotar tras el ataque y no quedarte atrás por inercia. Pide a un compañero en la partida que avise cuando cubras tú. Revisa en replay los goles encajados como último defensor y mira si salías tarde o llegabas sin cobertura.
3. **Mantener la cercanía al equipo y el boost.** La distancia a compañeros sube en las últimas partidas, hasta 4.160. Haz rotaciones en 3v3 amistosos con el objetivo de quedar a distancia de pase de los compañeros. Al mismo tiempo, reduce el `boost_overfill` (259,9 de media, con picos de 419 y 414) pasando a pads pequeños cuando el depósito está por encima de ~70 %, y conserva el `pct_zero_boost` por debajo del 12 % de las últimas 5 partidas.

**Nota:** con 10 partidas y un solo modo, las conclusiones son orientativas. Conviene volver a revisar este informe cuando haya 20 o más.

---
*Informe generado por claude-sonnet-5-5 el 2026-10-15 04:44 UTC.*

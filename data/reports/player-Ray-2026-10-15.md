# Informe de tendencia: Ray

## 1. Foto actual
Ray solo tiene datos en **3v3**, con 10 partidas y **4 victorias (40 % de winrate)**. Es una muestra pequeña, así que las conclusiones son orientativas. Es un jugador de producción media (1,1 goles, 3,0 tiros y 1,4 paradas por partido, con 375 de score medio). Su fase es **irregular**, pero con una señal curiosa: ganó 1 de las primeras 5 partidas y 3 de las últimas 5, aunque sus números individuales bajaron. No hay datos de rango, así que no puedo contextualizar la evolución con él.

## 2. Tendencias
Como tiene exactamente 10 partidas, `last10_averages` es idéntico a `averages` y no sirve para comparar. Para ver evolución he dividido el historial en **primeras 5 vs últimas 5 partidas** (cálculos míos a partir del JSON):

- **Tiros: 4,4 → 1,6 por partido.** Es el cambio más grande. En las últimas 5 hubo partidas con 0, 1 y 2 tiros, y el score cae de ~435 a ~316.
- **Velocidad supersónica: 6,1 % → 9,0 %.** Juega más rápido, sobre todo en las partidas 8 y 9 (12,5 % y 12,7 %). Esa velocidad no se está convirtiendo en más remates.
- **Tiempo a 0 de boost: 5,8 % → 7,8 %.** Se queda sin boost más a menudo, con picos de 13,9 % y 9,6 % en las partidas 7 y 8. Va ligado a jugar más rápido sin reponer.

Otros datos: el % de tiempo como último hombre bajó de 32,2 % a 27,4 %, y los goles se mantienen (1,2 → 1,0). Los resultados mejoran porque ganó 3 de las últimas 5, aunque la producción individual baja.

## 3. Fortalezas consolidadas
- **Impacto en las victorias:** las 4 victorias fueron también las 4 partidas en que fue MVP.
- **Buen posicionamiento defensivo:** 74,9 % del tiempo por detrás de la pelota y 51 % en el tercio defensivo.
- **Rotación equilibrada:** primer hombre 33,1 % y tercer hombre 22,5 %. No se queda pegado a una posición.
- **Gestión de boost sólida en general:** recoge más de lo que gasta (264,8 de bcpm frente a 252 de bpm) y roba 262 de boost por partido.
- **Eficiencia de remate:** 41,25 % de shooting con 1,1 goles sobre 3 tiros. Cuando dispara, acierta.
- **Saques:** 52,8 % de primeros toques (partida 9 sin dato), con picos de 100 % en 4 de 9 partidas.

## 4. Plan de práctica
1. **Recuperar el volumen de tiros.** Pasó de 4,4 a 1,6 tiros por partido sin perder precisión, así que el problema es crear ocasiones, no acertar. Haz series de 10 min de entrenamiento libre de remates tras un pase al espacio, y en partida exígete 3 tiros mínimo antes de pensar en el siguiente objetivo.
2. **Rutina de pads pequeños para bajar el tiempo a 0 de boost** (7,8 % en las últimas 5, hasta 13,9 % en una partida). Cuando bajes del 25 % de boost, rota por los pads pequeños de tu lado en vez de buscar el siguiente balón. Revisa si la velocidad supersónica (9 %) vale lo que cuesta en boost.
3. **Revisar las situaciones de último defensor.** Encaja 1,5 goles por partida siendo el último hombre, con un pico de 4 en la partida 8. Haz repeticiones de defensa en 1v1 y 2v2 en workshop o entrenamiento. Al volver a rotar, comprueba que tu compañero cubre antes de subir. Así no te quedas expuesto cuando pierdes la posición de último hombre.

---
*Informe generado por claude-sonnet-5-5 el 2026-10-15 04:45 UTC.*

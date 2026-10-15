/* Ficha de jugadores: radar comparado, pestañas, evolución, comparativa,
   totales e informe de tendencias. */

import {
  avg, chartTokens, esc, fetchJSON, fetchText, fmt, fmtDateLong, fmtDateShort,
  loadError, mdToHTML, multiLineChart, playerColor, renderNav, setUpdated, tile,
} from "../app.js";

let roster = [];
let chart = null;
let radar = null;
let radarActive = null;
// vista de informes publicada por el pipeline en summary.reports:
// { every, team: [{date, path}], players: {n: {items, games_at_last}} }
let reportsIndex = { every: 10, team: [], players: {} };
const playersData = new Map();

/* ---- radar octogonal: 8 ejes, todos "más = mejor" (los invertidos se
   transforman en axisValue). Ofensiva en la mitad superior y motor/defensa
   en la inferior, con Goles↔Paradas y Tiros↔Presión enfrentados.
   Normalizado al mejor del equipo por eje. ---- */
const RADAR_AXES = [
  ["Goles", "goals"],
  ["Tiros", "shots"],
  ["Asistencias", "assists"],
  ["Saques", "kickoff_ft_pct"],        // % de 1.er toque en sus kickoffs
  ["Paradas", "saves"],
  ["Presión", "boost_stolen"],
  ["Ritmo", "avg_speed"],
  ["Gestión", "pct_zero_boost", true], // invertida: % del tiempo CON boost
];

function playerAvg(name) {
  return playersData.get(name)?.modes?.["3v3"]?.averages || {};
}

// Valor de un eje para un jugador; los ejes con invert=true son métricas
// en % donde menos es mejor, y se muestran como su complemento (100 − v).
function axisValue(avgs, [, key, invert]) {
  const v = avgs[key];
  if (v == null) return null;
  return invert ? 100 - v : v;
}

function buildRadar(selected) {
  // sin Chart.js (CDN caído) el radar se queda vacío, pero la ficha sigue
  if (!window.Chart) return;
  const t = chartTokens();
  const maxes = RADAR_AXES.map((axis) =>
    Math.max(...roster.map((n) => axisValue(playerAvg(n), axis) ?? 0), 0.0001));
  const datasets = roster.map((n) => {
    const avgs = playerAvg(n);
    return {
      label: n,
      data: RADAR_AXES.map((axis, i) => (axisValue(avgs, axis) ?? 0) / maxes[i]),
      real: RADAR_AXES.map((axis) => axisValue(avgs, axis) ?? 0),
      pointHoverRadius: 5,
    };
  });
  // línea de referencia: media del equipo por eje (gris, discontinua)
  const teamReal = RADAR_AXES.map((axis) =>
    avg(roster.map((n) => axisValue(playerAvg(n), axis) ?? 0)) ?? 0);
  datasets.push({
    label: "Media equipo",
    isTeam: true,
    data: teamReal.map((v, i) => v / maxes[i]),
    real: teamReal,
    backgroundColor: "transparent",
    borderColor: t.faint,
    borderWidth: 1.5,
    borderDash: [6, 4],
    pointRadius: 0,
    pointHoverRadius: 4,
    pointBackgroundColor: t.faint,
    order: 3, // siempre al fondo
  });
  radar = new Chart(document.getElementById("radar"), {
    type: "radar",
    data: { labels: RADAR_AXES.map(([label]) => label), datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false }, // las pestañas de abajo son la leyenda
        tooltip: {
          callbacks: {
            label: (c) => `${c.dataset.label}: ${fmt.format(c.dataset.real[c.dataIndex])}`,
          },
        },
      },
      scales: {
        r: {
          min: 0, max: 1,
          ticks: { display: false },
          grid: { color: t.grid },
          angleLines: { color: t.grid },
          pointLabels: {
            color: t.muted,
            font: { family: t.fontBody, size: 13, weight: 600 },
            // dos líneas: eje + valor real del jugador seleccionado
            callback: (label, i) => {
              const real = radarActive ? axisValue(playerAvg(radarActive), RADAR_AXES[i]) : null;
              return real == null ? label : [label, fmt.format(real)];
            },
          },
        },
      },
    },
  });
  styleRadar(selected);
}

function styleRadar(name) {
  if (!radar) return;
  radarActive = name;
  radar.data.datasets.forEach((ds) => {
    if (ds.isTeam) return; // la media del equipo no cambia con la selección
    const color = playerColor(ds.label, roster);
    const active = ds.label === name;
    ds.backgroundColor = color + (active ? "59" : "14");
    ds.borderColor = active ? color : color + "66";
    ds.borderWidth = active ? 3 : 1.5;
    ds.pointRadius = active ? 3.5 : 2;
    ds.pointBackgroundColor = color;
    ds.order = active ? 0 : 1; // el activo se dibuja encima
  });
  radar.update();
}

// métricas de la comparativa: [etiqueta, clave, nota]
const COMPARE = [
  ["Boost usado por minuto (BPM)", "bpm", ""],
  ["% del tiempo sin boost", "pct_zero_boost", "menos es mejor · sano <12%"],
  ["Boost robado en campo rival", "boost_stolen", ""],
  ["% del tiempo supersónico", "pct_supersonic", ""],
  ["Goles encajados siendo último hombre", "ga_last_defender", "menos es mejor"],
  ["Distancia media a compañeros", "avg_dist_to_mates", "muy baja = apelotonados"],
];

// métricas disponibles en la gráfica de evolución: [clave, etiqueta, unidad]
const EVOLUTION = [
  ["score", "Score", ""],
  ["goals", "Goles", ""],
  ["assists", "Asistencias", ""],
  ["saves", "Paradas", ""],
  ["shots", "Tiros", ""],
  ["shooting_pct", "% de acierto", "%"],
  ["bpm", "Boost usado por minuto", ""],
  ["avg_boost", "Boost medio en el depósito", ""],
  ["pct_zero_boost", "% sin boost", "%"],
  ["boost_stolen", "Boost robado", ""],
  ["avg_speed", "Velocidad media", ""],
  ["pct_supersonic", "% supersónico", "%"],
  ["pct_behind_ball", "% detrás del balón", "%"],
  ["pct_most_back", "% último hombre", "%"],
  ["pct_most_forward", "% primer hombre", "%"],
  ["demos_inflicted", "Demos hechas", ""],
];
let evoActive = null;

// Evolución por partida de TODO el roster + media del equipo, con el
// jugador activo resaltado (mismo lenguaje visual que el radar). La
// leyenda de Chart.js permite ocultar/mostrar cada serie con un clic.
function renderEvolution() {
  if (!window.Chart) return; // sin CDN, la gráfica se omite sin romper nada
  if (chart) { chart.destroy(); chart = null; }
  if (!evoActive || !playersData.size) return;
  const key = document.getElementById("evolution-metric").value;
  const def = EVOLUTION.find((e) => e[0] === key) || EVOLUTION[0];

  // unión de las partidas 3v3 de todos, por fecha ascendente (si alguien
  // faltó a una, su serie puentea el hueco con spanGaps)
  const byMatch = new Map();
  for (const n of roster) {
    for (const h of playersData.get(n)?.history || []) {
      if (h.mode !== "3v3") continue;
      if (!byMatch.has(h.match_id)) byMatch.set(h.match_id, { date: h.date, values: {} });
      byMatch.get(h.match_id).values[n] = h[def[0]] ?? null;
    }
  }
  const rows = [...byMatch.values()].sort((a, b) => (a.date || "").localeCompare(b.date || ""));
  if (!rows.length) return;

  const series = roster.map((n) => ({
    label: n,
    values: rows.map((r) => r.values[n] ?? null),
    color: playerColor(n, roster),
    kind: n === evoActive ? "active" : "dim",
  }));
  series.push({
    label: "Media equipo",
    kind: "team",
    values: rows.map((r) => avg(roster.map((n) => r.values[n]).filter((v) => v != null))),
  });

  chart = multiLineChart(
    document.getElementById("evolution"),
    rows.map((r) => fmtDateShort(r.date)),
    series,
    { unit: def[2] }
  );
}

function renderTabs(selected) {
  document.getElementById("tabs").innerHTML = roster.map((n) => {
    const color = playerColor(n, roster);
    const active = n === selected;
    const avatarStyle = active
      ? `background:${color}26;border-color:${color};color:${color}`
      : "";
    return `<button type="button" class="player-tab" role="tab" data-name="${esc(n)}"
        aria-selected="${active}" ${active ? `style="border-bottom-color:${color}"` : ""}>
      <span class="mini-avatar" style="${avatarStyle}">${esc(n.slice(0, 2).toUpperCase())}</span>
      ${esc(n)}
    </button>`;
  }).join("");
  for (const btn of document.querySelectorAll(".player-tab")) {
    btn.addEventListener("click", () => {
      const name = btn.dataset.name;
      history.replaceState(null, "", `player.html?name=${encodeURIComponent(name)}`);
      renderTabs(name);
      styleRadar(name);
      loadPlayer(name);
    });
  }
}

function renderCompare(name, mine, teamAvg, color) {
  document.getElementById("compare-section").hidden = false;
  document.getElementById("compare-title").textContent = `${name} vs media del equipo`;
  document.getElementById("legend-me").style.background = color;
  document.getElementById("legend-me-name").textContent = name;
  document.getElementById("compare").innerHTML = COMPARE.map(([label, key, note]) => {
    const a = mine[key], b = teamAvg[key];
    if (a == null || b == null) return "";
    const max = Math.max(a, b, 0.001);
    const unit = key.startsWith("pct") ? "%" : "";
    return `<div class="duo">
      <span class="metric">${label}${note ? ` <small>(${note})</small>` : ""}</span>
      <div class="line"><span class="bar me" style="width:${Math.round((a / max) * 72)}%;background:${color}"></span><span class="v">${fmt.format(a)}${unit}</span></div>
      <div class="line"><span class="bar team" style="width:${Math.round((b / max) * 72)}%"></span><span class="v team">${fmt.format(b)}${unit}</span></div>
    </div>`;
  }).join("");
}

async function loadPlayer(name) {
  const player = playersData.get(name);
  if (!player) {
    document.getElementById("player-error").innerHTML = '<p class="empty">Jugador no encontrado.</p>';
    document.getElementById("tiles").innerHTML = "";
    document.getElementById("compare-section").hidden = true;
    return;
  }
  document.getElementById("player-error").innerHTML = "";
  document.title = `${player.name} — RL Stats`;
  const color = playerColor(player.name, roster);

  const mode = (player.modes || {})["3v3"];
  if (mode) {
    const avgs = mode.averages || {};
    const wr = Math.round((mode.winrate ?? 0) * 100);
    document.getElementById("tiles").innerHTML =
      tile("Partidas", mode.games, "") +
      tile("Winrate", `${wr}%`, `${mode.wins ?? "—"} victorias`, wr >= 50 ? "good" : "bad") +
      tile("Score medio", Math.round(avgs.score ?? 0), "por partida") +
      tile("Goles · Asist.", `${fmt.format(avgs.goals ?? 0)}<small> / ${fmt.format(avgs.assists ?? 0)}</small>`, "medias por partida");
  } else {
    document.getElementById("tiles").innerHTML = "";
  }

  // totales acumulados en 3v3 (palmarés), calculados del historial
  const rows3 = (player.history || []).filter((h) => h.mode === "3v3");
  if (rows3.length) {
    const sum = (key) => rows3.reduce((acc, h) => acc + (h[key] ?? 0), 0);
    const goals = sum("goals"), shots = sum("shots");
    const assists = sum("assists"), saves = sum("saves");
    const mvps = rows3.filter((h) => h.mvp).length;
    const mvpPct = Math.round((mvps / rows3.length) * 100);
    document.getElementById("totals").innerHTML =
      tile("Goles", goals,
        shots ? `de ${shots} tiros · ${Math.round((goals / shots) * 100)}% acierto` : "totales 3v3") +
      tile("Asistencias", assists, `${fmt.format(assists / rows3.length)} por partida`) +
      tile("Paradas", saves, `${fmt.format(saves / rows3.length)} por partida`) +
      // un tercio = reparto equitativo en un equipo de 3
      tile("MVPs", mvps, `${mvpPct}% de las partidas`, mvpPct >= 33 ? "good" : "");
  } else {
    document.getElementById("totals").innerHTML = "";
  }

  // la gráfica resalta al jugador activo (mismo lenguaje que el radar)
  evoActive = player.name;
  renderEvolution();

  // media del equipo: promedio de las medias 3v3 del roster
  document.getElementById("compare-section").hidden = true;
  if (mode) {
    const avgsAll = roster.map((n) => playersData.get(n)?.modes?.["3v3"]?.averages).filter(Boolean);
    if (avgsAll.length > 1) {
      const teamAvg = {};
      for (const [, key] of COMPARE) {
        const vals = avgsAll.map((a) => a[key]).filter((v) => v != null);
        if (vals.length) teamAvg[key] = avg(vals);
      }
      renderCompare(player.name, mode.averages || {}, teamAvg, color);
    }
  }

  // informe de tendencias: histórico por fechas, o estado vacío con progreso
  renderTrendReport(player.name, mode?.games ?? 0);
}

// Desplegable con las fechas de los informes de tendencia del jugador
// (summary.reports los enumera: un sitio estático no puede listar carpetas).
function renderTrendReport(name, games) {
  const sel = document.getElementById("trend-date");
  const info = reportsIndex.players?.[name];
  const items = [...(info?.items || [])].reverse();
  if (!items.length) {
    sel.hidden = true;
    // progreso real hacia el siguiente informe: cada `every` partidas
    // desde el último (el ciclo lo publica el pipeline, no va a fuego)
    const every = reportsIndex.every || 10;
    const since = Math.min(games - (info?.games_at_last ?? 0), every);
    document.getElementById("player-report").innerHTML = `
      <div class="empty-state">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="var(--faint)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 7v5l3 3"></path></svg>
        <span class="t">El informe de tendencias se genera cada ${every} partidas</span>
        <span class="s">Lleva ${since} de ${every} · comparará su evolución con el equipo y propondrá un plan de práctica</span>
        <span class="progress"><span style="width:${Math.round((since / every) * 100)}%"></span></span>
      </div>`;
    return;
  }
  sel.hidden = false;
  sel.innerHTML = items.map((i) => `<option value="${i.date}">${fmtDateLong(i.date)}</option>`).join("");
  showTrendReport(name, items[0].date);
}

// evita que al cambiar rápido de pestaña o de fecha, un fetch atrasado
// pinte el informe de otro jugador encima del actual
let trendSeq = 0;

async function showTrendReport(name, date) {
  const seq = ++trendSeq;
  const item = (reportsIndex.players?.[name]?.items || []).find((i) => i.date === date);
  const { data: md, failed } = item
    ? await fetchText(`data/${item.path}`)
    : { data: null, failed: false };
  if (seq !== trendSeq) return; // llegó tarde: ya se pidió otro informe
  document.getElementById("player-report").innerHTML = md
    ? `<div class="card report">${mdToHTML(md)}</div>`
    : `<p class="empty">No se pudo cargar el informe${failed ? " (fallo de red)" : ""}.</p>`;
}

async function main() {
  renderNav("player");
  const { data: summary } = await fetchJSON("data/summary.json");
  if (!summary) { loadError(document.getElementById("player-error")); return; }
  setUpdated(summary);
  roster = summary?.players || [];
  if (!roster.length) {
    document.getElementById("player-error").innerHTML =
      '<p class="empty">Aún no hay jugadores: se rellenan solos con la primera partida.</p>';
    return;
  }
  // todos los jugadores de una vez: alimentan radar, ficha y media del equipo
  const all = await Promise.all(
    roster.map((n) => fetchJSON(`data/players/${encodeURIComponent(n)}.json`))
  );
  roster.forEach((n, i) => { if (all[i].data) playersData.set(n, all[i].data); });

  reportsIndex = summary.reports || reportsIndex;

  const sel = document.getElementById("evolution-metric");
  sel.innerHTML = EVOLUTION.map(([k, label]) => `<option value="${k}">${label}</option>`).join("");
  sel.addEventListener("change", renderEvolution);

  const trendSel = document.getElementById("trend-date");
  trendSel.addEventListener("change", () => showTrendReport(evoActive, trendSel.value));

  const asked = new URLSearchParams(location.search).get("name");
  const selected = roster.includes(asked) ? asked : roster[0];
  renderTabs(selected);
  buildRadar(selected);
  loadPlayer(selected);
}
main();

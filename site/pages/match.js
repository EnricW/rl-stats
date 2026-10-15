/* Página de partida: marcador, tablas, visor 3D, cronología, heatmap,
   rotación, saques e informe IA. */

import {
  chartTokens, esc, fetchJSON, fmt, fmtClock, fmtDate, loadError,
  playerColor, rankLabel, renderNav, renderReport, safeRender, setUpdated, sides,
} from "../app.js";
import { initMatchViewer } from "../viewer.js";

const COLS = [
  ["Score", (s) => s.core?.score],
  ["Goles", (s) => s.core?.goals],
  ["Tiros", (s) => s.core?.shots],
  ["Asist.", (s) => s.core?.assists],
  ["Paradas", (s) => s.core?.saves],
  ["% acierto", (s) => s.core?.shooting_percentage],
  ["Boost robado", (s) => s.boost?.amount_stolen],
  ["% sin boost", (s) => s.boost?.percent_zero_boost],
  ["% supersónico", (s) => s.movement?.percent_supersonic_speed],
  ["Demos", (s) => s.demo?.inflicted],
];

function teamTable(match, color, title, ours) {
  const rows = match.players.filter((p) => p.team === color);
  if (!rows.length) return "";
  const head = COLS.map(([h]) => `<th class="num">${h}</th>`).join("");
  const body = rows.map((p) => {
    const name = p.roster
      ? `<a href="player.html?name=${encodeURIComponent(p.name)}">${esc(p.name)}</a>`
      : esc(p.name);
    const nick = p.in_game_name && p.in_game_name !== p.name
      ? ` <span class="nick">· ${esc(p.in_game_name)}</span>` : "";
    const rank = rankLabel(p.rank, { division: true });
    const rankTxt = rank ? ` <span class="nick">· ${esc(rank)}</span>` : "";
    const cells = COLS.map(([h, get]) => {
      const v = get(p.stats);
      const strong = h === "Score" ? " score-mono" : "";
      return `<td class="num${strong}">${v == null ? "—" : fmt.format(v)}</td>`;
    }).join("");
    return `<tr><td>${name}${nick}${rankTxt}${p.mvp ? " ⭐" : ""}</td>${cells}</tr>`;
  }).join("");
  const dot = ours ? "var(--blue)" : "var(--orange)";
  return `<section class="section">
    <div class="section-head"><span class="team-dot" style="background:${dot}"></span>
      <h2 ${ours ? "" : 'style="color:var(--muted)"'}>${title}</h2></div>
    <div class="card table-scroll ${ours ? "" : "dim"}"><table style="min-width:760px">
      <thead><tr><th>Jugador</th>${head}</tr></thead>
      <tbody>${body}</tbody>
    </table></div></section>`;
}

function renderOverview(match) {
  const { us, them } = sides(match);
  const sum = (color, get) => match.players
    .filter((p) => p.team === color)
    .reduce((acc, p) => acc + (get(p.stats) ?? 0), 0);
  const metrics = [
    ["Goles", (s) => s.core?.goals],
    ["Tiros", (s) => s.core?.shots],
    ["Paradas", (s) => s.core?.saves],
    ["Boost robado", (s) => s.boost?.amount_stolen],
    ["Score total", (s) => s.core?.score],
  ];
  const row = (label, a, b, fmtVal) => {
    const max = Math.max(a ?? 0, b ?? 0, 1);
    return `<div class="row">
      <span class="v">${a == null ? "—" : fmtVal(a)}</span>
      <span class="half l"><span class="bar" style="width:${Math.round(((a ?? 0) / max) * 100)}%"></span></span>
      <span class="lbl">${label}</span>
      <span class="half r"><span class="bar" style="width:${Math.round(((b ?? 0) / max) * 100)}%"></span></span>
      <span class="v r">${b == null ? "—" : fmtVal(b)}</span>
    </div>`;
  };
  const rows = metrics.map(([label, get]) =>
    row(label, sum(us, get), sum(them, get), (v) => fmt.format(v))).join("");
  // stats que solo existen a nivel de equipo (bloque "ball" de ballchasing)
  const teamStat = (color, get) => get(match.teams?.[color]?.stats) ?? null;
  const teamRows = [
    ["Posesión", (s) => s?.ball?.possession_time],
    ["Balón en campo propio", (s) => s?.ball?.time_in_side],
  ].map(([label, get]) => {
    const a = teamStat(us, get), b = teamStat(them, get);
    return a == null && b == null ? "" : row(label, a, b, fmtClock);
  }).join("");
  document.getElementById("overview").innerHTML =
    `<div class="head"><span class="l">NOSOTROS</span><span class="r">RIVALES</span></div>${rows}${teamRows}` +
    (teamRows ? '<span class="note">Balón en campo propio: cuanto menos, menos tiempo encerrados defendiendo.</span>' : "");
}

function renderPositioning(match) {
  const rows = match.players.filter((p) => p.roster);
  if (!rows.length) return;
  document.getElementById("positioning-section").hidden = false;
  document.getElementById("positioning").innerHTML = rows.map((p) => {
    const v = p.stats.positioning?.percent_behind_ball;
    return `<div class="bar-row">
      <span class="nm">${esc(p.name)}</span>
      <span class="track">
        <span class="fill" style="width:${Math.min(v ?? 0, 100)}%"></span>
        <span class="threshold" style="left:55%"></span>
      </span>
      <span class="val">${v == null ? "—" : fmt.format(v) + "%"}</span>
    </div>`;
  }).join("") + '<span class="note">La marca gris indica el umbral sano (55%): por encima, bien colocados en defensa.</span>';
}

function renderRoles(match, roster) {
  const rows = match.players.filter((p) => p.roster);
  const data = rows.map((p) => ({
    name: p.name,
    back: p.stats.positioning?.percent_most_back,
    fwd: p.stats.positioning?.percent_most_forward,
  })).filter((d) => d.back != null || d.fwd != null);
  if (!data.length) return;
  const maxV = Math.max(...data.flatMap((d) => [d.back ?? 0, d.fwd ?? 0]), 1);
  document.getElementById("roles-section").hidden = false;
  document.getElementById("roles").innerHTML = data.map((d) => {
    const color = playerColor(d.name, roster);
    const line = (v, cls, style, label) => v == null ? "" :
      `<div class="line"><span class="bar ${cls}" style="width:${Math.round((v / maxV) * 72)}%;${style}"></span><span class="v${cls === "team" ? " team" : ""}">${fmt.format(v)}% ${label}</span></div>`;
    return `<div class="duo">
      <span class="metric">${esc(d.name)}</span>
      ${line(d.back, "me", `background:${color}`, "último hombre")}
      ${line(d.fwd, "team", "", "primer hombre")}
    </div>`;
  }).join("") + '<span class="note">% del tiempo siendo el último / primer hombre del equipo (rol de facto). Equilibrado ≈ 33% cada uno; dos jugadores muy altos en "primer hombre" a la vez = doble commit.</span>';
}

function renderRotation(events, roster) {
  const rot = events.rotation || {};
  const names = Object.keys(rot);
  if (!names.length) return;
  document.getElementById("rotation-section").hidden = false;
  document.getElementById("rotation").innerHTML = names.map((name) => {
    const r = rot[name];
    const color = playerColor(name, roster);
    const seg = (v, suffix) => v == null ? "" :
      `<span class="fill" style="position:relative;flex:0 0 auto;width:${v}%;background:${color}${suffix}"></span>`;
    return `<div class="bar-row">
      <span class="nm">${esc(name)}</span>
      <span class="track" style="display:flex;overflow:hidden">
        ${seg(r.pct_first_man, "")}${seg(r.pct_second_man, "99")}${seg(r.pct_third_man, "4D")}
      </span>
      <span class="val" style="width:auto;font-size:13px">${fmt.format(r.pct_first_man ?? 0)} · ${fmt.format(r.pct_second_man ?? 0)} · ${fmt.format(r.pct_third_man ?? 0)}%</span>
    </div>`;
  }).join("") + '<span class="note">% del tiempo activo como 1.<sup>er</sup> hombre (color pleno: presiona el balón), 2.º (medio: apoya) y 3.º (suave: cubre atrás). El hueco hasta 100% son transiciones. Sano ≈ tercios equilibrados.</span>';
}

function renderKickoffs(events, ourTeamIdx, roster) {
  const list = events.kickoffs || [];
  if (!list.length) return;
  document.getElementById("kickoffs-section").hidden = false;
  const chips = list.map((k, i) => {
    const won = k.outcome == null ? null : k.outcome === ourTeamIdx;
    const cls = won == null ? "" : won ? " win" : " loss";
    const goal = k.goal_team == null ? null : k.goal_team === ourTeamIdx;
    const title = `Saque ${i + 1} · ${fmtClock(k.t)} · 1.er toque: ${k.first_touch ?? "—"}` +
      (won == null ? " · neutral" : won ? " · ganado" : " · perdido") +
      (goal == null ? "" : goal ? " · ¡gol nuestro!" : " · gol rival");
    return `<span class="ko${cls}${goal != null ? " goal" : ""}" title="${esc(title)}">${i + 1}</span>`;
  }).join("");
  const kp = events.kickoff_players || {};
  const rows = Object.entries(kp).map(([name, s]) => {
    const pct = s.taken ? Math.round((s.first_touches / s.taken) * 100) : null;
    return `<tr><td style="color:${playerColor(name, roster)};font-weight:600">${esc(name)}</td>
      <td class="num">${s.taken ?? "—"}</td>
      <td class="num">${s.first_touches ?? "—"}</td>
      <td class="num">${pct == null ? "—" : pct + "%"}</td>
      <td class="num">${s.avg_boost_after == null ? "—" : fmt.format(s.avg_boost_after)}</td></tr>`;
  }).join("");
  document.getElementById("kickoffs").innerHTML = `
    <div class="ko-chips">${chips}</div>
    <div class="table-scroll"><table style="min-width:0">
      <thead><tr><th>Jugador</th><th class="num">Saques tirados</th><th class="num">1.er toque</th><th class="num">% ganados</th><th class="num">Boost tras saque</th></tr></thead>
      <tbody>${rows}</tbody>
    </table></div>
    <span class="note">Un chip por saque: azul = primer control nuestro, naranja = del rival, gris = neutral; con borde = acabó en gol. Pasa el cursor para ver el detalle.</span>`;
}

function renderHeatmap(frames, match, roster) {
  const rosterNames = match.players.filter((p) => p.roster).map((p) => p.name);
  const tabsData = frames.players
    .map((p, i) => ({ name: p.name, team: p.team, i }))
    .filter((p) => rosterNames.includes(p.name));
  if (!tabsData.length) return;
  document.getElementById("heatmap-section").hidden = false;
  const tabs = document.getElementById("heatmap-tabs");
  tabs.innerHTML = tabsData.map((p, j) =>
    `<button type="button" class="heat-tab" data-i="${p.i}" aria-pressed="${j === 0}"
       style="--c:${playerColor(p.name, roster)}">${esc(p.name)}</button>`).join("");
  const draw = (i) => drawHeatmap(frames, i, playerColor(frames.players[i].name, roster));
  for (const btn of tabs.querySelectorAll(".heat-tab")) {
    btn.addEventListener("click", () => {
      for (const b of tabs.querySelectorAll(".heat-tab")) b.setAttribute("aria-pressed", b === btn);
      draw(+btn.dataset.i);
    });
  }
  draw(tabsData[0].i);
}

function drawHeatmap(frames, idx, color) {
  const t = chartTokens();
  const canvas = document.getElementById("heatmap-canvas");
  const ctx = canvas.getContext("2d");
  const W = canvas.width, H = canvas.height;
  const GRID_COLS = 24, GRID_ROWS = 30; // campo de 8192×10240 uu
  const grid = new Float32Array(GRID_COLS * GRID_ROWS);
  const team0 = frames.players[idx].team === 0; // el equipo 0 ataca hacia +y
  const car = frames.cars[idx];
  let maxV = 0;
  for (let i = 0; i < car.length; i++) {
    if (frames.phase[i] !== 1) continue; // solo juego activo
    const f = car[i];
    if (!f || f[0] == null || f[1] == null) continue;
    let x = f[0], y = f[1];
    if (!team0) { x = -x; y = -y; } // espejo: siempre atacando hacia arriba
    const c = Math.min(GRID_COLS - 1, Math.max(0, Math.floor(((x + 4096) / 8192) * GRID_COLS)));
    const r = Math.min(GRID_ROWS - 1, Math.max(0, Math.floor(((5120 - y) / 10240) * GRID_ROWS)));
    const v = ++grid[r * GRID_COLS + c];
    if (v > maxV) maxV = v;
  }
  ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = t.card2 || "#0F141F";
  ctx.fillRect(0, 0, W, H);
  if (maxV) {
    const cw = W / GRID_COLS, ch = H / GRID_ROWS;
    ctx.fillStyle = color;
    for (let r = 0; r < GRID_ROWS; r++) {
      for (let c = 0; c < GRID_COLS; c++) {
        const v = grid[r * GRID_COLS + c];
        if (!v) continue;
        ctx.globalAlpha = Math.pow(v / maxV, 0.6) * 0.92;
        ctx.fillRect(c * cw, r * ch, cw + 0.5, ch + 0.5);
      }
    }
    ctx.globalAlpha = 1;
  }
  // líneas del campo: borde, medio, círculo central y bocas de portería
  ctx.strokeStyle = "rgba(237,242,250,.28)";
  ctx.lineWidth = 1.5;
  ctx.strokeRect(1, 1, W - 2, H - 2);
  ctx.beginPath(); ctx.moveTo(0, H / 2); ctx.lineTo(W, H / 2); ctx.stroke();
  ctx.beginPath(); ctx.arc(W / 2, H / 2, W * 0.11, 0, Math.PI * 2); ctx.stroke();
  const gw = W * (1786 / 8192);
  ctx.strokeRect(W / 2 - gw / 2, 1, gw, H * 0.035);
  ctx.strokeRect(W / 2 - gw / 2, H * (1 - 0.035) - 1, gw, H * 0.035);
  ctx.fillStyle = "rgba(154,167,189,.85)";
  ctx.font = `600 13px ${t.fontBody}`;
  ctx.fillText("ATAQUE", 10, 22);
  ctx.fillText("DEFENSA", 10, H - 12);
}

function renderTimeline(frames, events, ourIsTeam0) {
  const t = chartTokens();
  const font = `font-family="${t.fontBody}"`;
  const svg = document.getElementById("timeline-svg");
  const duration = frames.ball.length / frames.fps;
  let regEnd = duration;
  for (let i = 1; i < frames.clock.length; i++) {
    if (frames.clock[i] === 0 && frames.clock[i - 1] > 0) { regEnd = i / frames.fps; break; }
  }
  const x = (ts) => 60 + (ts / duration) * 650;
  const parts = [];
  parts.push(`<text x="10" y="48" font-size="12" font-weight="600" fill="${t.blueHi}" ${font}>NOSOTROS</text>`);
  parts.push(`<text x="10" y="132" font-size="12" font-weight="600" fill="${t.orangeHi}" ${font}>RIVALES</text>`);
  parts.push(`<line x1="60" y1="85" x2="710" y2="85" stroke="${t.border}" stroke-width="2"></line>`);
  if (regEnd < duration) {
    parts.push(`<line x1="${x(regEnd)}" y1="70" x2="${x(regEnd)}" y2="100" stroke="${t.faint}" stroke-width="2" stroke-dasharray="3 3"></line>`);
    parts.push(`<text x="${x(regEnd)}" y="62" text-anchor="middle" font-size="11" fill="${t.faint}" ${font}>FIN 5:00</text>`);
  }
  for (const g of frames.goals) {
    const ours = (g.team === 0) === ourIsTeam0;
    const gx = x(g.t);
    const [y1, y2, cy, ty] = ours ? [85, 58, 52, 36] : [85, 112, 118, 140];
    const color = ours ? t.blue : t.orange;
    const txt = ours ? t.ink : t.orangeHi;
    const label = `${esc(g.name)}${g.t > regEnd ? " · OT" : ""}`;
    parts.push(`<line x1="${gx}" y1="${y1}" x2="${gx}" y2="${y2}" stroke="${color}" stroke-width="2"></line>`);
    parts.push(`<circle cx="${gx}" cy="${cy}" r="6" fill="${color}"></circle>`);
    parts.push(`<text x="${gx}" y="${ty}" text-anchor="middle" font-size="12" font-weight="600" fill="${txt}" ${font}>${label}</text>`);
  }
  // marcas menores: tiros y paradas con su tiempo exacto (si hay eventos)
  for (const e of events?.stat_events || []) {
    if (e.t == null || e.kind === "assist") continue;
    const ours = (e.team === 0) === ourIsTeam0;
    const ex = x(e.t), ey = ours ? 76 : 94;
    const color = ours ? t.blueHi : t.orangeHi;
    const tip = `<title>${esc(e.name)} · ${e.kind === "shot" ? "tiro" : "parada"} · ${fmtClock(e.t)}</title>`;
    parts.push(
      e.kind === "shot"
        ? `<circle cx="${ex}" cy="${ey}" r="3.5" fill="none" stroke="${color}" stroke-width="1.5" opacity=".75">${tip}</circle>`
        : `<rect x="${ex - 3}" y="${ey - 3}" width="6" height="6" transform="rotate(45 ${ex} ${ey})" fill="${color}" opacity=".8">${tip}</rect>`
    );
  }
  parts.push(`<text x="60" y="162" font-size="11" fill="${t.faint}" ${font}>0:00</text>`);
  parts.push(`<text x="${x(duration)}" y="162" text-anchor="end" font-size="11" fill="${t.faint}" ${font}>${regEnd < duration ? "prórroga" : fmtClock(duration)}</text>`);
  svg.innerHTML = parts.join("");
  svg.setAttribute("aria-label", "Cronología de la partida: goles, tiros y paradas");
  document.getElementById("timeline-legend").hidden = !(events?.stat_events || []).length;
  document.getElementById("timeline-section").hidden = false;
}

function renderScoreboard(match) {
  // el marcador se tiñe según el resultado (mismas clases que la portada)
  if (match.result) document.getElementById("scoreboard").classList.add(match.result);
  const { us, them } = sides(match);
  const result = match.result === "win"
    ? '<span class="res win" style="align-self:center;font-size:13px;padding:6px 12px">VICTORIA</span>'
    : match.result === "loss"
      ? '<span class="res loss" style="align-self:center;font-size:13px;padding:6px 12px">DERROTA</span>' : "";
  const lobby = (() => {
    const lo = rankLabel(match.min_rank), hi = rankLabel(match.max_rank);
    if (!lo && !hi) return "";
    const txt = lo && hi && lo !== hi ? `${lo} – ${hi}` : (lo || hi);
    return `<span class="chip">Lobby: ${esc(txt)}</span>`;
  })();
  document.getElementById("scoreboard").innerHTML = `
    <div class="chips">
      <span class="chip">${esc(match.mode)} ranked</span>
      <span class="chip">${esc(match.map ?? "—")}</span>
      <span class="chip">${fmtDate(match.date)}</span>
      ${lobby}
      ${match.overtime ? '<span class="chip warn">Prórroga</span>' : ""}
    </div>
    <div class="teams-score">
      <div style="display:flex;align-items:center;gap:24px">
        <div class="side"><span class="tag" style="color:var(--blue-hi)">Nosotros</span>
          <span class="pts" style="color:var(--blue-hi)">${match.score[us]}</span></div>
        <span class="dash" style="font-size:28px;color:var(--faint)">—</span>
        <div class="side"><span class="tag" style="color:var(--orange-hi)">Rivales</span>
          <span class="pts" style="color:var(--orange-hi)">${match.score[them]}</span></div>
        ${result}
      </div>
      <span class="spacer" style="flex-grow:1"></span>
      <a class="btn" href="#visor" id="watch-btn" hidden>
        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="6 3 20 12 6 21 6 3"></polygon></svg>
        Ver repetición</a>
    </div>`;
}

async function main() {
  renderNav("match");
  // el id de la URL acaba en una ruta de fetch: solo el formato UUID
  // de ballchasing (igual que valida pipeline/report.py --match)
  const raw = new URLSearchParams(location.search).get("id");
  const id = raw && /^[0-9a-f-]{36}$/i.test(raw) ? raw : null;
  const [matchRes, summaryRes] = await Promise.all([
    id ? fetchJSON(`data/matches/${id}.json`) : Promise.resolve({ data: null, missing: true }),
    fetchJSON("data/summary.json"),
  ]);
  const match = matchRes.data;
  const summary = summaryRes.data;
  setUpdated(summary);
  if (!match) {
    const board = document.getElementById("scoreboard");
    if (matchRes.failed) loadError(board, "los datos de la partida");
    else board.innerHTML = '<p class="empty">Partida no encontrada.</p>';
    return;
  }
  document.title = `${match.mode} en ${match.map ?? "?"} — RL Stats`;

  const { us, them } = sides(match);
  safeRender("scoreboard", () => renderScoreboard(match));
  safeRender("overview", () => renderOverview(match));
  safeRender("teams", () => {
    document.getElementById("teams").innerHTML =
      teamTable(match, us, "Nuestro equipo", true) + teamTable(match, them, "Rivales", false);
  });
  safeRender("positioning", () => renderPositioning(match));
  // colores de identidad: el roster global del equipo, no solo los
  // presentes en esta partida (si falta uno, los colores no bailan)
  const matchRoster = match.players.filter((p) => p.roster).map((p) => p.name);
  const colorRoster = summary?.players?.length ? summary.players : matchRoster;
  safeRender("roles", () => renderRoles(match, colorRoster));

  // summary dice qué derivados existen (has_report/has_events/has_frames):
  // así no se piden archivos que sabemos que faltan (404 a ciegas)
  const entry = summary?.matches?.find((m) => m.id === match.id);
  const noReportText =
    "Esta partida aún no tiene informe (se genera en la siguiente pasada del pipeline).";
  if (entry?.has_report === false) {
    document.getElementById("report").innerHTML = `<p class="empty">${noReportText}</p>`;
  } else {
    renderReport(document.getElementById("report"), `data/reports/${match.id}.md`, noReportText);
  }

  // visor 3D, cronología, heatmap y eventos: solo si el replay se parseó.
  // Eventos (~7 KB) y frames (pesados) se piden en paralelo.
  const ourIsTeam0 = us === "blue"; // team 0 = azul en el replay
  const [eventsRes, framesRes] = await Promise.all([
    entry?.has_events === false
      ? Promise.resolve({ data: null }) : fetchJSON(`data/events/${match.id}.json`),
    entry?.has_frames === false
      ? Promise.resolve({ data: null }) : fetchJSON(`data/frames/${match.id}.json`),
  ]);
  const events = eventsRes.data;
  const frames = framesRes.data;
  if (events) {
    safeRender("rotation", () => renderRotation(events, colorRoster));
    safeRender("kickoffs", () => renderKickoffs(events, ourIsTeam0 ? 0 : 1, colorRoster));
  }
  if (frames) {
    safeRender("timeline-svg", () => renderTimeline(frames, events, ourIsTeam0));
    safeRender("heatmap-canvas", () => renderHeatmap(frames, match, colorRoster));
  }
  if (frames && window.THREE) {
    document.getElementById("visor-section").hidden = false;
    document.getElementById("watch-btn").hidden = false;
    try {
      initMatchViewer(document.getElementById("viewer-root"), frames);
    } catch (e) {
      // sin WebGL (navegador antiguo o restringido): se oculta el visor
      console.error("Visor no disponible:", e);
      document.getElementById("viewer-root").innerHTML =
        '<p class="empty">Tu navegador no puede mostrar el visor 3D (requiere WebGL).</p>';
    }
    // el visor estaba hidden al cargar: el salto a #visor (desde la
    // portada o el listado) hay que repetirlo ahora que existe
    if (location.hash === "#visor") {
      document.getElementById("visor-section").scrollIntoView({ behavior: "smooth" });
    }
  }
}
main();

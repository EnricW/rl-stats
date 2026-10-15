/* Portada: resumen del equipo, forma, última partida, ranking e informe. */

import {
  esc, fetchJSON, fetchText, fmt, fmtDateLong, fmtDateShort, loadError, mdToHTML,
  playerColor, renderNav, resultPill, setUpdated, sides, sortByDateDesc, tile,
} from "../app.js";

const CHECK = '<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="var(--win)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="Victoria"><path d="M20 6 9 17l-5-5"></path></svg>';
const CROSS = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--loss)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" role="img" aria-label="Derrota"><path d="M18 6 6 18"></path><path d="m6 6 12 12"></path></svg>';

function renderTiles(matches) {
  const played = matches.filter((m) => m.result);
  const wins = played.filter((m) => m.result === "win").length;
  const losses = played.length - wins;
  let gf = 0, gc = 0;
  for (const m of matches) {
    if (!m.our_team) continue;
    const { us, them } = sides(m);
    gf += m.score[us]; gc += m.score[them];
  }
  const wr = played.length ? Math.round((wins / played.length) * 100) : 0;
  const dif = gf - gc;
  document.getElementById("tiles").innerHTML =
    tile("Partidas", matches.length, "temporada actual") +
    tile("Winrate", `${wr}%`, `${wins} V · ${losses} D`, wr >= 50 ? "good" : "bad") +
    tile("Goles", `${gf}<small> / ${gc}</small>`, "a favor / en contra") +
    tile("Dif. de goles", `${dif >= 0 ? "+" : ""}${dif}`,
      matches.length ? `media ${fmt.format(dif / matches.length)} por partida` : "",
      dif >= 0 ? "good" : "bad");
}

function renderForma(matches) {
  // cronológico de izquierda a derecha, las últimas 8
  const seq = [...matches].reverse().slice(-8);
  if (!seq.length) {
    document.getElementById("forma").innerHTML =
      '<p class="empty">Aún no hay partidas: juega una y aparecerá aquí sola.</p>';
    return;
  }
  const items = seq.map((m, i) => {
    const last = i === seq.length - 1;
    // tres estados: victoria, derrota y neutro (empate o equipo ambiguo)
    const icon = m.result === "win"
      ? `<span class="form-icon win">${CHECK}</span>`
      : m.result === "loss"
        ? `<span class="form-icon loss">${CROSS}</span>`
        : '<span class="form-icon" aria-label="Sin resultado" style="color:var(--faint)">—</span>';
    return `<a class="form-item ${last ? "last" : ""}" href="match.html?id=${m.id}">
        ${icon}
        <span>${fmtDateShort(m.date)}${last ? " · última" : ""}</span>
      </a>`;
  }).join('<span class="form-link" aria-hidden="true"></span>');
  document.getElementById("forma").innerHTML = `
    <div class="label-block">
      <span class="tile-label" style="font-size:12px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--faint)">Forma</span>
      <span class="sub">últimas ${seq.length} partidas</span>
    </div>
    <div class="form-seq">${items}</div>`;
}

function renderUltima(matches, roster) {
  const m = matches[0];
  if (!m) {
    document.getElementById("ultima").innerHTML =
      '<p class="empty">La primera partida del equipo aparecerá aquí.</p>';
    return;
  }
  const { us, them } = sides(m);
  const rows = (m.players || []).map((p) => {
    const bits = [];
    if (p.mvp) bits.push("MVP ⭐");
    if (p.goals) bits.push(`${p.goals} ${p.goals === 1 ? "gol" : "goles"}`);
    if (p.assists) bits.push(`${p.assists} asist.`);
    if (p.saves) bits.push(`${p.saves} ${p.saves === 1 ? "parada" : "paradas"}`);
    bits.push(`score ${fmt.format(p.score)}`);
    return `<div class="row"><span class="dot" style="background:${playerColor(p.name, roster)}"></span>
      <span class="nm">${esc(p.name)}</span><span class="tx">${bits.join(" · ")}</span></div>`;
  }).join("");
  document.getElementById("ultima").innerHTML = `
    <div class="score-block">
      <span class="kicker" style="font-size:12px;font-weight:600;letter-spacing:2px;text-transform:uppercase;color:var(--accent)">Última partida</span>
      <div class="bigscore">
        <span class="us">${m.score[us]}</span><span class="dash">—</span><span class="them">${m.score[them]}</span>
        ${resultPill(m.result, m.overtime)}
      </div>
      <span class="sub" style="font-size:14px;color:var(--muted)">${esc(m.mode)} · ${esc(m.map ?? "—")} · ${fmtDateShort(m.date)}</span>
    </div>
    <div class="players-mini">${rows}</div>
    <div class="cta">
      <a class="btn" href="match.html?id=${m.id}">Ver partida
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 12h14"></path><path d="m13 6 6 6-6 6"></path></svg></a>
    </div>`;
}

function renderRanking(matches, roster) {
  const totals = new Map();
  for (const m of matches) for (const p of m.players || []) {
    const t = totals.get(p.name) || { score: 0, games: 0 };
    t.score += p.score; t.games += 1;
    totals.set(p.name, t);
  }
  const rank = [...totals.entries()]
    .map(([name, t]) => ({ name, avg: t.score / t.games }))
    .sort((a, b) => b.avg - a.avg);
  const max = rank[0]?.avg || 1;
  document.getElementById("ranking-bars").innerHTML = rank.map((r) => `
    <a class="bar-row" href="player.html?name=${encodeURIComponent(r.name)}" style="color:var(--ink)">
      <span class="nm">${esc(r.name)}</span>
      <span class="track"><span class="fill" style="width:${Math.round((r.avg / max) * 100)}%;background:${playerColor(r.name, roster)}"></span></span>
      <span class="val">${Math.round(r.avg)}</span>
    </a>`).join("") || '<p class="empty">Sin datos todavía.</p>';
}

// evita que un cambio rápido de fecha pinte un informe atrasado encima del nuevo
let teamReportSeq = 0;

async function main() {
  renderNav("index");
  const { data: summary, failed } = await fetchJSON("data/summary.json");
  if (!summary) {
    loadError(document.getElementById("tiles"), failed ? "los datos" : "los datos (aún no existen)");
    document.getElementById("forma").innerHTML = "";
    document.getElementById("ultima").innerHTML = "";
    return;
  }
  setUpdated(summary);
  const matches = sortByDateDesc(summary.matches || []);
  const roster = summary.players || [];
  renderTiles(matches);
  renderForma(matches);
  renderUltima(matches, roster);
  renderRanking(matches, roster);

  // informe de equipo: histórico con fechas y rutas publicadas por el
  // pipeline en summary.reports (la web no reconstruye nombres a mano)
  const teamReports = [...(summary.reports?.team || [])].reverse();
  const teamSel = document.getElementById("team-report-date");
  const pathByDate = new Map(teamReports.map((r) => [r.date, r.path]));
  const showTeam = async (date) => {
    const seq = ++teamReportSeq;
    const { data: md, failed } = await fetchText(`data/${pathByDate.get(date)}`);
    if (seq !== teamReportSeq) return; // llegó tarde: ya se pidió otra fecha
    document.getElementById("team-report").innerHTML = md
      ? mdToHTML(md)
      : `<p class="empty">No se pudo cargar el informe${failed ? " (fallo de red)" : ""}.</p>`;
  };
  if (teamReports.length) {
    teamSel.hidden = false;
    teamSel.innerHTML = teamReports.map((r) => `<option value="${r.date}">${fmtDateLong(r.date)}</option>`).join("");
    teamSel.addEventListener("change", () => showTeam(teamSel.value));
    showTeam(teamReports[0].date);
  } else {
    document.getElementById("team-report").innerHTML =
      '<p class="empty">El informe de equipo se genera cada semana y aparecerá aquí.</p>';
  }

  // el contenido se monta tras cargar: el salto a #ancla hay que repetirlo ahora
  if (location.hash) {
    document.getElementById(location.hash.slice(1))?.scrollIntoView({ behavior: "smooth" });
  }
}
main();

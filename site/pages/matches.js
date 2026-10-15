/* Listado de partidas de la temporada. */

import {
  esc, fetchJSON, fmt, fmtDateShort, playerColor, renderNav, resultPill,
  scoreText, setUpdated, sortByDateDesc,
} from "../app.js";

function bestOfTeam(m, roster) {
  const ours = (m.players || []);
  if (!ours.length) return "—";
  const top = [...ours].sort((a, b) => (b.score ?? 0) - (a.score ?? 0))[0];
  const color = playerColor(top.name, roster);
  return `<span style="display:inline-flex;align-items:center;gap:8px">
    <span style="width:10px;height:10px;border-radius:3px;background:${color}"></span>
    <a href="player.html?name=${encodeURIComponent(top.name)}">${esc(top.name)}</a>
    <span style="color:var(--faint)">· ${fmt.format(top.score)}${top.mvp ? " ⭐" : ""}</span>
  </span>`;
}

async function main() {
  renderNav("match");
  const { data: summary } = await fetchJSON("data/summary.json");
  if (!summary) {
    document.getElementById("match-rows").innerHTML =
      '<tr><td colspan="6"><p class="empty">No se pudieron cargar los datos. Comprueba la conexión y recarga la página.</p></td></tr>';
    return;
  }
  setUpdated(summary);
  const matches = sortByDateDesc(summary.matches || []);
  const roster = summary.players || [];

  const wins = matches.filter((m) => m.result === "win").length;
  const losses = matches.filter((m) => m.result === "loss").length;
  document.getElementById("season-line").textContent =
    `${matches.length} ${matches.length === 1 ? "partida" : "partidas"} · ${wins} V — ${losses} D`;

  document.getElementById("match-rows").innerHTML = matches.map((m) => `
    <tr class="${m.result ?? ""}">
      <td>${fmtDateShort(m.date)}</td>
      <td>${esc(m.map ?? "—")}</td>
      <td class="num score-mono">${scoreText(m)}${m.overtime ? ' <span style="color:var(--faint);font-size:12px">OT</span>' : ""}</td>
      <td>${resultPill(m.result)}</td>
      <td>${bestOfTeam(m, roster)}</td>
      <td class="num" style="white-space:nowrap">
        <a href="match.html?id=${m.id}">Ver partida</a>
      </td>
    </tr>`).join("") ||
    '<tr><td colspan="6"><p class="empty">Aún no hay partidas: juega una y aparecerá aquí sola.</p></td></tr>';
}
main();

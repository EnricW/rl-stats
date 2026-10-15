/* Utilidades compartidas: carga de datos, formato, nav y gráficas.
   Módulo ES: cada página lo importa desde site/pages/<página>.js. */

export const fmt = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 });

// Colores de identidad por jugador: tokens --player-1..4 de styles.css
// (tonos propios que no chocan con --blue "nosotros" ni --orange "rivales").
let _playerColors = null;
function playerColors() {
  if (!_playerColors) {
    const css = getComputedStyle(document.documentElement);
    _playerColors = [1, 2, 3, 4].map(
      (i) => css.getPropertyValue(`--player-${i}`).trim() || "#8E6BE4"
    );
  }
  return _playerColors;
}

/* ---- carga de datos ----
   "no-cache" = revalidar siempre contra el servidor (ETag): GitHub Pages
   cachea 10 min y sin esto los datos recién desplegados tardan en aparecer.
   Devuelven {data, missing, failed}: "no existe" (404) y "falló la red" son
   cosas distintas y cada página muestra el mensaje que corresponde. */
async function fetchResource(path, parse) {
  try {
    const resp = await fetch(path, { cache: "no-cache" });
    if (resp.status === 404) return { data: null, missing: true, failed: false };
    if (!resp.ok) return { data: null, missing: false, failed: true };
    return { data: await parse(resp), missing: false, failed: false };
  } catch {
    return { data: null, missing: false, failed: true };
  }
}

export const fetchJSON = (path) => fetchResource(path, (r) => r.json());
export const fetchText = (path) => fetchResource(path, (r) => r.text());

// Mensaje de error de carga, para no dejar la página en blanco sin pistas.
export function loadError(el, what = "los datos") {
  if (el) el.innerHTML = `<p class="empty">No se pudieron cargar ${what}. Comprueba la conexión y recarga la página.</p>`;
}

// Aísla el pintado de una sección: si sus datos vienen con un campo de menos,
// esa sección muestra un aviso y el resto de la página sigue montándose.
export function safeRender(sectionId, fn) {
  try {
    fn();
  } catch (err) {
    console.error(`Error pintando #${sectionId}:`, err);
    const el = document.getElementById(sectionId);
    if (el) el.innerHTML = '<p class="empty">No se pudo mostrar esta sección.</p>';
  }
}

/* ---- formato ---- */

export function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-ES", {
    day: "2-digit", month: "short", year: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

export function fmtDateShort(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-ES", { day: "2-digit", month: "short" });
}

export function fmtDateLong(iso) {
  if (!iso) return "—";
  // una fecha sin hora ("2026-10-15") se interpretaría en UTC y en husos
  // negativos se mostraría el día anterior; se ancla a mediodía local
  const d = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T12:00:00`) : new Date(iso);
  return d.toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" });
}

export function fmtClock(totalSeconds) {
  const s = Math.max(0, Math.round(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export function resultPill(result, overtime) {
  const ot = overtime ? " · OT" : "";
  if (result === "win") return `<span class="res win">V${ot}</span>`;
  if (result === "loss") return `<span class="res loss">D${ot}</span>`;
  return '<span class="chip">—</span>';
}

// "nosotros" y "ellos" de una partida (se repetía en 5 sitios)
export function sides(match) {
  const us = match.our_team ?? "blue";
  return { us, them: us === "blue" ? "orange" : "blue" };
}

export function scoreText(match) {
  // marcador siempre "nosotros – ellos" cuando sabemos qué equipo somos
  const { score, our_team } = match;
  if (!our_team) return `${score.blue} – ${score.orange}`;
  const { us, them } = sides(match);
  return `${score[us]} – ${score[them]}`;
}

// Escape explícito de los 5 caracteres: esc() se usa también dentro de
// atributos HTML (title, data-*), donde las comillas sin escapar permitirían
// salirse del atributo (XSS con un nick de rival malicioso).
export function esc(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function avg(values) {
  return values.length ? values.reduce((a, b) => a + b, 0) / values.length : null;
}

export function sortByDateDesc(matches) {
  return [...matches].sort((a, b) => (b.date || "").localeCompare(a.date || ""));
}

// Rangos competitivos de ballchasing (id tipo "diamond-2") en español.
const RANK_ES = {
  "unranked": "Sin rango", "bronze": "Bronce", "silver": "Plata", "gold": "Oro",
  "platinum": "Platino", "diamond": "Diamante", "champion": "Campeón",
  "grand-champion": "Gran Campeón", "supersonic-legend": "Leyenda Supersónica",
};

export function rankLabel(rank, { division = false } = {}) {
  if (!rank?.id) return null;
  const m = String(rank.id).match(/^(.*?)(?:-(\d+))?$/);
  const base = RANK_ES[m[1]] ?? rank.name ?? rank.id;
  const tier = m[2] ? ` ${["I", "II", "III"][+m[2] - 1] ?? m[2]}` : "";
  const div = division && rank.division ? ` · div. ${rank.division}` : "";
  return base + tier + div;
}

export function playerColor(name, roster) {
  const colors = playerColors();
  const sorted = [...roster].sort((a, b) => a.localeCompare(b, "es"));
  const i = sorted.indexOf(name);
  return colors[i >= 0 ? i % colors.length : 0];
}

/* ---- componentes compartidos ---- */

export function tile(label, value, hint, cls = "") {
  return `<div class="tile"><span class="label">${label}</span>
    <span class="value ${cls}">${value}</span>
    ${hint ? `<span class="hint">${hint}</span>` : ""}</div>`;
}

export function setUpdated(summary) {
  const el = document.querySelector(".updated");
  if (el && summary) el.textContent = `Última sincronización · ${fmtDate(summary.generated_at)}`;
}

// Navegación común. `active`: "index" | "match" | "player".
export function renderNav(active) {
  const el = document.querySelector("nav.site");
  if (!el) return;
  const link = (href, key, label) =>
    `<a href="${href}" class="${active === key ? "active" : ""}"
        ${active === key ? 'aria-current="page"' : ""}>${label}</a>`;
  el.setAttribute("aria-label", "Navegación principal");
  el.innerHTML = `
    <a class="logo" href="index.html" aria-label="RL Stats">
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="var(--accent)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 3a15 15 0 0 1 0 18"></path><path d="M12 3a15 15 0 0 0 0 18"></path><path d="M3.5 9h17"></path><path d="M3.5 15h17"></path></svg>
      <b>RL<span>STATS</span></b>
    </a>
    <div class="links">
      ${link("index.html", "index", "Portada")}
      ${link("matches.html", "match", "Partidas")}
      ${link("player.html", "player", "Jugadores")}
    </div>
    <span class="spacer"></span>
    <span class="updated"></span>`;
}

/* ---- gráficas (Chart.js) ---- */

// Tokens de la paleta leídos del CSS: todas las gráficas y lienzos (radar,
// evolución, cronología, mapa de calor, visor) usan estos en lugar de
// colores a fuego que se desviaban de styles.css.
export function chartTokens() {
  const css = getComputedStyle(document.documentElement);
  const get = (name) => css.getPropertyValue(name).trim();
  return {
    seriesHi: get("--blue-hi"),
    blue: get("--blue"),
    blueHi: get("--blue-hi"),
    orange: get("--orange"),
    orangeHi: get("--orange-hi"),
    ink: get("--ink"),
    grid: get("--grid"),
    border: get("--border"),
    muted: get("--muted"),
    faint: get("--faint"),
    card2: get("--card-2"),
    fontBody: get("--font-body") || "Barlow",
  };
}

// Gráfica de línea multi-serie, con el mismo lenguaje visual que el radar:
// la serie activa en color pleno, el resto atenuado y la media del equipo en
// gris discontinuo. series = [{ label, values, color, kind }] con kind
// "active" | "dim" | "team". La leyenda es clicable (Chart.js oculta/muestra
// cada serie por defecto).
export function multiLineChart(canvas, labels, series, { unit = "" } = {}) {
  const t = chartTokens();
  const last = labels.length - 1;
  const datasets = series.map(({ label, values, color, kind }) => {
    if (kind === "team") {
      return {
        label, data: values,
        borderColor: t.faint, borderWidth: 1.5, borderDash: [6, 4],
        pointRadius: 0, pointHoverRadius: 4, pointBackgroundColor: t.faint,
        tension: 0.25, spanGaps: true, order: 3,
      };
    }
    const active = kind === "active";
    return {
      label, data: values,
      borderColor: active ? color : color + "59",
      backgroundColor: color,
      pointBackgroundColor: values.map((_, i) => (active && i === last ? t.seriesHi : color)),
      borderWidth: active ? 3 : 1.5,
      pointRadius: active ? values.map((_, i) => (i === last ? 5 : 3)) : 0,
      pointHoverRadius: active ? 7 : 5,
      tension: 0.25, spanGaps: true, order: active ? 0 : 1,
    };
  });
  return new Chart(canvas, {
    type: "line",
    data: { labels, datasets },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: {
          display: true, position: "top", align: "end",
          labels: { usePointStyle: true, pointStyle: "line", boxWidth: 24, color: t.muted, font: { family: t.fontBody, size: 13 } },
        },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmt.format(c.parsed.y)}${unit}` } },
      },
      scales: {
        x: { grid: { display: false }, border: { color: t.grid }, ticks: { color: t.faint, maxTicksLimit: 8, font: { family: t.fontBody } } },
        y: { grid: { color: t.grid }, border: { display: false }, ticks: { color: t.faint, maxTicksLimit: 5, font: { family: t.fontBody } } },
      },
    },
  });
}

/* ---- informe IA ---- */

// El markdown lo escribe la IA a partir de datos que incluyen nicks de
// rivales (texto de terceros), así que SIEMPRE se sanea antes de insertarlo.
export function mdToHTML(md) {
  // sin las librerías del CDN no hay parseo NI saneado: texto plano legible
  if (!window.marked || !window.DOMPurify) {
    return `<pre class="report-raw">${esc(md)}</pre>`;
  }
  return DOMPurify.sanitize(marked.parse(md));
}

export async function renderReport(container, path, emptyText) {
  const { data: md, failed } = await fetchText(path);
  if (!md) {
    container.innerHTML = `<p class="empty">${
      failed ? "No se pudo cargar el informe. Comprueba la conexión y recarga la página." : emptyText
    }</p>`;
    return;
  }
  container.innerHTML = mdToHTML(md);
}

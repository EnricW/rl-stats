/* Utilidades compartidas: carga de datos, formato, nav y gráficas. */

const fmt = new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1 });

// Colores de identidad por jugador (orden alfabético estable del roster).
const PLAYER_COLORS = ["#1E88D4", "#8E6BE4", "#C27425", "#4ADE80"];

// "no-cache" = revalidar siempre contra el servidor (ETag): GitHub Pages cachea
// 10 min y sin esto los datos recién desplegados tardan en aparecer.
// Devuelven null tanto si el archivo no existe como si falla la red o el
// parseo: las páginas deciden qué mostrar (estado vacío o mensaje de error).
async function fetchJSON(path) {
  try {
    const resp = await fetch(path, { cache: "no-cache" });
    if (!resp.ok) return null;
    return await resp.json();
  } catch {
    return null;
  }
}

async function fetchText(path) {
  try {
    const resp = await fetch(path, { cache: "no-cache" });
    if (!resp.ok) return null;
    return await resp.text();
  } catch {
    return null;
  }
}

// Mensaje de error de carga, para no dejar la página en blanco sin pistas.
function loadError(el, what = "los datos") {
  if (el) el.innerHTML = `<p class="empty">No se pudieron cargar ${what}. Comprueba la conexión y recarga la página.</p>`;
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-ES", {
    day: "2-digit", month: "short", year: "2-digit", hour: "2-digit", minute: "2-digit",
  });
}

function fmtDateShort(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-ES", { day: "2-digit", month: "short" });
}

function fmtDateLong(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("es-ES", { day: "2-digit", month: "short", year: "numeric" });
}

function fmtClock(totalSeconds) {
  const s = Math.max(0, Math.round(totalSeconds));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

function resultPill(result, overtime) {
  const ot = overtime ? " · OT" : "";
  if (result === "win") return `<span class="res win">V${ot}</span>`;
  if (result === "loss") return `<span class="res loss">D${ot}</span>`;
  return '<span class="chip">—</span>';
}

function scoreText(match) {
  // marcador siempre "nosotros – ellos" cuando sabemos qué equipo somos
  const { score, our_team: us } = match;
  if (!us) return `${score.blue} – ${score.orange}`;
  const them = us === "blue" ? "orange" : "blue";
  return `${score[us]} – ${score[them]}`;
}

// Escape explícito de los 5 caracteres: esc() se usa también dentro de
// atributos HTML (title, data-*), donde las comillas sin escapar permitirían
// salirse del atributo (XSS con un nick de rival malicioso).
function esc(text) {
  return String(text ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

// Rangos competitivos de ballchasing (id tipo "diamond-2") en español.
const RANK_ES = {
  "unranked": "Sin rango", "bronze": "Bronce", "silver": "Plata", "gold": "Oro",
  "platinum": "Platino", "diamond": "Diamante", "champion": "Campeón",
  "grand-champion": "Gran Campeón", "supersonic-legend": "Leyenda Supersónica",
};

function rankLabel(rank, { division = false } = {}) {
  if (!rank?.id) return null;
  const m = String(rank.id).match(/^(.*?)(?:-(\d+))?$/);
  const base = RANK_ES[m[1]] ?? rank.name ?? rank.id;
  const tier = m[2] ? ` ${["I", "II", "III"][+m[2] - 1] ?? m[2]}` : "";
  const div = division && rank.division ? ` · div. ${rank.division}` : "";
  return base + tier + div;
}

function playerColor(name, roster) {
  const sorted = [...roster].sort((a, b) => a.localeCompare(b, "es"));
  const i = sorted.indexOf(name);
  return PLAYER_COLORS[i >= 0 ? i % PLAYER_COLORS.length : 0];
}

function setUpdated(summary) {
  const el = document.querySelector(".updated");
  if (el && summary) el.textContent = `Última sincronización · ${fmtDate(summary.generated_at)}`;
}

// Navegación común. `active`: "index" | "match" | "player".
function renderNav(active) {
  const el = document.querySelector("nav.site");
  if (!el) return;
  const link = (href, key, label) =>
    `<a href="${href}" class="${active === key ? "active" : ""}">${label}</a>`;
  el.innerHTML = `
    <a class="logo" href="index.html" aria-label="RL Stats">
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#55C1FF" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"></circle><path d="M12 3a15 15 0 0 1 0 18"></path><path d="M12 3a15 15 0 0 0 0 18"></path><path d="M3.5 9h17"></path><path d="M3.5 15h17"></path></svg>
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

function chartTokens() {
  const css = getComputedStyle(document.documentElement);
  return {
    seriesHi: css.getPropertyValue("--blue-hi").trim(),
    grid: css.getPropertyValue("--grid").trim(),
    muted: css.getPropertyValue("--muted").trim(),
    faint: css.getPropertyValue("--faint").trim(),
  };
}

// Gráfica de línea multi-serie, con el mismo lenguaje visual que el radar:
// la serie activa en color pleno, el resto atenuado y la media del equipo en
// gris discontinuo. series = [{ label, values, color, kind }] con kind
// "active" | "dim" | "team". La leyenda es clicable (Chart.js oculta/muestra
// cada serie de serie por defecto).
function multiLineChart(canvas, labels, series, { unit = "" } = {}) {
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
          labels: { usePointStyle: true, pointStyle: "line", boxWidth: 24, color: t.muted, font: { family: "Barlow", size: 13 } },
        },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${fmt.format(c.parsed.y)}${unit}` } },
      },
      scales: {
        x: { grid: { display: false }, border: { color: t.grid }, ticks: { color: t.faint, maxTicksLimit: 8, font: { family: "Barlow" } } },
        y: { grid: { color: t.grid }, border: { display: false }, ticks: { color: t.faint, maxTicksLimit: 5, font: { family: "Barlow" } } },
      },
    },
  });
}

/* ---- informe IA ---- */

// El markdown lo escribe la IA a partir de datos que incluyen nicks de
// rivales (texto de terceros), así que SIEMPRE se sanea antes de insertarlo.
function mdToHTML(md) {
  // sin las librerías del CDN no hay parseo NI saneado: texto plano legible
  if (!window.marked || !window.DOMPurify) {
    return `<pre class="report-raw">${esc(md)}</pre>`;
  }
  return DOMPurify.sanitize(marked.parse(md));
}

async function renderReport(container, path, emptyText) {
  const md = await fetchText(path);
  if (!md) {
    container.innerHTML = `<p class="empty">${emptyText}</p>`;
    return;
  }
  container.innerHTML = mdToHTML(md);
}

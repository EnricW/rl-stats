/* Visor de repeticiones: reproduce data/frames/<id>.json con three.js.
   Vista 3D orbital (sigue la bola) y vista aérea 2D, conmutables. */

const TEAM_COLORS = { 0: 0x2e9fe6, 1: 0xe8923b };
const TEAM_EMISSIVE = { 0: 0x16425f, 1: 0x4a2d10 };
const TEAM_HI = { 0: "#55C1FF", 1: "#F0A24A" };
const BOOST_YELLOW = 0xffc53d;

// RL: x ancho (±4096), y largo (±5120, porterías), z altura. three.js: y arriba.
const rl2three = (x, y, z) => [x, z, -y];

/* Etiqueta por coche: nombre + barra de boost, siempre de cara a la cámara
   e independiente de la rotación del coche (flota en la escena, no en él). */
function makeCarLabel(player) {
  const canvas = document.createElement("canvas");
  canvas.width = 256; canvas.height = 96;
  const ctx = canvas.getContext("2d");
  const tex = new THREE.CanvasTexture(canvas);
  let lastBoost = -1;

  function draw(boost) {
    ctx.clearRect(0, 0, 256, 96);
    ctx.font = "700 34px Barlow, sans-serif";
    ctx.textAlign = "center";
    ctx.lineWidth = 6;
    ctx.strokeStyle = "rgba(10,14,22,.9)";
    ctx.strokeText(player.name, 128, 40);
    ctx.fillStyle = TEAM_HI[player.team];
    ctx.fillText(player.name, 128, 40);
    // barra de boost
    const w = 140, h = 12, x = (256 - w) / 2, y = 58;
    ctx.fillStyle = "rgba(10,14,22,.85)";
    ctx.strokeStyle = "rgba(85,100,130,.8)";
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.roundRect(x, y, w, h, 6); ctx.fill(); ctx.stroke();
    if (boost > 0) {
      ctx.fillStyle = "#FFC53D";
      ctx.beginPath();
      ctx.roundRect(x + 2, y + 2, Math.max(4, (w - 4) * (boost / 100)), h - 4, 4);
      ctx.fill();
    }
    tex.needsUpdate = true;
  }
  draw(33);

  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, depthTest: false }));
  sprite.scale.set(860, 322, 1);
  sprite.update = (boost) => {
    const b = Math.round(boost ?? 0);
    if (b !== lastBoost) { lastBoost = b; draw(b); }
  };
  return sprite;
}

function buildField(scene, pads) {
  const W = 8192, L = 10240, H = 2044;
  const floor = new THREE.Mesh(
    new THREE.PlaneGeometry(W, L),
    new THREE.MeshLambertMaterial({ color: 0x0f1522 })
  );
  floor.rotation.x = -Math.PI / 2;
  scene.add(floor);

  const lines = new THREE.LineSegments(
    new THREE.BufferGeometry(),
    new THREE.LineBasicMaterial({ color: 0x26324a })
  );
  const pts = [];
  const seg = (x1, y1, x2, y2) => pts.push(x1, 2, y1, x2, 2, y2);
  seg(-W / 2, -L / 2, W / 2, -L / 2); seg(-W / 2, L / 2, W / 2, L / 2);
  seg(-W / 2, -L / 2, -W / 2, L / 2); seg(W / 2, -L / 2, W / 2, L / 2);
  seg(-W / 2, 0, W / 2, 0);
  for (let i = 0; i < 48; i++) {
    const a1 = (i / 48) * Math.PI * 2, a2 = ((i + 1) / 48) * Math.PI * 2;
    seg(Math.cos(a1) * 1150, Math.sin(a1) * 1150, Math.cos(a2) * 1150, Math.sin(a2) * 1150);
  }
  // áreas de portería
  seg(-2500, -L / 2, -2500, -L / 2 + 1150); seg(2500, -L / 2, 2500, -L / 2 + 1150);
  seg(-2500, -L / 2 + 1150, 2500, -L / 2 + 1150);
  seg(-2500, L / 2, -2500, L / 2 - 1150); seg(2500, L / 2, 2500, L / 2 - 1150);
  seg(-2500, L / 2 - 1150, 2500, L / 2 - 1150);
  lines.geometry.setAttribute("position", new THREE.Float32BufferAttribute(pts, 3));
  scene.add(lines);

  // porterías (el equipo 0/azul defiende y negativo en RL -> z positivo en three)
  for (const [zEnd, color] of [[L / 2, TEAM_COLORS[0]], [-L / 2, TEAM_COLORS[1]]]) {
    const goal = new THREE.LineSegments(
      new THREE.EdgesGeometry(new THREE.BoxGeometry(1786, 643, 880)),
      new THREE.LineBasicMaterial({ color })
    );
    goal.position.set(0, 321, zEnd + (zEnd > 0 ? 440 : -440));
    scene.add(goal);
  }

  // pads de boost del propio replay (34 en campos estándar); amarillo boost
  const bigMat = new THREE.MeshLambertMaterial({ color: BOOST_YELLOW, emissive: 0x6b4e12 });
  const smallMat = new THREE.MeshLambertMaterial({ color: 0x9a7c2a, emissive: 0x2e2308 });
  const fallback = [[-3584, 0, 1], [3584, 0, 1], [-3072, 4096, 1], [3072, 4096, 1], [-3072, -4096, 1], [3072, -4096, 1]];
  for (const [bx, by, big] of (pads && pads.length ? pads : fallback)) {
    const pad = new THREE.Mesh(
      big ? new THREE.CylinderGeometry(110, 110, 30, 18) : new THREE.CylinderGeometry(52, 52, 12, 12),
      big ? bigMat : smallMat
    );
    const [px, py, pz] = rl2three(bx, by, big ? 16 : 7);
    pad.position.set(px, py, pz);
    scene.add(pad);
  }

  const walls = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(W, H, L)),
    new THREE.LineBasicMaterial({ color: 0x1c2434 })
  );
  walls.position.y = H / 2;
  scene.add(walls);
}

function buildCar(player) {
  const group = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(118, 36, 84),
    new THREE.MeshLambertMaterial({ color: TEAM_COLORS[player.team], emissive: TEAM_EMISSIVE[player.team] })
  );
  body.position.y = 18;
  const cabin = new THREE.Mesh(
    new THREE.BoxGeometry(50, 22, 60),
    new THREE.MeshLambertMaterial({ color: 0x1a2232, emissive: 0x0a0e16 })
  );
  cabin.position.set(-12, 42, 0);
  const nose = new THREE.Mesh(
    new THREE.BoxGeometry(26, 10, 40),
    new THREE.MeshBasicMaterial({ color: 0xffffff })
  );
  nose.position.set(52, 32, 0);

  // llama de boost en la trasera (visible solo cuando gasta boost)
  const flame = new THREE.Mesh(
    new THREE.ConeGeometry(17, 80, 10),
    new THREE.MeshBasicMaterial({ color: BOOST_YELLOW, transparent: true, opacity: 0.9 })
  );
  flame.rotation.z = Math.PI / 2; // apunta hacia -x (detrás del coche)
  flame.position.set(-100, 20, 0);
  flame.visible = false;

  group.add(body, cabin, nose, flame);
  group.scale.setScalar(1.4);
  group.flame = flame;
  return group;
}

function lerp(a, b, k) { return a + (b - a) * k; }
function lerpAngle(a, b, k) {
  let d = b - a;
  while (d > Math.PI) d -= Math.PI * 2;
  while (d < -Math.PI) d += Math.PI * 2;
  return a + d * k;
}

function initMatchViewer(root, data) {
  const stage = root.querySelector(".viewer-stage");
  const playBtn = root.querySelector(".play-btn");
  const scrub = root.querySelector('input[type="range"]');
  const scrubWrap = root.querySelector(".scrub-wrap");
  const timeEl = root.querySelector(".viewer-time");
  const speedBtn = root.querySelector(".speed-btn");
  const viewBtn = root.querySelector(".view-btn");
  const hudBlue = root.querySelector(".viewer-hud .b");
  const hudOrange = root.querySelector(".viewer-hud .o");
  const hudClock = root.querySelector(".viewer-hud .clock");
  const goalBanner = root.querySelector(".viewer-goal");

  const fps = data.fps;
  const frames = data.ball.length;
  const duration = frames / fps;

  // segmentos de fase (0 cuenta atrás, 1 juego, 2 gol/repetición): inicio y
  // fin en segundos de cada tramo, por frame, para la capa central
  const phases = data.phase || [];
  const segStart = new Array(frames).fill(0);
  const segEnd = new Array(frames).fill(duration);
  if (phases.length === frames) {
    let s = 0;
    for (let i = 1; i <= frames; i++) {
      if (i === frames || phases[i] !== phases[s]) {
        for (let k = s; k < i; k++) { segStart[k] = s / fps; segEnd[k] = i / fps; }
        s = i;
      }
    }
  }

  // fin de la parte reglamentaria (para mostrar +OT): primer frame con reloj a 0
  let regEnd = duration;
  for (let i = 1; i < data.clock.length; i++) {
    if (data.clock[i] === 0 && data.clock[i - 1] > 0) { regEnd = i / fps; break; }
  }

  /* escena */
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0a0e16);
  scene.add(new THREE.HemisphereLight(0x99aacc, 0x10141f, 1.5));
  const sun = new THREE.DirectionalLight(0xffffff, 1.6);
  sun.position.set(3000, 6000, 2000);
  scene.add(sun);
  buildField(scene, data.pads);

  const ball = new THREE.Mesh(
    new THREE.SphereGeometry(93, 24, 18),
    new THREE.MeshLambertMaterial({ color: 0xedf2fa, emissive: 0x44566e })
  );
  scene.add(ball);

  const cars = data.players.map((p) => {
    const car = buildCar(p);
    scene.add(car);
    return car;
  });

  // explosión de gol: ráfaga de partículas desde la bola
  const PARTICLE_N = 42;
  const boomGeo = new THREE.BufferGeometry();
  boomGeo.setAttribute("position",
    new THREE.Float32BufferAttribute(new Float32Array(PARTICLE_N * 3), 3));
  const boomMat = new THREE.PointsMaterial({
    color: 0xffffff, size: 90, transparent: true, opacity: 0, depthWrite: false,
  });
  const boom = new THREE.Points(boomGeo, boomMat);
  boom.visible = false;
  scene.add(boom);
  const boomState = { life: -1, vel: [] };
  function explode(pos, color) {
    boomMat.color.set(color);
    boomState.life = 0;
    boomState.vel = [];
    const attr = boomGeo.attributes.position;
    for (let p = 0; p < PARTICLE_N; p++) {
      attr.setXYZ(p, pos.x, pos.y, pos.z);
      const a = Math.random() * Math.PI * 2;
      const b = Math.random() * Math.PI - Math.PI / 2;
      const v = 1400 + Math.random() * 1800;
      boomState.vel.push([
        Math.cos(a) * Math.cos(b) * v,
        Math.abs(Math.sin(b)) * v + 500,
        Math.sin(a) * Math.cos(b) * v,
      ]);
    }
    attr.needsUpdate = true;
    boom.visible = true;
  }
  function boomUpdate(dt) {
    if (boomState.life < 0) return;
    boomState.life += dt;
    if (boomState.life > 1.2) { boomState.life = -1; boom.visible = false; return; }
    const attr = boomGeo.attributes.position;
    for (let p = 0; p < PARTICLE_N; p++) {
      const v = boomState.vel[p];
      attr.setXYZ(p, attr.getX(p) + v[0] * dt, Math.max(40, attr.getY(p) + v[1] * dt), attr.getZ(p) + v[2] * dt);
      v[1] -= 2600 * dt; // gravedad
    }
    attr.needsUpdate = true;
    boomMat.opacity = Math.max(0, 1 - boomState.life / 1.2);
  }
  // etiquetas flotantes (nombre + boost), fuera del coche para no heredar giros
  const labels = data.players.map((p) => {
    const label = makeCarLabel(p);
    scene.add(label);
    return label;
  });

  const camera3d = new THREE.PerspectiveCamera(50, 16 / 9, 10, 60000);
  const camera2d = new THREE.OrthographicCamera(-1, 1, 1, -1, 10, 30000);
  camera2d.position.set(0, 16000, 0);
  camera2d.up.set(0, 0, -1); // arriba de la pantalla = portería rival
  camera2d.lookAt(0, 0, 0);
  let view2d = false;

  const renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  stage.prepend(renderer.domElement);

  function fitOrtho() {
    const aspect = camera3d.aspect;
    let halfH = 5500, halfW = halfH * aspect;
    if (halfW < 4400) { halfW = 4400; halfH = halfW / aspect; }
    camera2d.left = -halfW; camera2d.right = halfW;
    camera2d.top = halfH; camera2d.bottom = -halfH;
    camera2d.updateProjectionMatrix();
  }

  function resize() {
    const w = stage.clientWidth;
    const h = Math.min(560, Math.max(280, Math.round(w * 0.56)));
    renderer.setSize(w, h);
    camera3d.aspect = w / h;
    camera3d.updateProjectionMatrix();
    fitOrtho();
  }
  resize();
  window.addEventListener("resize", () => { resize(); needsRender = true; });

  // render bajo demanda: en pausa y sin interacción no se repinta (ahorra
  // GPU y batería; el bucle rAF sigue vivo pero sin trabajo)
  let needsRender = true;

  /* cámara 3D orbital que sigue la bola */
  const orbit = { azimuth: Math.PI * 0.5, polar: 0.95, radius: 9000 };
  const target = new THREE.Vector3(0, 300, 0);
  let dragging = false, lastX = 0, lastY = 0;
  stage.addEventListener("pointerdown", (e) => { dragging = true; lastX = e.clientX; lastY = e.clientY; });
  window.addEventListener("pointerup", () => { dragging = false; });
  window.addEventListener("pointermove", (e) => {
    if (!dragging || view2d) return;
    orbit.azimuth -= (e.clientX - lastX) * 0.005;
    orbit.polar = Math.min(1.35, Math.max(0.25, orbit.polar - (e.clientY - lastY) * 0.004));
    lastX = e.clientX; lastY = e.clientY;
    needsRender = true;
  });
  stage.addEventListener("wheel", (e) => {
    if (view2d) return;
    e.preventDefault();
    orbit.radius = Math.min(16000, Math.max(2500, orbit.radius * (1 + e.deltaY * 0.001)));
    needsRender = true;
  }, { passive: false });

  if (viewBtn) {
    viewBtn.addEventListener("click", () => {
      view2d = !view2d;
      viewBtn.textContent = view2d ? "3D" : "2D";
      viewBtn.setAttribute("aria-label", view2d ? "Cambiar a vista 3D" : "Cambiar a vista aérea 2D");
      needsRender = true;
    });
  }

  /* reproducción */
  const state = { t: 0, playing: false, speed: 1 };
  scrub.max = String(frames - 1);

  // marcas de gol en el scrubber
  for (const g of data.goals) {
    const tick = document.createElement("span");
    tick.className = "scrub-goal";
    tick.style.left = `${(g.t / duration) * 100}%`;
    tick.style.background = TEAM_HI[g.team];
    tick.title = `Gol de ${g.name}`;
    scrubWrap.appendChild(tick);
  }

  const ICON_PLAY = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><polygon points="7 4 21 12 7 20 7 4"></polygon></svg>';
  const ICON_PAUSE = '<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>';

  function setPlaying(on) {
    state.playing = on;
    playBtn.innerHTML = on ? ICON_PAUSE : ICON_PLAY;
    playBtn.setAttribute("aria-label", on ? "Pausar" : "Reproducir");
  }
  playBtn.addEventListener("click", () => { setPlaying(!state.playing); needsRender = true; });
  scrub.addEventListener("input", () => { state.t = Number(scrub.value) / fps; needsRender = true; });
  speedBtn.addEventListener("click", () => {
    state.speed = state.speed >= 4 ? 1 : state.speed * 2;
    speedBtn.textContent = `×${state.speed}`;
  });

  // texto central (3-2-1, GO!, GOAL, GOAL REPLAY); la clave evita reiniciar
  // la animación en cada frame
  const centerEl = root.querySelector(".viewer-center span");
  let centerKey = "";
  function centerShow(key, text, mode) {
    if (key === centerKey) return;
    centerKey = key;
    centerEl.textContent = text;
    centerEl.className = "";
    if (key) {
      void centerEl.offsetWidth; // reinicia la animación CSS
      centerEl.className = mode;
    }
  }

  let bannerUntil = -1;
  let lastT = null;
  function applyFrame(now) {
    const ft = Math.min(state.t * fps, frames - 1.001);
    const i = Math.floor(ft), k = ft - i, j = Math.min(i + 1, frames - 1);

    const b0 = data.ball[i], b1 = data.ball[j];
    if (b0[0] != null && b1[0] != null) {
      const [bx, by, bz] = rl2three(lerp(b0[0], b1[0], k), lerp(b0[1], b1[1], k), lerp(b0[2], b1[2], k));
      ball.position.set(bx, Math.max(by, 93), bz);
    }

    cars.forEach((car, c) => {
      const f0 = data.cars[c][i], f1 = data.cars[c][j];
      const label = labels[c];
      if (f0[0] == null || f1[0] == null) { car.visible = false; label.visible = false; return; }
      car.visible = true; label.visible = true;
      const [x, y, z] = rl2three(lerp(f0[0], f1[0], k), lerp(f0[1], f1[1], k), lerp(f0[2], f1[2], k));
      car.position.set(x, Math.max(y - 17, 0), z);
      car.rotation.order = "YXZ";
      car.rotation.y = lerpAngle(f0[5] ?? 0, f1[5] ?? 0, k);
      car.rotation.x = lerp(f0[3] ?? 0, f1[3] ?? 0, k);
      car.rotation.z = lerp(f0[4] ?? 0, f1[4] ?? 0, k);

      // etiqueta flotante sobre el coche, sin heredar su rotación
      label.position.set(x, car.position.y + 340, z);
      const ls = view2d ? 1.6 : 1; // en la vista aérea el campo entero está a la vista
      label.scale.set(860 * ls, 322 * ls, 1);
      label.update(f0[6]);

      // llama cuando gasta boost (el nivel baja respecto al frame siguiente)
      const burning = f0[6] != null && f1[6] != null && f1[6] < f0[6];
      car.flame.visible = burning;
      if (burning) {
        const flick = 0.75 + 0.45 * Math.abs(Math.sin(now * 0.04 + c));
        car.flame.scale.set(1, flick, 1);
      }
    });

    // cámara 3D: sigue la bola con suavidad
    target.lerp(new THREE.Vector3(
      THREE.MathUtils.clamp(ball.position.x, -2800, 2800), 200,
      THREE.MathUtils.clamp(ball.position.z, -3600, 3600)), 0.04);
    camera3d.position.set(
      target.x + orbit.radius * Math.sin(orbit.polar) * Math.cos(orbit.azimuth),
      target.y + orbit.radius * Math.cos(orbit.polar),
      target.z + orbit.radius * Math.sin(orbit.polar) * Math.sin(orbit.azimuth));
    camera3d.lookAt(target);

    // HUD: marcador, reloj y aviso de gol
    let score = [0, 0], lastGoal = null;
    for (const g of data.goals) if (g.t <= state.t) { score = g.score; lastGoal = g; }
    hudBlue.textContent = score[0];
    hudOrange.textContent = score[1];
    const ot = state.t > regEnd + 0.5;
    hudClock.textContent = ot ? `+${fmtClock(state.t - regEnd)}` : fmtClock(data.clock[i] ?? 0);
    if (lastGoal && state.t - lastGoal.t < 3) {
      goalBanner.querySelector("span").innerHTML =
        `GOL · <span style="color:${TEAM_HI[lastGoal.team]}">${esc(lastGoal.name)}</span>`;
      goalBanner.classList.add("show");
      bannerUntil = lastGoal.t + 3;
    } else if (state.t > bannerUntil) {
      goalBanner.classList.remove("show");
    }

    // capa central según la fase del juego
    if (phases.length === frames) {
      const ph = phases[i];
      if (ph === 0) {
        // la cuenta atrás real son los últimos 3 s del tramo (antes hay una
        // breve espera a que los jugadores estén listos): 3 en -3, 2 en -2, 1 en -1
        const remaining = segEnd[i] - state.t;
        if (remaining <= 3.05) {
          const n = Math.max(1, Math.ceil(remaining - 0.05));
          centerShow(`cd${n}@${segStart[i]}`, String(n), "pop");
        } else {
          centerShow("", "", "");
        }
      } else if (ph === 2) {
        if (state.t - segStart[i] < 2.6) centerShow(`goal@${segStart[i]}`, "GOAL", "pop");
        else centerShow(`rep@${segStart[i]}`, "GOAL REPLAY", "hold");
      } else {
        const sIdx = Math.round(segStart[i] * fps);
        if (sIdx > 0 && phases[sIdx - 1] === 0 && state.t - segStart[i] < 1) {
          centerShow(`go@${sIdx}`, "GO!", "pop");
        } else {
          centerShow("", "", "");
        }
      }
    }

    // explosión al cruzar el momento exacto de un gol (reproduciendo, no al saltar)
    if (lastT != null && state.t > lastT && state.t - lastT < 0.5) {
      for (const g of data.goals) {
        if (lastT < g.t && state.t >= g.t) explode(ball.position, TEAM_HI[g.team]);
      }
    }
    lastT = state.t;

    scrub.value = String(Math.round(ft));
    timeEl.innerHTML = `${fmtClock(state.t)} <span>/ ${fmtClock(duration)}</span>`;
  }

  let prev = performance.now();
  function loop(now) {
    const dt = (now - prev) / 1000;
    prev = now;
    if (state.playing) {
      state.t += dt * state.speed;
      if (state.t >= duration) { state.t = duration; setPlaying(false); }
    }
    // la explosión de gol en curso sigue animándose aunque se pause justo ahí
    if (state.playing || needsRender || boomState.life >= 0) {
      applyFrame(now);
      boomUpdate(Math.min(dt, 0.1) * state.speed);
      renderer.render(scene, view2d ? camera2d : camera3d);
      needsRender = false;
    }
    requestAnimationFrame(loop);
  }
  applyFrame(performance.now());
  requestAnimationFrame(loop);
}

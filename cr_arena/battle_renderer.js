/* Shared battle graphics for live play and standalone saved replays.
 * Coordinates and radii in the drawing contract are tiles, Blue at the bottom.
 * en: [uid, team, kind, card, x, y, hp, maxHp, radius, flags, towerSlot, facingX, facingY, stunTicks, footprint,
 *      shield, statusFlags, charge]
 * footprint: optional [x0, y0, x1, y1] in tiles. shield: shield hp left (0 none). statusFlags: the engine's
 * status bits, -1 when not reported. charge: build-up in permille, -1 when not reported.
 * sp: [team, card, x, y, aimX, aimY, motionName]; pr: [team, x, y]
 * flags: bit 0 flying, bit 1 deploying. Missing optional fields are supported for old traces.
 */
(() => {
  "use strict";
  const C = Object.freeze({
    blue: "#3b8ef0",
    blueDk: "#1c4f96",
    red: "#f0703c",
    redDk: "#9a3a14",
    grassA: "#75ad4d",
    grassB: "#6ca346",
    water: "#358cb9",
    bridge: "#a87540",
    gold: "#f2c230",
  });
  const KING = 2,
    PRINCESS = 3,
    BUILDING = 1;
  // One picture per card (system emoji, our own choice of symbols), so a unit can be told apart at a glance.
  const ICON = {
    Knight: "⚔️",
    Archer: "🏹",
    Giant: "🦍",
    Pekka: "🤖",
    Minions: "😈",
    Balloon: "🎈",
    Golem: "🗿",
    Skeletons: "💀",
    Musketeer: "🔫",
    BabyDragon: "🐉",
    Wizard: "🧙",
    MiniPekka: "🦾",
    HogRider: "🐗",
    Princess: "👸",
    LavaHound: "🌋",
    IceSpirits: "❄️",
    BattleRam: "🐏",
    IceGolemite: "🧊",
    MegaMinion: "👿",
    GoblinGang: "👺",
    ElectroWizard: "⚡",
    Bats: "🦇",
    Cannon: "💣",
    InfernoTower: "🔥",
    Tesla: "🔌",
    Xbow: "🎯",
    Tombstone: "🪦",
    Fireball: "☄️",
    Arrows: "🎯",
    Rocket: "🚀",
    GoblinBarrel: "🛢️",
    Lightning: "🌩️",
    Zap: "⚡",
    Poison: "☠️",
    Log: "🪵",
    Goblins: "👺",
    SpearGoblins: "👺",
    LavaPups: "🔥",
    Golemite: "🗿",
    Barbarians: "🪓",
    Skeleton: "💀",
    Goblin: "👺",
    Bat: "🦇",
    Minion: "😈",
  };
  const iconOf = (name) => ICON[name] || ICON[name.replace(/s$/, "")] || "";

  const pretty = (n) => n.replace(/([a-z])([A-Z])/g, "$1 $2");
  const lerp = (a, b, t) => a + (b - a) * t;
  const isFlight = (s) => !s[6] || s[6] === "FLIGHT" || s[6] === "AIRBORNE";
  const spKey = (sp) => sp[0] + "|" + sp[1] + "|" + sp[4] + "|" + sp[5];

  const grain = (x, y) => ((x * 73 + y * 151 + x * y * 17) % 101) / 101;
  // deterministic 0..1 scatter, so a seek redraws the same picture
  const hash = (n) => {
    const v = Math.sin(n * 127.1 + 311.7) * 43758.5453;
    return v - Math.floor(v);
  };
  // The classic-deck spells with their own travel, landing and impact art.
  const SPELL_ART = new Set(["Arrows", "Fireball", "GoblinBarrel", "Lightning", "Log", "Poison", "Rocket", "Zap"]);

  function create(canvas, arena) {
    const ctx = canvas.getContext("2d"),
      TX = arena.tiles_x,
      TY = arena.tiles_y;
    let T = 16,
      flip = false,
      cards = {},
      fx = [],
      firstSeen = new Map(),
      hitAt = new Map(),
      shieldMax = new Map(),
      spellFrom = new Map(),
      spellSeen = new Map();
    let previous = null,
      drawn = [];
    const X = (tx) => (flip ? TX - tx : tx) * T;
    const Y = (ty) => (flip ? ty : TY - ty) * T;
    function reset() {
      previous = null;
      fx = [];
      firstSeen.clear();
      hitAt.clear();
      shieldMax.clear();
      spellFrom.clear();
      spellSeen.clear();
    }
    function observe(s, now) {
      s.by = new Map(s.en.map((e) => [e[0], e]));
      const prev = previous;
      if (prev) {
        for (const [uid, e] of prev.by) {
          const n = s.by.get(uid);
          if (!n)
            fx.push({
              kind: "die",
              x: e[4],
              y: e[5],
              r: e[8],
              team: e[1],
              at: now,
            });
          else if (n[6] < e[6] || (n[15] || 0) < (e[15] || 0)) hitAt.set(uid, now);
        }
      }
      for (const e of s.en) {
        if (!firstSeen.has(e[0])) firstSeen.set(e[0], prev ? now : -1e9);
        // the bar shows the shield left against the most it has been
        if (e[15] > (shieldMax.get(e[0]) || 0)) shieldMax.set(e[0], e[15]);
      }
      s.spBy = new Map(s.sp.map((sp) => [spKey(sp), sp]));
      // Every row per key: one Arrows cast is three volleys that share a key.
      s.spAll = new Map();
      for (const sp of s.sp) {
        const k = spKey(sp);
        if (!s.spAll.has(k)) s.spAll.set(k, []);
        s.spAll.get(k).push(sp);
      }
      for (const [k, sp] of s.spBy) {
        if (!spellFrom.has(k)) spellFrom.set(k, [sp[2], sp[3]]);
        if (!spellSeen.has(k)) spellSeen.set(k, now);
      }
      if (prev)
        for (const [k, sp] of prev.spBy)
          if (!s.spBy.has(k)) {
            // a travelling spell has arrived
            spellFrom.delete(k);
            spellSeen.delete(k);
            if (isFlight(sp))
              fx.push({
                kind: "boom",
                x: sp[4],
                y: sp[5],
                team: sp[0],
                card: sp[1],
                at: now,
              });
          } else if (isFlight(sp) && (prev.spAll?.get(k)?.length || 0) > s.spAll.get(k).length) {
            // an earlier volley of the same cast has landed; only spell art draws this
            fx.push({ kind: "land", x: sp[4], y: sp[5], team: sp[0], card: sp[1], at: now });
          }

      previous = s;
    }
    function drawGround() {
      const half = arena.half,
        grid = arena.grid,
        water = arena.water_half_rows,
        cell = T / half;
      ctx.fillStyle = "#344b2b";
      ctx.fillRect(0, 0, TX * T, TY * T);
      // The mown field is drawn at tile resolution; only the river needs the
      // simulator's finer grid. This keeps the terrain inexpensive to redraw.
      for (let ty = 0; ty < TY; ty++)
        for (let tx = 0; tx < TX; tx++) {
          const px = Math.min(X(tx), X(tx + 1)),
            py = Math.min(Y(ty), Y(ty + 1));
          ctx.fillStyle = (tx + ty) % 2 ? C.grassA : C.grassB;
          ctx.fillRect(px, py, T + 0.5, T + 0.5);
          ctx.fillStyle = "rgba(235,255,174,.11)";
          ctx.fillRect(px + 1, py + 1, T - 2, Math.max(1, T * 0.09));
          if (grain(tx, ty) > 0.58) {
            ctx.strokeStyle = "rgba(35,93,35,.32)";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(px + T * 0.33, py + T * 0.75);
            ctx.lineTo(px + T * 0.25, py + T * 0.52);
            ctx.moveTo(px + T * 0.33, py + T * 0.75);
            ctx.lineTo(px + T * 0.43, py + T * 0.55);
            ctx.stroke();
          }
        }
      for (let hy = water[0]; hy <= water[1]; hy++)
        for (let hx = 0; hx < grid[hy].length; hx++) {
          const v = grid[hy][hx],
            x = Math.min(X(hx / half), X((hx + 1) / half)),
            y = Math.min(Y(hy / half), Y((hy + 1) / half)),
            bridge = !(v & arena.bits.WATER);
          ctx.fillStyle = bridge
            ? (hy + hx) % 3 ? "#ac7a43" : "#ba8950"
            : (hy + hx) % 3 ? C.water : "#419bc4";
          ctx.fillRect(x, y, cell + 0.6, cell + 0.6);
          if (bridge) {
            ctx.fillStyle = "rgba(255,229,163,.28)";
            ctx.fillRect(x + 1, y + 1, cell - 2, Math.max(1, cell * 0.1));
            ctx.fillStyle = "rgba(55,35,19,.34)";
            ctx.fillRect(x, y + cell - Math.max(1, cell * 0.09), cell, Math.max(1, cell * 0.09));
            // The rails follow the actual bridge cells supplied by the engine.
            for (const side of [-1, 1]) {
              const neighbor = grid[hy][hx + side];
              if (neighbor === undefined || neighbor & arena.bits.WATER) {
                ctx.fillStyle = "#6d492d";
                const railX = (flip ? -side : side) < 0 ? x : x + cell - Math.max(2, cell * 0.16);
                ctx.fillRect(railX, y, Math.max(2, cell * 0.16), cell + 0.5);
                ctx.fillStyle = "#d4a66a";
                ctx.fillRect(railX + 1, y + 1, Math.max(1, cell * 0.05), cell - 2);
              }
            }
          } else {
            ctx.strokeStyle = "rgba(209,242,246,.36)";
            ctx.lineWidth = Math.max(1, T * 0.045);
            ctx.beginPath();
            ctx.moveTo(x + cell * 0.16, y + cell * 0.48);
            ctx.lineTo(x + cell * 0.63, y + cell * 0.4);
            ctx.stroke();
          }
        }
      // Stone banks and a raised frame make the river legible at replay size.
      for (const row of [water[0], water[1] + 1]) {
        const py = Y(row / half);
        ctx.fillStyle = "#dbc48c";
        ctx.fillRect(0, py - T * 0.09, TX * T, T * 0.18);
        ctx.fillStyle = "rgba(47,57,36,.34)";
        ctx.fillRect(0, py + T * 0.09, TX * T, Math.max(1, T * 0.07));
      }
      ctx.strokeStyle = "#35472c";
      ctx.lineWidth = Math.max(3, T * 0.22);
      ctx.strokeRect(0, 0, TX * T, TY * T);
      ctx.strokeStyle = "rgba(230,218,170,.75)";
      ctx.lineWidth = Math.max(1, T * 0.055);
      ctx.strokeRect(T * 0.12, T * 0.12, TX * T - T * 0.24, TY * T - T * 0.24);
    }
    function shieldBar(x, y, w, frac) {
      ctx.fillStyle = "rgba(0,0,0,.55)";
      ctx.fillRect(x - w / 2, y, w, 3);
      ctx.fillStyle = "#cfe3ff";
      ctx.fillRect(x - w / 2, y, w * Math.max(0, Math.min(1, frac)), 3);
    }
    function hpBar(x, y, w, frac, team) {
      ctx.fillStyle = "rgba(0,0,0,.55)";
      ctx.fillRect(x - w / 2, y, w, 4);
      ctx.fillStyle = team === 0 ? C.blue : C.red;
      ctx.fillRect(x - w / 2, y, w * Math.max(0, Math.min(1, frac)), 4);
    }
    function polygon(points, fill, stroke = null, width = 0.1) {
      ctx.beginPath();
      ctx.moveTo(points[0][0], points[0][1]);
      for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
      ctx.closePath();
      ctx.fillStyle = fill;
      ctx.fill();
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = width;
        ctx.stroke();
      }
    }
    function disk(x, y, rx, ry, fill, stroke = null, width = 0.1) {
      ctx.beginPath();
      ctx.ellipse(x, y, rx, ry, 0, 0, 7);
      ctx.fillStyle = fill;
      ctx.fill();
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = width;
        ctx.stroke();
      }
    }
    // ---- Classic-deck spell art -------------------------------------------------
    // Only the eight cards in SPELL_ART get custom art; every other spell or effect
    // object keeps the generic drawing. The art is decoration placed on the points,
    // sizes and timings the renderer already used: the simulator reports no spell
    // hit radius in this contract, so nothing here is drawn as a radius.
    const artOf = (cid) => {
      const name = cards[cid]?.[0];
      return SPELL_ART.has(name) ? name : null;
    };
    // screen-space unit vector along a tile-space direction (flip-safe)
    function screenDir(dx, dy) {
      const sx = X(dx) - X(0),
        sy = Y(dy) - Y(0),
        n = Math.hypot(sx, sy);
      return n > 1e-6 ? [sx / n, sy / n] : [0, -1];
    }
    function bolt(x0, y0, x1, y1, seed, jag) {
      ctx.beginPath();
      ctx.moveTo(x0, y0);
      const nx = -(y1 - y0),
        ny = x1 - x0,
        n = Math.hypot(nx, ny) || 1;
      for (let i = 1; i < 6; i++) {
        const f = i / 6,
          w = (hash(seed + i) - 0.5) * 2 * jag;
        ctx.lineTo(lerp(x0, x1, f) + (nx / n) * w, lerp(y0, y1, f) + (ny / n) * w);
      }
      ctx.lineTo(x1, y1);
    }
    function arrowShape(x, y, ux, uy, len, fletch) {
      // shaft from tail to head along (ux, uy)
      const hx = x + ux * len * 0.5,
        hy = y + uy * len * 0.5,
        tx = x - ux * len * 0.5,
        ty = y - uy * len * 0.5,
        px = -uy,
        py = ux;
      ctx.strokeStyle = "#6b4a2b";
      ctx.lineWidth = Math.max(1, len * 0.09);
      ctx.beginPath();
      ctx.moveTo(tx, ty);
      ctx.lineTo(hx, hy);
      ctx.stroke();
      polygon([
        [hx + ux * len * 0.22, hy + uy * len * 0.22],
        [hx + px * len * 0.11, hy + py * len * 0.11],
        [hx - px * len * 0.11, hy - py * len * 0.11],
      ], "#d9dde0", "#5d6469", Math.max(0.5, len * 0.03));
      polygon([
        [tx, ty],
        [tx - ux * len * 0.16 + px * len * 0.13, ty - uy * len * 0.16 + py * len * 0.13],
        [tx + ux * len * 0.12, ty + uy * len * 0.12],
        [tx - ux * len * 0.16 - px * len * 0.13, ty - uy * len * 0.16 - py * len * 0.13],
      ], fletch);
    }
    function barrelShape(x, y, r, spin, team) {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(spin);
      ctx.fillStyle = "#9a6434";
      ctx.strokeStyle = "#4b2f19";
      ctx.lineWidth = Math.max(1, r * 0.1);
      ctx.beginPath();
      ctx.roundRect(-r * 0.78, -r, r * 1.56, r * 2, r * 0.55);
      ctx.fill();
      ctx.stroke();
      ctx.strokeStyle = "rgba(60,34,16,.55)";
      ctx.lineWidth = Math.max(0.6, r * 0.05);
      for (const sx of [-0.35, 0, 0.35]) {
        ctx.beginPath();
        ctx.moveTo(r * sx, -r * 0.92);
        ctx.lineTo(r * sx, r * 0.92);
        ctx.stroke();
      }
      ctx.fillStyle = "#59606a";
      for (const sy of [-0.62, 0.48]) ctx.fillRect(-r * 0.8, r * sy, r * 1.6, r * 0.16);
      ctx.fillStyle = team === 0 ? C.blue : C.red;
      ctx.fillRect(-r * 0.8, -r * 0.08, r * 1.6, r * 0.14);
      ctx.restore();
    }
    function logShape(cx, cy, ux, uy, len, thick, roll, team) {
      // a log lying across (ux, uy): the roll direction is perpendicular to it
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(Math.atan2(uy, ux));
      ctx.fillStyle = "#7a4a22";
      ctx.strokeStyle = team === 0 ? C.blueDk : C.redDk;
      ctx.lineWidth = Math.max(1, thick * 0.12);
      ctx.beginPath();
      ctx.roundRect(-len / 2, -thick / 2, len, thick, thick * 0.35);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "rgba(255,214,150,.22)";
      ctx.fillRect(-len / 2 + thick * 0.3, -thick * 0.38, len - thick * 0.6, thick * 0.18);
      // bark grooves move as the log turns
      ctx.strokeStyle = "rgba(48,27,12,.6)";
      ctx.lineWidth = Math.max(0.7, thick * 0.08);
      for (let i = 0; i < 6; i++) {
        const v = Math.sin(roll + i * 1.05);
        if (v < -0.2) continue;
        const gy = (thick / 2) * Math.cos(roll + i * 1.05) * 0.8;
        ctx.beginPath();
        ctx.moveTo(-len / 2 + thick * 0.45 + i * len * 0.03, gy);
        ctx.lineTo(len / 2 - thick * 0.45 - i * len * 0.02, gy);
        ctx.stroke();
      }
      for (const side of [-1, 1]) {
        disk((side * len) / 2, 0, thick * 0.22, thick * 0.5, "#c9945a", "#5e3a1c", Math.max(0.7, thick * 0.08));
        disk((side * len) / 2, 0, thick * 0.1, thick * 0.22, "#a87543");
      }
      ctx.restore();
    }
    function smokePuff(x, y, r, a, dark) {
      ctx.globalAlpha = a;
      disk(x, y, r, r * 0.9, dark ? "#3c3330" : "#e7dfcf");
      ctx.globalAlpha = 1;
    }
    // Travel: one spell row at (x, y) on the ground, `lift` above it, moving along (ux, uy).
    function drawFlightArt(art, sp, x, y, lift, r, ux, uy, prog, trail, now) {
      const gx = X(x),
        gy = Y(y),
        hx = gx,
        hy = gy - lift,
        team = sp[0];
      ctx.save();
      ctx.lineCap = "round";
      if (art === "Fireball") {
        trail.forEach(([tx, ty], i) => smokePuff(tx, ty, r * (0.55 + i * 0.16), 0.42 - i * 0.07, true));
        polygon([[hx - ux * r * 2.6, hy - uy * r * 2.6], [hx - uy * r * 0.85, hy + ux * r * 0.85],
          [hx + uy * r * 0.85, hy - ux * r * 0.85]], "rgba(246,120,32,.75)");
        disk(hx, hy, r * 1.05, r * 1.05, "#e9521c");
        disk(hx + ux * r * 0.12, hy + uy * r * 0.12, r * 0.78, r * 0.78, "#f9a12e");
        disk(hx + ux * r * 0.22, hy + uy * r * 0.22, r * 0.45, r * 0.45, "#fff2a8");
      } else if (art === "Rocket") {
        trail.forEach(([tx, ty], i) => smokePuff(tx, ty, r * (0.45 + i * 0.18), 0.6 - i * 0.1, false));
        const L = r * 2.4,
          W = r * 0.62,
          tx = hx - ux * L * 0.5,
          ty = hy - uy * L * 0.5,
          flick = 0.8 + 0.2 * Math.sin(now / 35);
        polygon([[tx - ux * L * 0.55 * flick, ty - uy * L * 0.55 * flick], [tx - uy * W * 0.8, ty + ux * W * 0.8],
          [tx + uy * W * 0.8, ty - ux * W * 0.8]], "#ffb43a", "#f06a1f", 1);
        ctx.save();
        ctx.translate(hx, hy);
        ctx.rotate(Math.atan2(uy, ux));
        polygon([[-L * 0.5, -W], [-L * 0.62, -W * 1.5], [-L * 0.3, -W * 0.7]], "#59606a");
        polygon([[-L * 0.5, W], [-L * 0.62, W * 1.5], [-L * 0.3, W * 0.7]], "#59606a");
        ctx.fillStyle = "#cfd3d6";
        ctx.strokeStyle = "#3b4045";
        ctx.lineWidth = Math.max(1, r * 0.1);
        ctx.beginPath();
        ctx.roundRect(-L * 0.5, -W * 0.7, L * 0.78, W * 1.4, W * 0.4);
        ctx.fill();
        ctx.stroke();
        polygon([[L * 0.28, -W * 0.7], [L * 0.6, 0], [L * 0.28, W * 0.7]], "#d23b2b", "#3b4045", Math.max(1, r * 0.1));
        ctx.fillStyle = team === 0 ? C.blue : C.red;
        ctx.fillRect(-L * 0.2, -W * 0.7, L * 0.12, W * 1.4);
        ctx.restore();
      } else if (art === "Arrows") {
        // a tight volley; tails fletched in the caster's colour
        const px = -uy,
          py = ux,
          len = Math.max(6, r * 1.9),
          fletch = team === 0 ? "#cfe3ff" : "#ffd9c7";
        for (let i = 0; i < 7; i++) {
          const a = (hash(i * 3 + 1) - 0.5) * 2,
            b = (hash(i * 7 + 5) - 0.5) * 2;
          arrowShape(hx + px * a * r * 1.25 + ux * b * r * 0.8, hy + py * a * r * 1.25 + uy * b * r * 0.8, ux, uy, len, fletch);
        }
      } else if (art === "GoblinBarrel") {
        barrelShape(hx, hy, r * 0.95, prog * Math.PI * 5, team);
      } else if (art === "Log") {
        logShape(hx, hy, -uy, ux, 2 * T, T * 0.4, prog * Math.PI * 3, team);
      }
      ctx.restore();
    }
    // A spell sitting at its centre (ROLLING, AREA, PULSING, STRIKES).
    function drawGroundArt(art, sp, px, py, col, age, now) {
      ctx.save();
      ctx.lineCap = "round";
      if (art === "Log" && sp[6] === "ROLLING") {
        const [ux, uy] = screenDir(sp[4] - sp[2], sp[5] - sp[3]),
          rolled = Math.hypot(sp[2], sp[3]) / 0.4;
        for (let i = 1; i <= 3; i++)
          smokePuff(px - ux * T * (0.35 + i * 0.32) + (hash(i) - 0.5) * T,
            py - uy * T * (0.35 + i * 0.32), T * (0.2 + i * 0.05), 0.45 - i * 0.12, false);
        logShape(px, py, -uy, ux, 2 * T, T * 0.4, rolled, sp[0]);
      } else if (art === "Poison") {
        ctx.globalAlpha = 0.5 + 0.08 * Math.sin(now / 160);
        disk(px, py, T * 1.05, T * 0.92, "#e2b43c", "#b0731f", Math.max(1, T * 0.08));
        ctx.globalAlpha = 0.45;
        for (let i = 0; i < 5; i++)
          disk(px + Math.cos(i * 1.26) * T * 0.48, py + Math.sin(i * 1.26) * T * 0.4, T * 0.42, T * 0.36,
            i % 2 ? "#f0cf5a" : "#d79a2c");
        ctx.globalAlpha = 0.7;
        for (let i = 0; i < 9; i++)
          disk(px + (hash(i * 3 + 2) - 0.5) * T * 1.6, py + (hash(i * 7 + 1) - 0.5) * T * 1.3,
            T * 0.05, T * 0.05, "#5a2f63");
        ctx.globalAlpha = 1;
        for (let i = 0; i < 7; i++) {
          const life = ((now / 900 + hash(i * 11)) % 1),
            bx = px + (hash(i * 5 + 2) - 0.5) * T * 1.5,
            by = py + (hash(i * 9 + 4) - 0.5) * T * 1.2 - life * T * 0.35;
          ctx.globalAlpha = 0.85 * (1 - life);
          disk(bx, by, T * (0.06 + life * 0.1), T * (0.06 + life * 0.1), "rgba(255,236,160,.35)", "#fff0a8", 1);
        }
        ctx.globalAlpha = 1;
      } else if (art === "Lightning") {
        // bolts drop from above on a beat counted from when the spell appeared (decorative:
        // the strikes' targets and times are not in the drawing contract)
        ctx.globalAlpha = 0.18;
        disk(px, py, T, T * 0.9, "#cfeeff");
        ctx.globalAlpha = 1;
        const beat = Math.floor(age / 460),
          phase = (age % 460) / 460;
        if (phase < 0.32) {
          const a = hash(beat * 13 + 1) * Math.PI * 2,
            d = hash(beat * 17 + 3) * T * 0.75,
            sx = px + Math.cos(a) * d,
            sy = py + Math.sin(a) * d * 0.8;
          ctx.globalAlpha = 1 - phase / 0.32;
          disk(sx, sy, T * 0.55, T * 0.42, "rgba(255,248,190,.65)");
          ctx.strokeStyle = "#8fd7ff";
          ctx.lineWidth = Math.max(3, T * 0.24);
          bolt(sx + (hash(beat) - 0.5) * T * 0.5, sy - T * 2.4, sx, sy, beat * 7, T * 0.35);
          ctx.stroke();
          ctx.strokeStyle = "#ffffff";
          ctx.lineWidth = Math.max(1.2, T * 0.09);
          bolt(sx + (hash(beat) - 0.5) * T * 0.5, sy - T * 2.4, sx, sy, beat * 7, T * 0.35);
          ctx.stroke();
          ctx.globalAlpha = 1;
        }
      } else if (art === "Zap") {
        ctx.globalAlpha = 0.45;
        disk(px, py, T, T, "#9fe3ff");
        ctx.globalAlpha = 1;
        ctx.strokeStyle = "#8fd7ff";
        ctx.lineWidth = Math.max(2.5, T * 0.2);
        bolt(px + T * 0.2, py - T * 2.2, px, py, Math.floor(now / 70), T * 0.25);
        ctx.stroke();
        ctx.strokeStyle = "#e9fbff";
        ctx.lineWidth = Math.max(1.5, T * 0.1);
        const spin = Math.floor(now / 70);
        for (let i = 0; i < 6; i++) {
          const a = (i / 6) * Math.PI * 2 + hash(spin + i) * 0.6;
          bolt(px, py, px + Math.cos(a) * T, py + Math.sin(a) * T, spin * 6 + i, T * 0.18);
          ctx.stroke();
        }
      }
      ctx.restore();
      // the existing centre marker stays as it was
      if (!(art === "Log" && sp[6] === "ROLLING")) {
        ctx.strokeStyle = col;
        ctx.lineWidth = 2;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.arc(px, py, T, 0, 7);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
    // Impact: drawn on the same 450 ms clock and size envelope as the generic burst.
    function drawImpactArt(art, f, t) {
      const x = X(f.x),
        y = Y(f.y),
        R = T * (0.8 + 1.9 * Math.min(1, t * 2.2)),
        fade = Math.max(0, 1 - t);
      ctx.save();
      ctx.lineCap = "round";
      if (art === "Fireball" || art === "Rocket") {
        const big = art === "Rocket" ? 1.15 : 1;
        if (t < 0.3) {
          ctx.globalAlpha = 1 - t / 0.3;
          disk(x, y, R * 0.75 * big, R * 0.75 * big, "#fff4b8");
        }
        ctx.globalAlpha = Math.max(0, 0.95 - t * 1.2);
        disk(x, y, R * 0.62 * big, R * 0.58 * big, "#f47a24");
        ctx.globalAlpha = Math.max(0, 0.9 - t * 1.6);
        disk(x, y, R * 0.36 * big, R * 0.34 * big, "#ffd35a");
        for (let i = 0; i < 9; i++) {
          const a = (i / 9) * Math.PI * 2 + hash(i) * 0.5;
          smokePuff(x + Math.cos(a) * R * 0.55 * big, y + Math.sin(a) * R * 0.5 * big - t * T * 0.4,
            T * (0.38 + t * 0.4) * big, Math.min(0.7, t * 1.6) * fade, true);
        }
        ctx.fillStyle = "#ffcf4a";
        for (let i = 0; i < 10; i++) {
          const a = hash(i * 3 + 7) * Math.PI * 2,
            d = R * (0.5 + t * 0.7) * big;
          ctx.globalAlpha = fade;
          ctx.fillRect(x + Math.cos(a) * d, y + Math.sin(a) * d, Math.max(1.5, T * 0.1), Math.max(1.5, T * 0.1));
        }
        if (art === "Rocket") {
          ctx.globalAlpha = fade;
          ctx.strokeStyle = "#fff1c9";
          ctx.lineWidth = Math.max(2, T * 0.14);
          ctx.beginPath();
          ctx.arc(x, y, R * 1.05, 0, 7);
          ctx.stroke();
        }
      } else if (art === "Arrows") {
        // arrows stuck where the volley came down, inside the landing marker
        ctx.globalAlpha = Math.max(0, 0.6 - t * 0.7);
        ctx.strokeStyle = "#efe6cc";
        ctx.lineWidth = Math.max(1.5, T * 0.1);
        ctx.beginPath();
        ctx.arc(x, y, R * 0.8, 0, 7);
        ctx.stroke();
        ctx.globalAlpha = fade;
        const fletch = f.team === 0 ? "#cfe3ff" : "#ffd9c7";
        for (let i = 0; i < 11; i++) {
          const a = hash(i * 5 + (f.kind === "land" ? 3 : 0)) * Math.PI * 2,
            d = Math.sqrt(hash(i * 13 + 1)) * T * 1.9;
          arrowShape(x + Math.cos(a) * d, y + Math.sin(a) * d * 0.85, 0.42, -0.9, T * 0.75, fletch);
        }
      } else if (art === "GoblinBarrel") {
        for (let i = 0; i < 6; i++) {
          const a = (i / 6) * Math.PI * 2 + 0.3;
          smokePuff(x + Math.cos(a) * R * 0.35, y + Math.sin(a) * R * 0.3, T * (0.45 + t * 0.5), 0.75 * fade, false);
        }
        ctx.globalAlpha = fade;
        for (let i = 0; i < 6; i++) {
          const a = (i / 6) * Math.PI * 2 + hash(i) * 0.6,
            d = T * (0.3 + t * 1.6);
          ctx.save();
          ctx.translate(x + Math.cos(a) * d, y + Math.sin(a) * d - Math.sin(t * Math.PI) * T * 0.6);
          ctx.rotate(a + t * 6);
          ctx.fillStyle = "#9a6434";
          ctx.fillRect(-T * 0.08, -T * 0.32, T * 0.16, T * 0.64);
          ctx.restore();
        }
      } else if (art === "Log" || art === "Zap" || art === "Lightning" || art === "Poison") {
        // Log touching down after its throw; a Zap or other area seen only as an event
        const dust = art === "Log";
        ctx.globalAlpha = fade;
        if (dust) {
          for (const side of [-1, 1])
            for (let i = 0; i < 3; i++)
              smokePuff(x + side * T * (0.7 + i * 0.3), y + (i - 1) * T * 0.15, T * (0.3 + t * 0.4), 0.6 * fade, false);
        } else {
          disk(x, y, R * 0.7, R * 0.7, art === "Poison" ? "rgba(226,180,60,.45)" : "rgba(159,227,255,.55)");
          ctx.strokeStyle = "#8fd7ff";
          ctx.lineWidth = Math.max(2.5, T * 0.2);
          bolt(x + T * 0.2, y - T * 2.2, x, y, 21, T * 0.25);
          ctx.stroke();
          ctx.strokeStyle = "#e9fbff";
          ctx.lineWidth = Math.max(1.5, T * 0.1);
          for (let i = 0; i < 6; i++) {
            const a = (i / 6) * Math.PI * 2 + hash(i + 4) * 0.6;
            bolt(x, y, x + Math.cos(a) * R * 0.7, y + Math.sin(a) * R * 0.7, i + 9, T * 0.16);
            ctx.stroke();
          }
        }
      }
      ctx.restore();
    }
    function drawTower(e, px, py, r, hit, fill, edge) {
      let left = px - r,
        top = py - r,
        width = 2 * r,
        height = 2 * r;
      if (e[2] === PRINCESS && e[14]) {
        const [x0, y0, x1, y1] = e[14];
        left = Math.min(X(x0), X(x1));
        top = Math.min(Y(y0), Y(y1));
        width = Math.abs(x1 - x0) * T;
        height = Math.abs(y1 - y0) * T;
      }
      ctx.fillStyle = "rgba(20,29,21,.35)";
      ctx.beginPath();
      ctx.ellipse(left + width * 0.55, top + height * 0.88, width * 0.63, height * 0.3, 0, 0, 7);
      ctx.fill();
      // The first rectangle is the exact simulator footprint, including wide
      // princess-tower footprints. Decorative pieces stay inside this outline.
      ctx.fillStyle = hit > 0 ? "#fff" : "#8f8e79";
      ctx.strokeStyle = "#4a4b45";
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.roundRect(left, top, width, height, Math.min(6, r * 0.3));
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = "#666f67";
      ctx.fillRect(left + width * 0.07, top + height * 0.55, width * 0.86, height * 0.32);
      ctx.fillStyle = "#c5bea1";
      ctx.fillRect(left + width * 0.1, top + height * 0.12, width * 0.8, height * 0.47);
      ctx.fillStyle = edge;
      ctx.fillRect(left + width * 0.09, top + height * 0.2, width * 0.82, height * 0.12);
      ctx.fillStyle = fill;
      ctx.fillRect(left + width * 0.13, top + height * 0.08, width * 0.74, height * 0.32);
      ctx.fillStyle = "rgba(255,255,255,.22)";
      ctx.fillRect(left + width * 0.16, top + height * 0.1, width * 0.66, height * 0.05);
      ctx.fillStyle = "#494b43";
      ctx.fillRect(left + width * 0.45, top + height * 0.48, width * 0.1, height * 0.29);
      for (const side of [0.04, 0.79]) {
        ctx.fillStyle = "#d3c9a9";
        ctx.fillRect(left + width * side, top + height * 0.04, width * 0.17, height * 0.18);
        ctx.fillStyle = "#817b68";
        ctx.fillRect(left + width * side, top + height * 0.19, width * 0.17, height * 0.06);
      }
      if (e[2] === KING) {
        polygon([
          [px - r * 0.34, top + height * 0.25],
          [px - r * 0.35, top + height * 0.1],
          [px - r * 0.12, top + height * 0.17],
          [px, top + height * 0.03],
          [px + r * 0.12, top + height * 0.17],
          [px + r * 0.35, top + height * 0.1],
          [px + r * 0.34, top + height * 0.25],
        ], "#f1c943", "#7d5a25", 1.2);
        disk(px, top + height * 0.16, r * 0.065, r * 0.065, "#fff2a4");
      } else {
        polygon([
          [px - r * 0.23, top + height * 0.26],
          [px, top + height * 0.04],
          [px + r * 0.23, top + height * 0.26],
        ], "#f4d166", "#795b2b", 1);
      }
    }
    function drawBuilding(name, px, py, r, fill, edge, hit) {
      ctx.save();
      ctx.translate(px, py);
      ctx.scale(r, r);
      disk(0.12, 0.43, 0.95, 0.42, "rgba(20,29,21,.3)");
      ctx.fillStyle = hit > 0 ? "#fff" : "#8b8575";
      ctx.strokeStyle = "#3e4241";
      ctx.lineWidth = 0.12;
      ctx.beginPath();
      ctx.roundRect(-0.85, -0.72, 1.7, 1.55, 0.15);
      ctx.fill();
      ctx.stroke();
      ctx.fillStyle = fill;
      ctx.fillRect(-0.72, -0.72, 1.44, 0.28);
      if (/Cannon|Xbow|Tesla|Inferno/i.test(name)) {
        disk(0, -0.2, 0.58, 0.52, edge, "#e4be77", 0.1);
        ctx.fillStyle = "#303b46";
        ctx.fillRect(-0.16, -1.08, 0.32, 0.9);
        disk(0, -1.08, 0.16, 0.13, /Inferno/.test(name) ? "#f6a43c" : "#c3d8dd");
      } else if (/Tombstone/.test(name)) {
        ctx.fillStyle = "#c0bcb0";
        ctx.beginPath();
        ctx.roundRect(-0.4, -0.74, 0.8, 1.1, 0.35);
        ctx.fill();
        ctx.fillStyle = "#5e625b";
        ctx.fillRect(-0.06, -0.57, 0.12, 0.6);
        ctx.fillRect(-0.25, -0.37, 0.5, 0.12);
      } else {
        ctx.fillStyle = "#d0c4a5";
        ctx.fillRect(-0.57, -0.35, 1.14, 0.8);
        ctx.fillStyle = edge;
        ctx.fillRect(-0.19, -0.11, 0.38, 0.56);
      }
      ctx.restore();
    }
    function drawTroop(name, px, py, r, fill, edge, hit, facing) {
      const goblin = /Goblin/.test(name), skeleton = /Skeleton/.test(name),
        giant = /Giant|Golem|Pekka|LavaHound/.test(name),
        metal = /Pekka|MegaMinion/.test(name),
        winged = /Minion|Bat|Dragon|LavaHound/.test(name),
        archer = /Archer|Princess/.test(name),
        caster = /Wizard|Witch|Spirit/.test(name),
        mounted = /HogRider|BattleRam/.test(name);
      const skin = skeleton ? "#e7e4ce" : goblin ? "#8ccc55" : metal ? "#596177" : "#e3ad82";
      const coat = /Wizard/.test(name) ? "#375db1" : archer ? "#9d4d86" :
        goblin ? "#875638" : /Barbarian/.test(name) ? "#bd7645" :
        metal ? "#4c4b72" : /Golem/.test(name) ? "#7c8c8d" : fill;
      ctx.save();
      ctx.translate(px, py);
      ctx.rotate(facing);
      ctx.scale(r, r);
      disk(0.1, 0.7, 0.87, 0.32, "rgba(14,27,20,.3)");
      // Team color lives on the base; the miniature keeps its card colors.
      disk(0, 0.45, 0.82, 0.35, edge);
      disk(0, 0.42, 0.67, 0.24, "#d3c49d");
      if (winged) {
        polygon([[-0.25, -0.25], [-1.25, -0.9], [-1.02, 0.12], [-0.35, 0.4]],
          /Dragon|Lava/.test(name) ? "#658e57" : "#5d597f", "#303849");
        polygon([[0.25, -0.25], [1.25, -0.9], [1.02, 0.12], [0.35, 0.4]],
          /Dragon|Lava/.test(name) ? "#658e57" : "#5d597f", "#303849");
      }
      if (mounted) {
        disk(0, 0.17, 0.82, 0.64, "#78534a", "#513c37");
        disk(0, -0.49, 0.52, 0.39, "#aa8171", "#684c44");
        disk(-0.33, -0.54, 0.16, 0.21, "#d6b69b");
        disk(0.33, -0.54, 0.16, 0.21, "#d6b69b");
      }
      disk(-0.34, 0.45, giant ? 0.28 : 0.19, 0.3, "#534b42");
      disk(0.34, 0.45, giant ? 0.28 : 0.19, 0.3, "#534b42");
      disk(0, 0.05, giant ? 0.78 : 0.57, giant ? 0.71 : 0.56,
        hit > 0 ? "#fff" : coat, "#3b4347", 0.1);
      if (/Golem/.test(name)) {
        polygon([[-0.7,-0.4],[-0.25,-0.8],[0.25,-0.72],[0.7,-0.4],[0.58,0.32],[0,0.48],[-0.65,0.3]],
          /Ice/.test(name) ? "#a4dce5" : "#899493", "#4b6064");
      }
      disk(0, -0.47, giant ? 0.54 : 0.43, giant ? 0.51 : 0.43,
        hit > 0 ? "#fff" : skin, "#5b544c", 0.09);
      if (goblin) {
        polygon([[-0.36,-0.5],[-0.98,-0.69],[-0.55,-0.25]], "#8ccc55", "#4e7135");
        polygon([[0.36,-0.5],[0.98,-0.69],[0.55,-0.25]], "#8ccc55", "#4e7135");
      } else if (skeleton) {
        disk(-0.16, -0.46, 0.13, 0.17, "#323a42");
        disk(0.16, -0.46, 0.13, 0.17, "#323a42");
        ctx.fillStyle = "#5b5650";
        ctx.fillRect(-0.15, -0.18, 0.3, 0.08);
      } else if (metal) {
        polygon([[-0.58,-0.7],[-0.42,-1.13],[-0.15,-0.87],[0.15,-0.87],[0.42,-1.13],[0.58,-0.7]],
          "#666984", "#2f344f");
        ctx.fillStyle = "#b5dff0";
        ctx.fillRect(-0.28, -0.49, 0.56, 0.09);
      } else if (archer || caster || /Musketeer/.test(name)) {
        polygon([[-0.53,-0.43],[-0.47,-0.96],[0,-1.13],[0.47,-0.96],[0.53,-0.43]],
          /Musketeer/.test(name) ? "#5b417e" : coat, "#4d3d55");
        disk(0, -0.43, 0.28, 0.31, skin);
      } else if (/Knight|Barbarian|BattleRam/.test(name)) {
        polygon([[-0.53,-0.42],[-0.4,-0.88],[0,-1.02],[0.4,-0.88],[0.53,-0.42]],
          /Barbarian/.test(name) ? "#e2c445" : "#aeb6bd", "#59616a");
      }
      if (!skeleton && !metal) {
        disk(-0.16, -0.48, 0.055, 0.075, "#2b3237");
        disk(0.16, -0.48, 0.055, 0.075, "#2b3237");
      }
      if (archer) {
        ctx.strokeStyle = "#6a412c";
        ctx.lineWidth = 0.15;
        ctx.beginPath();
        ctx.arc(0.65, -0.07, 0.43, -1.3, 1.3);
        ctx.stroke();
        ctx.strokeStyle = "#eee5c5";
        ctx.lineWidth = 0.05;
        ctx.beginPath();
        ctx.moveTo(0.76, -0.48);
        ctx.lineTo(0.76, 0.34);
        ctx.stroke();
      } else if (/Musketeer/.test(name)) {
        ctx.fillStyle = "#3c4149";
        ctx.fillRect(0.39, -0.95, 0.17, 1.12);
        ctx.fillStyle = "#c8a35a";
        ctx.fillRect(0.36, -0.15, 0.24, 0.13);
      } else if (caster) {
        disk(0.59, -0.33, 0.25, 0.25,
          /Ice/.test(name) ? "#a8ebfa" : "#f6b24b", "#f8e1a8");
      } else if (!winged && !mounted) {
        ctx.strokeStyle = "#d7e1e4";
        ctx.lineWidth = 0.17;
        ctx.beginPath();
        ctx.moveTo(0.5, 0.2);
        ctx.lineTo(0.7, -0.75);
        ctx.stroke();
        ctx.fillStyle = "#776040";
        ctx.fillRect(0.27, 0.1, 0.47, 0.12);
      }
      if (/Balloon/.test(name)) {
        disk(0, -1.16, 0.72, 0.88, fill, edge, 0.13);
        ctx.fillStyle = "rgba(255,255,255,.28)";
        ctx.fillRect(-0.37, -1.73, 0.13, 0.75);
        ctx.strokeStyle = "#e6d1a8";
        ctx.lineWidth = 0.07;
        for (const side of [-0.42, 0.42]) {
          ctx.beginPath();
          ctx.moveTo(side, -0.52);
          ctx.lineTo(side * 0.65, 0.18);
          ctx.stroke();
        }
      }
      ctx.restore();
    }
    function drawEntity(e, x, y, hp, now) {
      const [uid, team, kind, cid, , , , maxHp, rad, flags, , fxv, fyv] = e;
      const mine = team === 0,
        fill = mine ? C.blue : C.red,
        edge = mine ? C.blueDk : C.redDk;
      const flying = flags & 1,
        deploying = flags & 2,
        tower = kind === KING || kind === PRINCESS;
      const born = firstSeen.get(uid) ?? 0,
        pop = Math.min(1, Math.max(0, (now - born) / 160));
      const elapsed = now - (hitAt.get(uid) ?? -1e9);
      const hit = elapsed < 0 ? 0 : Math.max(0, 1 - elapsed / 140);
      const px = X(x),
        py = Y(y) - (flying ? T * 0.5 : 0);
      let r = Math.max(T * 0.48, rad * T) * (0.6 + 0.4 * pop);
      ctx.globalAlpha = deploying ? 0.55 : 1;
      if (flying) {
        ctx.fillStyle = "rgba(0,0,0,.22)";
        ctx.beginPath();
        ctx.ellipse(X(x), Y(y) + r * 0.5, r, r * 0.45, 0, 0, 7);
        ctx.fill();
      }
      const name = tower ? "" : cards[cid]?.[0] || "Unknown";
      if (tower) {
        r = (kind === KING ? 1.55 : 1.5) * T;
        if (kind === PRINCESS && e[14]) {
          const [x0, y0, x1, y1] = e[14];
          r = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) * T / 2;
        }
        drawTower(e, px, py, r, hit, fill, edge);
      } else if (kind === BUILDING) {
        drawBuilding(name, px, py, r, fill, edge, hit);
      } else {
        const screenX = flip ? -fxv : fxv,
          screenY = flip ? fyv : -fyv,
          facing = Math.hypot(screenX, screenY) > 0.1 ? Math.atan2(screenX, -screenY) : 0;
        drawTroop(name, px, py, r, fill, edge, hit, facing);
      }
      ctx.globalAlpha = 1;
      if (e[13] > 0) {
        ctx.strokeStyle = "#ffd400";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(px, py, r + 3.5, 0, 7);
        ctx.stroke();
      }
      const shield = e[15] || 0;
      const barY = Math.max(12, py - r - 8);
      if (tower || hp < maxHp || shield > 0)
        hpBar(px, barY, Math.max(16, 2 * r), maxHp ? hp / maxHp : 0, team);
      if (shield > 0)
        shieldBar(px, barY - 4, Math.max(16, 2 * r), shield / (shieldMax.get(uid) || shield));
      if (tower) {
        ctx.fillStyle = "#16202e";
        ctx.font = "700 11px ui-monospace, Menlo, monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "alphabetic";
        ctx.fillText(Math.round(hp), px, Math.max(10, barY - 3));
      }
      drawn.push({ p: [px, py], rad: r, entity: e });
      if (deploying) {
        ctx.strokeStyle = "#fff";
        ctx.setLineDash([3, 3]);
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(px, py, r + 3, 0, 7);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
    function drawFx(now) {
      fx = fx.filter((f) => now - f.at < 450);
      for (const f of fx) {
        const t = (now - f.at) / 450;
        if (t < 0) continue;
        const art = (f.kind === "boom" || f.kind === "land") && f.card !== undefined ? artOf(f.card) : null;
        if (art) {
          drawImpactArt(art, f, t);
        } else if (f.kind === "land") {
          // a volley landing has no generic picture
        } else if (f.kind === "boom") {
          const col = f.team === 0 ? C.blue : C.red,
            r = T * (0.8 + 1.9 * Math.min(1, t * 2.2));
          ctx.fillStyle = "#fff";
          ctx.globalAlpha = Math.max(0, 0.85 - t * 1.6);
          ctx.beginPath();
          ctx.arc(X(f.x), Y(f.y), r, 0, 7);
          ctx.fill();
          ctx.strokeStyle = col;
          ctx.globalAlpha = 1 - t;
          ctx.lineWidth = 3;
          ctx.beginPath();
          ctx.arc(X(f.x), Y(f.y), r, 0, 7);
          ctx.stroke();
        } else if (f.kind === "die") {
          ctx.strokeStyle = f.team === 0 ? C.blue : C.red;
          ctx.globalAlpha = 1 - t;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(X(f.x), Y(f.y), Math.max(4, f.r * T) * (1 + t * 1.6), 0, 7);
          ctx.stroke();
        } else {
          ctx.strokeStyle = "#fff";
          ctx.globalAlpha = 1 - t;
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.arc(X(f.x), Y(f.y), T * (0.4 + t * 1.2), 0, 7);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
      }
    }

    function draw(a, b, t, now, options = {}) {
      drawn = [];
      ctx.globalAlpha = 1;
      ctx.setLineDash([]);
      ctx.lineCap = "butt";
      ctx.lineJoin = "round";
      ctx.textBaseline = "alphabetic";
      T = options.scale || 16;
      flip = !!options.flip;
      cards = options.cards || {};
      const delayTicks = options.delayTicks || 0,
        overlay = options.overlay;
      const dpr = canvas.width / (TX * T);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      drawGround();
      if (overlay) overlay();
      for (const sp of b.sp.filter(isFlight)) {
        // where each travelling spell will land
        const col = sp[0] === 0 ? C.blue : C.red,
          name = cards[sp[1]] ? pretty(cards[sp[1]][0]) : "";
        ctx.fillStyle = col;
        ctx.globalAlpha = 0.16;
        ctx.beginPath();
        ctx.arc(X(sp[4]), Y(sp[5]), 2.2 * T, 0, 7);
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.strokeStyle = col;
        ctx.setLineDash([5, 4]);
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.setLineDash([]);
        if (artOf(sp[1])) {
          // a pale inner rim, as the game marks a spell's landing spot
          ctx.strokeStyle = "rgba(255,255,255,.55)";
          ctx.lineWidth = Math.max(1.5, T * 0.12);
          ctx.beginPath();
          ctx.arc(X(sp[4]), Y(sp[5]), 2.2 * T - Math.max(2, T * 0.12), 0, 7);
          ctx.stroke();
        }
        ctx.fillStyle = "#16202e";
        ctx.font = "600 11px system-ui";
        ctx.textAlign = "center";
        ctx.textBaseline = "alphabetic";
        ctx.fillText(name, X(sp[4]), Y(sp[5]) - 2.4 * T);
      }
      const list = [];
      for (const e of b.en) {
        const p = a.by.get(e[0]);
        list.push([
          e,
          p ? lerp(p[4], e[4], t) : e[4],
          p ? lerp(p[5], e[5], t) : e[5],
          p ? lerp(p[6], e[6], t) : e[6],
        ]);
      }
      list.sort(
        (p, q) =>
          (p[0][9] & 1) - (q[0][9] & 1) || (flip ? p[2] - q[2] : q[2] - p[2]),
      ); // ground first, then flying; far before near
      for (const [e, x, y, hp] of list) drawEntity(e, x, y, hp, now);
      const named = []; // one name per group of the same unit standing together
      ctx.font = "700 " + Math.max(9, Math.round(T * 0.5)) + "px system-ui";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.lineJoin = "round";
      for (const [e, x, y] of list) {
        if (e[2] === KING || e[2] === PRINCESS || !cards[e[3]]) continue;
        if (
          named.some(
            (n) =>
              n[0] === e[1] &&
              n[1] === e[3] &&
              Math.abs(n[2] - x) < 2.2 &&
              Math.abs(n[3] - y) < 2.2,
          )
        )
          continue;
        named.push([e[1], e[3], x, y]);
        const r = Math.max(T * 0.48, e[8] * T),
          ly = Y(y) + r + 2 - (e[9] & 1 ? T * 0.5 : 0),
          label = pretty(cards[e[3]][0]);
        ctx.lineWidth = 3;
        ctx.strokeStyle = "rgba(10,16,28,.85)";
        ctx.strokeText(label, X(x), ly);
        ctx.fillStyle = e[1] === 0 ? "#cfe3ff" : "#ffd9c7";
        ctx.fillText(label, X(x), ly);
      }
      const same = a.pr.length === b.pr.length;
      b.pr.forEach((p, i) => {
        const q = same ? a.pr[i] : p;
        ctx.fillStyle = p[0] === 0 ? "#dbeaff" : "#ffe2d2";
        ctx.strokeStyle = "#16202e";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(
          X(lerp(q[1], p[1], t)),
          Y(lerp(q[2], p[2], t)),
          Math.max(2.5, T * 0.16),
          0,
          7,
        );
        ctx.fill();
        ctx.stroke();
      });
      for (const p of b.me?.pend || []) {
        // your own plays that have not landed yet: a marker with a clock that runs down
        const q = a.me?.pend?.find((o) => o[0] === p[0]),
          left = q ? lerp(q[4], p[4], t) : p[4];
        const px = X(p[2]),
          py = Y(p[3]),
          name = cards[p[1]] ? pretty(cards[p[1]][0]) : "";
        ctx.fillStyle = "rgba(255,255,255,.22)";
        ctx.beginPath();
        ctx.arc(px, py, T * 0.8, 0, 7);
        ctx.fill();
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.arc(
          px,
          py,
          T * 0.8,
          -Math.PI / 2,
          -Math.PI / 2 +
            2 *
              Math.PI *
              Math.max(0, Math.min(1, left / Math.max(1, delayTicks))),
        );
        ctx.stroke();
        ctx.fillStyle = "#16202e";
        ctx.font = "600 11px system-ui";
        ctx.textAlign = "center";
        ctx.textBaseline = "alphabetic";
        ctx.fillText(name, px, py - T - 2);
      }
      for (const sp of b.sp.filter((s) => !isFlight(s))) {
        const px = X(sp[2]),
          py = Y(sp[3]),
          col = sp[0] === 0 ? C.blue : C.red,
          art = artOf(sp[1]);
        ctx.strokeStyle = col;
        ctx.fillStyle = "#7a4a1f";
        ctx.lineWidth = 2;
        if (art) {
          const seen = spellSeen.get(spKey(sp));
          drawGroundArt(art, sp, px, py, col, seen === undefined ? 0 : Math.max(0, now - seen), now);
        } else if (sp[6] === "ROLLING") {
          ctx.fillRect(px - T, py - T * 0.2, 2 * T, T * 0.4);
          ctx.strokeRect(px - T, py - T * 0.2, 2 * T, T * 0.4);
        } else {
          ctx.setLineDash([4, 3]);
          ctx.beginPath();
          ctx.arc(px, py, T, 0, 7);
          ctx.stroke();
          ctx.setLineDash([]);
        }
        ctx.fillStyle = "#16202e";
        ctx.font = "600 11px system-ui";
        ctx.textAlign = "center";
        ctx.textBaseline = "alphabetic";
        ctx.fillText(pretty(cards[sp[1]]?.[0] || ""), px, py - T - 3);
        drawn.push({ p: [px, py], rad: T, spell: sp });
      }
      for (const [k, sp] of b.spBy) {
        if (!isFlight(sp)) continue; // travelling spells: a ball that arcs from where it was thrown to its target
        const p = a.spBy.get(k) || sp,
          x = lerp(p[2], sp[2], t),
          y = lerp(p[3], sp[3], t),
          from = spellFrom.get(k) || [x, y];
        const total = Math.hypot(sp[4] - from[0], sp[5] - from[1]),
          prog =
            total > 0
              ? Math.min(1, Math.hypot(x - from[0], y - from[1]) / total)
              : 1;
        const lift = Math.sin(Math.PI * prog) * 2.2 * T,
          col = sp[0] === 0 ? C.blue : C.red,
          r = T * (0.45 + 0.25 * Math.sin(Math.PI * prog));
        const dx = sp[4] - from[0],
          dy = sp[5] - from[1],
          n = Math.hypot(dx, dy) || 1;
        const art = artOf(sp[1]);
        if (art) {
          // Same arc, position and hit target as the generic ball below; only the picture differs.
          const rows = b.spAll?.get(k) || [sp],
            before = a.spAll?.get(k) || [];
          for (const row of rows) {
            let rx = x,
              ry = y;
            if (row !== sp) {
              // another volley of this cast: interpolate from its nearest row in the earlier frame
              let q = row,
                best = 2.5;
              for (const o of before) {
                const d = Math.hypot(o[2] - row[2], o[3] - row[3]);
                if (d < best) (best = d), (q = o);
              }
              rx = lerp(q[2], row[2], t);
              ry = lerp(q[3], row[3], t);
            }
            const rp = total > 0 ? Math.min(1, Math.hypot(rx - from[0], ry - from[1]) / total) : 1,
              rl = Math.sin(Math.PI * rp) * 2.2 * T,
              rr = T * (0.45 + 0.25 * Math.sin(Math.PI * rp));
            ctx.fillStyle = "rgba(0,0,0,.25)";
            ctx.beginPath();
            ctx.ellipse(X(rx), Y(ry), rr, rr * 0.5, 0, 0, 7);
            ctx.fill();
            // on-screen heading of the arc, including the climb or fall
            const [gx, gy] = screenDir(dx, dy),
              vx = gx * total * T,
              vy = gy * total * T - Math.cos(Math.PI * rp) * Math.PI * 2.2 * T,
              vn = Math.hypot(vx, vy) || 1;
            const trail = [];
            for (let i = 1; i <= 4; i++) {
              const bx = rx - (dx / n) * i * 0.45,
                by = ry - (dy / n) * i * 0.45,
                bl = Math.sin(Math.PI * Math.max(0, rp - i * 0.02)) * 2.2 * T;
              trail.push([X(bx), Y(by) - bl]);
            }
            drawFlightArt(art, row, rx, ry, rl, rr, vx / vn, vy / vn, rp, trail, now);
          }
          drawn.push({ p: [X(x), Y(y) - lift], rad: r, spell: sp });
          continue;
        }
        ctx.fillStyle = "rgba(0,0,0,.25)";
        ctx.beginPath();
        ctx.ellipse(X(x), Y(y), r, r * 0.5, 0, 0, 7);
        ctx.fill();
        ctx.strokeStyle = col;
        ctx.lineCap = "round";
        for (let i = 1; i <= 4; i++) {
          // trail
          ctx.globalAlpha = 0.5 - i * 0.1;
          ctx.lineWidth = r * (1.5 - i * 0.25);
          const bx = x - (dx / n) * i * 0.45,
            by = y - (dy / n) * i * 0.45,
            bl = Math.sin(Math.PI * Math.max(0, prog - i * 0.02)) * 2.2 * T;
          ctx.beginPath();
          ctx.moveTo(X(bx), Y(by) - bl);
          ctx.lineTo(X(bx + (dx / n) * 0.3), Y(by + (dy / n) * 0.3) - bl);
          ctx.stroke();
        }
        ctx.globalAlpha = 1;
        ctx.fillStyle = col;
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(X(x), Y(y) - lift, r, 0, 7);
        ctx.fill();
        ctx.stroke();
        drawn.push({ p: [X(x), Y(y) - lift], rad: r, spell: sp });
      }
      drawFx(now);
      return drawn;
    }
    return { reset, observe, draw, addEffect: (f) => fx.push(f) };
  }
  // The mask, shading and tap all refer to the SAME half-cell. A mask cell
  // describes its centre; never expand it back into a whole-tile rectangle.
  const placement = Object.freeze({
    at(x, y, grid) {
      if (!Number.isFinite(x) || !Number.isFinite(y)) return null;
      const cx = Math.floor(x * grid.half),
        cy = Math.floor(y * grid.half);
      if (cx < 0 || cx >= grid.width || cy < 0 || cy >= grid.height)
        return null;
      return { cx, cy, x: (cx + 0.5) / grid.half, y: (cy + 0.5) / grid.half };
    },
    allowed(grid, point) {
      return (
        !!point &&
        point.cx >= 0 &&
        point.cx < grid.width &&
        point.cy >= 0 &&
        point.cy < grid.height &&
        grid.m[point.cy * grid.width + point.cx] === "1"
      );
    },
    draw(ctx, grid, scale, hover) {
      const cell = scale / grid.half;
      ctx.fillStyle = "rgba(200,30,30,.34)";
      for (let cy = 0; cy < grid.height; cy++)
        for (let cx = 0; cx < grid.width; cx++) {
          if (grid.m[cy * grid.width + cx] === "0")
            ctx.fillRect(cx * cell, (grid.height - cy - 1) * cell, cell, cell);
        }
      if (!hover) return;
      const ok = placement.allowed(grid, hover);
      ctx.lineWidth = 2;
      ctx.strokeStyle = ok ? "#fff" : "#ff5a4a";
      ctx.fillStyle = ok ? "rgba(255,255,255,.25)" : "rgba(255,90,74,.25)";
      ctx.beginPath();
      ctx.arc(
        hover.x * scale,
        (grid.height / grid.half - hover.y) * scale,
        scale * 0.75,
        0,
        7,
      );
      ctx.fill();
      ctx.stroke();
    },
  });
  window.BattleRenderer = Object.freeze({
    placement,
    create,
    iconOf,
    pretty,
    lerp,
    colors: C,
  });
})();

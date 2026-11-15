/* Shared battle graphics for live play and standalone saved replays.
 * Coordinates and radii in the drawing contract are tiles, Blue at the bottom.
 * en: [uid, team, kind, card, x, y, hp, maxHp, radius, flags, towerSlot, facingX, facingY, stunTicks, footprint,
 *      shield, statusFlags, charge, unitType]
 * footprint: optional [x0, y0, x1, y1] in tiles. shield: shield hp left (0 none). statusFlags: the engine's
 * status bits, -1 when not reported. charge: build-up in permille, -1 when not reported. unitType: the
 * engine's unit-type name (a Golem's Golemite keeps the Golem card), null when not reported.
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

  // Ground troops from the seven classic decks get upright three-quarter miniatures, as units
  // are seen on the battle reference video, instead of top-down tokens that spin with facing.
  // Spawned units keep their card's ID, so en[18] (the engine's unit-type name) picks the unit;
  // old traces without it fall back to the card and, for Golem and Battle Ram, the unit radius.
  const GROUND_CARDS = new Set(["Archer", "BattleRam", "ElectroWizard", "Giant", "GoblinGang", "Golem",
    "HogRider", "IceGolemite", "IceSpirits", "Knight", "MiniPekka", "Musketeer", "Pekka", "Princess",
    "Skeletons", "Wizard"]);
  const UNIT_ALIAS = Object.freeze({Goblin_Stab: "Goblin", Goblins: "Goblin", GoblinGang: "Goblin",
    Skeletons: "Skeleton", IceSpirits: "IceSpirit", Barbarians: "Barbarian", Golemites: "Golemite"});
  function groundUnit(card, unit, radius, flying) {
    if (flying || !GROUND_CARDS.has(card)) return null;
    let key = unit || card;
    if (!unit && radius < 0.62 && card === "Golem") key = "Golemite";
    if (!unit && radius < 0.62 && card === "BattleRam") key = "Barbarian";
    key = UNIT_ALIAS[key] || key;
    return GROUND_ART.has(key) ? key : null;
  }
  const GROUND_ART = new Set(["Archer", "BattleRam", "Barbarian", "ElectroWizard", "Giant", "Goblin",
    "SpearGoblin", "Golem", "Golemite", "HogRider", "IceGolemite", "IceSpirit", "Knight", "MiniPekka",
    "Musketeer", "Pekka", "Princess", "Skeleton", "Wizard"]);
  // Screen-space facing to a pose: mirror for leftward motion and show the back when walking
  // up the screen. The vector already includes board flipping.
  function poseOf(screenX, screenY) {
    const n = Math.hypot(screenX, screenY);
    if (!(n > 1e-6)) return {dir: 1, back: false};
    return {dir: screenX / n < -0.2 ? -1 : 1, back: screenY / n < -0.5};
  }

  const pretty = (n) => n.replace(/([a-z])([A-Z])/g, "$1 $2");
  const lerp = (a, b, t) => a + (b - a) * t;
  const isFlight = (s) => !s[6] || s[6] === "FLIGHT" || s[6] === "AIRBORNE";
  const spKey = (sp) => sp[0] + "|" + sp[1] + "|" + sp[4] + "|" + sp[5];

  const grain = (x, y) => ((x * 73 + y * 151 + x * y * 17) % 101) / 101;

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
      spellFrom = new Map();
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
      for (const [k, sp] of s.spBy)
        if (!spellFrom.has(k)) spellFrom.set(k, [sp[2], sp[3]]);
      if (prev)
        for (const [k, sp] of prev.spBy)
          if (!s.spBy.has(k)) {
            // a travelling spell has arrived
            spellFrom.delete(k);
            if (isFlight(sp))
              fx.push({
                kind: "boom",
                x: sp[4],
                y: sp[5],
                team: sp[0],
                at: now,
              });
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
    function rounded(x, y, w, h, rad, fill, stroke = null, width = 0.07) {
      ctx.beginPath();
      ctx.roundRect(x, y, w, h, rad);
      ctx.fillStyle = fill;
      ctx.fill();
      if (stroke) {
        ctx.strokeStyle = stroke;
        ctx.lineWidth = width;
        ctx.stroke();
      }
    }
    function line(points, color, width) {
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(points[0][0], points[0][1]);
      for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
      ctx.stroke();
    }
    // Upright miniature in unit space: x = 1 is one radius forward, the feet stand at y ≈ 0.5.
    // The figure keeps the entity centre, radius and hit target; only its pose follows facing.
    function drawGroundTroop(unit, px, py, r, fill, edge, hit, pose) {
      const w = (c) => (hit > 0 ? "#fff" : c), back = pose.back;
      const OUT = "#2f3438", SKIN = "#e3ad82";
      const eyes = (hx, hy, color = "#2b3237", size = 1) => {
        if (back) return;
        disk(hx + 0.13, hy, 0.05 * size, 0.07 * size, color);
        disk(hx - 0.07, hy, 0.045 * size, 0.07 * size, color);
      };
      const legs = (color, top, len, width, spread) => {
        rounded(-spread - width / 2, top, width, len, width * 0.35, color, OUT, 0.05);
        rounded(spread - width / 2, top, width, len, width * 0.35, color, OUT, 0.05);
      };
      const shrink = (s) => {
        ctx.translate(0, 0.52);
        ctx.scale(s, s);
        ctx.translate(0, -0.52);
      };
      ctx.save();
      ctx.translate(px, py);
      ctx.scale(pose.dir * r, r);
      const big = /Giant|Golem$|Pekka$|HogRider|BattleRam/.test(unit) && unit !== "MiniPekka";
      disk(0.06, 0.6, big ? 0.92 : 0.78, 0.26, "rgba(14,27,20,.32)");
      disk(0, 0.55, big ? 0.82 : 0.66, 0.25, edge);
      disk(0, 0.52, big ? 0.66 : 0.52, 0.17, "#d3c49d");
      if (/Goblin|Skeleton|IceSpirit/.test(unit)) shrink(unit === "IceSpirit" ? 0.78 : 0.86);
      switch (unit) {
        case "Knight":
        case "Barbarian": {
          const barb = unit === "Barbarian";
          legs(barb ? "#6b4a2f" : "#4a4f5c", 0.12, 0.4, 0.2, 0.15);
          rounded(-0.37, -0.34, 0.74, 0.62, 0.17, w(barb ? "#9a6a3d" : "#aeb6bd"), OUT);
          if (barb) rounded(-0.37, 0.02, 0.74, 0.12, 0.04, fill);
          else polygon([[-0.2, -0.3], [0.2, -0.3], [0.16, 0.28], [0, 0.36], [-0.16, 0.28]], w(fill), OUT, 0.05);
          disk(-0.37, -0.24, 0.16, 0.13, barb ? w(SKIN) : "#cbd2d8", OUT, 0.05);
          disk(0.4, -0.12, 0.13, 0.13, w(SKIN), OUT, 0.05);
          disk(0, -0.62, 0.3, 0.3, w(SKIN), "#5b544c", 0.07);
          if (barb) {
            polygon([[-0.32, -0.62], [-0.3, -0.84], [0, -0.95], [0.3, -0.84], [0.32, -0.62]], "#9aa3aa", OUT, 0.05);
            polygon([[-0.3, -0.78], [-0.56, -0.98], [-0.42, -0.7]], "#f1ead2", OUT, 0.04);
            polygon([[0.3, -0.78], [0.56, -0.98], [0.42, -0.7]], "#f1ead2", OUT, 0.04);
            if (!back) polygon([[-0.16, -0.5], [0.3, -0.5], [0.12, -0.24], [-0.04, -0.3]], "#e9c24c", "#9a7a26", 0.04);
          } else {
            polygon([[-0.31, -0.6], [-0.27, -0.84], [0, -0.94], [0.27, -0.84], [0.31, -0.6], [0.08, -0.74]],
              "#c58a3a", "#7a5420", 0.04);
            if (!back) disk(0.1, -0.5, 0.15, 0.05, "#e2b04a");
          }
          if (back) disk(0, -0.64, 0.29, 0.27, barb ? "#e9c24c" : "#c58a3a");
          eyes(0.02, -0.64);
          line([[0.42, 0.0], [0.8, -0.78]], "#dfe6ea", 0.11);
          line([[0.3, -0.06], [0.54, 0.08]], "#7a5a2a", 0.08);
          break;
        }
        case "Archer":
        case "Princess": {
          const princess = unit === "Princess", hair = princess ? "#f0cf5a" : "#e2549b";
          if (!back) polygon([[-0.3, -0.36], [0.24, -0.36], [0.4, 0.34], [-0.46, 0.34]], w(fill), OUT, 0.05);
          legs("#5b4636", 0.14, 0.38, 0.16, 0.13);
          polygon([[-0.3, -0.36], [0.3, -0.36], [0.38, 0.22], [-0.38, 0.22]],
            w(princess ? "#f2e6d0" : "#5f9a4a"), OUT, 0.06);
          rounded(-0.32, -0.06, 0.64, 0.09, 0.03, princess ? fill : "#7a5428");
          if (back) polygon([[-0.32, -0.38], [0.32, -0.38], [0.46, 0.32], [-0.46, 0.32]], w(fill), OUT, 0.05);
          disk(0, -0.62, 0.28, 0.28, w(SKIN), "#5b544c", 0.07);
          polygon([[-0.32, -0.56], [-0.28, -0.84], [0.02, -0.94], [0.28, -0.82], [0.3, -0.64], [0.06, -0.78]],
            hair, OUT, 0.04);
          disk(-0.34, -0.48, 0.11, 0.2, hair, OUT, 0.04);
          if (back) disk(0, -0.64, 0.27, 0.26, hair);
          if (princess) polygon([[-0.16, -0.86], [-0.12, -1.02], [-0.03, -0.92], [0.05, -1.04], [0.13, -0.92],
            [0.2, -1.0], [0.2, -0.84]], "#f6d14a", "#8a6a22", 0.035);
          eyes(0.02, -0.62);
          ctx.strokeStyle = "#6a412c";
          ctx.lineWidth = 0.12;
          ctx.beginPath();
          ctx.arc(0.32, -0.2, 0.46, -1.25, 1.25);
          ctx.stroke();
          line([[0.46, -0.64], [0.46, 0.24]], "#eee5c5", 0.035);
          if (princess) {
            line([[0.2, -0.2], [0.72, -0.2]], "#c9a36a", 0.04);
            disk(0.76, -0.2, 0.09, 0.07, "#ff9a3c", "#ffd36a", 0.03);
          }
          break;
        }
        case "Musketeer": {
          legs("#3a3550", 0.14, 0.38, 0.16, 0.13);
          polygon([[-0.3, -0.36], [0.3, -0.36], [0.42, 0.3], [-0.42, 0.3]], w("#4b3f6e"), OUT, 0.06);
          polygon([[-0.24, -0.36], [-0.06, -0.36], [0.3, 0.1], [0.14, 0.18]], fill, OUT, 0.04);
          disk(0, -0.6, 0.28, 0.28, w(SKIN), "#5b544c", 0.07);
          disk(-0.24, -0.46, 0.12, 0.2, "#6e4aa0", OUT, 0.04);
          polygon([[-0.42, -0.66], [0.44, -0.66], [0.28, -0.74], [0.18, -0.92], [-0.18, -0.92], [-0.28, -0.74]],
            "#b8c0c8", "#59616a", 0.05);
          if (back) disk(0, -0.58, 0.26, 0.22, "#6e4aa0");
          eyes(0.02, -0.58);
          line([[0.02, 0.04], [0.98, -0.34]], "#3c4149", 0.1);
          line([[-0.12, 0.1], [0.34, -0.08]], "#8a5a32", 0.15);
          break;
        }
        case "Wizard":
        case "ElectroWizard": {
          const electro = unit === "ElectroWizard";
          polygon([[-0.3, -0.36], [0.3, -0.36], [0.46, 0.46], [-0.46, 0.46]],
            w(electro ? "#2f3e66" : fill), OUT, 0.06);
          polygon([[-0.08, -0.36], [0.08, -0.36], [0.12, 0.46], [-0.12, 0.46]], electro ? fill : "#f2e6d0");
          disk(0, -0.6, 0.28, 0.28, w(SKIN), "#5b544c", 0.07);
          if (electro) {
            polygon([[-0.3, -0.62], [-0.42, -0.94], [-0.18, -0.84], [-0.06, -1.08], [0.06, -0.86], [0.22, -1.04],
              [0.26, -0.82], [0.4, -0.9], [0.3, -0.6]], "#8fd8ff", "#2d77a8", 0.04);
            if (back) disk(0, -0.62, 0.27, 0.25, "#8fd8ff");
            eyes(0.02, -0.6, "#1b6fb8");
            for (const [ox, oy] of [[0.5, -0.12], [-0.48, -0.06]]) {
              disk(ox, oy, 0.17, 0.17, "#bff0ff", "#3fa9f5", 0.06);
              line([[ox - 0.1, oy - 0.26], [ox + 0.04, oy - 0.14], [ox - 0.04, oy - 0.06], [ox + 0.1, oy + 0.08]],
                "#ffffff", 0.04);
            }
          } else {
            polygon([[-0.34, -0.62], [0.34, -0.62], [0.2, -0.86], [0.04, -1.2], [-0.2, -0.86]],
              w(fill), OUT, 0.05);
            if (back) disk(0, -0.6, 0.26, 0.24, "#7a5a3a");
            else polygon([[-0.14, -0.5], [0.3, -0.5], [0.12, -0.18]], "#8a6a4a", OUT, 0.03);
            eyes(0.02, -0.64);
            disk(0.56, -0.18, 0.2, 0.2, "#f6b24b", "#fff0b0", 0.06);
            disk(0.56, -0.2, 0.09, 0.09, "#fff6c8");
          }
          break;
        }
        case "Giant": {
          legs("#6b4a2f", 0.08, 0.44, 0.3, 0.26);
          rounded(-0.6, -0.48, 1.2, 0.86, 0.32, w("#8b5a35"), OUT, 0.08);
          rounded(-0.58, 0.08, 1.16, 0.13, 0.04, fill);
          line([[-0.42, -0.42], [0.36, 0.08]], "#5e3a20", 0.1);
          disk(-0.66, -0.06, 0.2, 0.3, w(SKIN), OUT, 0.05);
          disk(0.7, -0.02, 0.24, 0.26, w(SKIN), OUT, 0.06);
          disk(0, -0.7, 0.3, 0.3, w(SKIN), "#5b544c", 0.07);
          polygon([[-0.3, -0.72], [-0.24, -0.96], [0.04, -1.04], [0.28, -0.94], [0.3, -0.72], [0.08, -0.84]],
            "#c8642a", OUT, 0.04);
          if (back) disk(0, -0.72, 0.29, 0.27, "#c8642a");
          else polygon([[-0.16, -0.6], [0.3, -0.6], [0.14, -0.38], [-0.06, -0.42]], "#c8642a", OUT, 0.03);
          eyes(0.03, -0.72);
          break;
        }
        case "Golem":
        case "Golemite":
        case "IceGolemite": {
          const ice = unit === "IceGolemite", stone = ice ? "#a9e3f0" : "#8d8577",
            dark = ice ? "#5b9fb3" : "#5a5248", glow = ice ? "#e9fbff" : "#ffd65a";
          if (unit === "Golemite") shrink(0.86);
          rounded(-0.26, 0.04, 0.2, 0.46, 0.08, dark, OUT, 0.05);
          rounded(0.06, 0.04, 0.2, 0.46, 0.08, dark, OUT, 0.05);
          polygon([[-0.62, -0.38], [-0.24, -0.6], [0.3, -0.56], [0.62, -0.3], [0.54, 0.24], [0.04, 0.36],
            [-0.52, 0.22]], w(stone), OUT, 0.07);
          line([[-0.2, -0.28], [0.02, -0.06], [-0.08, 0.16]], dark, 0.05);
          polygon([[0, -0.2], [0.13, -0.05], [0, 0.1], [-0.13, -0.05]], fill, OUT, 0.04);
          disk(-0.7, -0.08, 0.2, 0.28, w(stone), OUT, 0.06);
          disk(0.7, -0.02, 0.23, 0.27, w(stone), OUT, 0.06);
          polygon([[-0.28, -0.6], [-0.22, -0.9], [0.14, -0.96], [0.32, -0.78], [0.26, -0.56]], w(stone), OUT, 0.06);
          if (!ice && unit === "Golem") disk(-0.12, -0.92, 0.12, 0.05, "#6f9b4b");
          if (!back) {
            disk(0.18, -0.74, 0.055, 0.045, glow);
            disk(0, -0.74, 0.05, 0.045, glow);
          }
          break;
        }
        case "IceSpirit": {
          polygon([[-0.3, -0.36], [-0.2, -0.7], [-0.04, -0.46], [0.08, -0.82], [0.18, -0.46], [0.34, -0.66],
            [0.34, -0.3]], "#e9fbff", "#5fb4d1", 0.05);
          disk(0, 0.02, 0.4, 0.46, w("#bfefff"), "#5fb4d1", 0.07);
          rounded(-0.36, 0.06, 0.72, 0.12, 0.05, fill);
          eyes(0.0, -0.12, "#1f5f86", 1.4);
          break;
        }
        case "HogRider": {
          for (const lx of [-0.5, -0.24, 0.26, 0.5]) rounded(lx - 0.07, 0.2, 0.14, 0.32, 0.05, "#5e3e33", OUT, 0.04);
          disk(-0.04, 0.12, 0.76, 0.38, w("#8c5b4a"), OUT, 0.07);
          disk(0.64, 0.02, 0.3, 0.27, w("#a86f5c"), OUT, 0.06);
          disk(0.88, 0.08, 0.12, 0.1, "#e3a08a", OUT, 0.04);
          polygon([[0.74, 0.14], [0.86, 0.22], [0.74, 0.22]], "#f6f0dc");
          disk(0.6, -0.2, 0.08, 0.1, "#6e4639");
          if (!back) disk(0.72, -0.04, 0.035, 0.045, "#2b3237");
          rounded(-0.34, -0.66, 0.56, 0.64, 0.18, w(fill), OUT, 0.06);
          disk(-0.06, -0.92, 0.24, 0.24, w(SKIN), "#5b544c", 0.06);
          polygon([[-0.1, -1.12], [-0.02, -1.3], [0.06, -1.12]], "#2b2b2b");
          rounded(-0.16, -1.2, 0.2, 0.12, 0.05, "#2b2b2b");
          eyes(-0.06, -0.92);
          line([[0.12, -0.5], [0.44, -1.0]], "#7a5a2a", 0.08);
          rounded(0.3, -1.16, 0.3, 0.22, 0.05, "#8f979e", OUT, 0.05);
          break;
        }
        case "BattleRam": {
          for (const bx of [-0.42, 0.22]) {
            rounded(bx - 0.16, 0.06, 0.12, 0.42, 0.04, "#6b4a2f", OUT, 0.04);
            rounded(bx + 0.04, 0.06, 0.12, 0.42, 0.04, "#6b4a2f", OUT, 0.04);
            rounded(bx - 0.24, -0.42, 0.48, 0.5, 0.14, w(SKIN), OUT, 0.05);
            rounded(bx - 0.24, -0.08, 0.48, 0.1, 0.03, fill);
            disk(bx, -0.62, 0.2, 0.2, w(SKIN), "#5b544c", 0.05);
            polygon([[bx - 0.22, -0.64], [bx - 0.2, -0.8], [bx, -0.88], [bx + 0.2, -0.8], [bx + 0.22, -0.64]],
              "#9aa3aa", OUT, 0.04);
            polygon([[bx - 0.2, -0.76], [bx - 0.38, -0.92], [bx - 0.28, -0.68]], "#f1ead2");
            polygon([[bx + 0.2, -0.76], [bx + 0.38, -0.92], [bx + 0.28, -0.68]], "#f1ead2");
            eyes(bx, -0.6, "#2b3237", 0.8);
          }
          rounded(-0.86, -0.24, 1.6, 0.34, 0.15, w("#8a5a32"), "#4e3219", 0.07);
          for (const rx of [-0.5, 0.2]) rounded(rx, -0.26, 0.08, 0.38, 0.02, "#6c7378");
          disk(0.84, -0.07, 0.22, 0.22, "#9aa3aa", OUT, 0.06);
          polygon([[0.86, -0.22], [1.06, -0.36], [0.98, -0.1]], "#d9d2b8", OUT, 0.03);
          break;
        }
        case "Goblin":
        case "SpearGoblin": {
          const spear = unit === "SpearGoblin";
          legs("#5b4636", 0.14, 0.36, 0.16, 0.12);
          polygon([[-0.28, -0.3], [0.28, -0.3], [0.34, 0.22], [-0.34, 0.22]], w("#875638"), OUT, 0.06);
          rounded(-0.3, -0.04, 0.6, 0.1, 0.03, fill);
          disk(0, -0.56, 0.3, 0.27, w("#8ccc55"), "#4e7135", 0.06);
          polygon([[-0.26, -0.6], [-0.7, -0.78], [-0.36, -0.42]], "#8ccc55", "#4e7135", 0.04);
          polygon([[0.26, -0.6], [0.7, -0.78], [0.36, -0.42]], "#8ccc55", "#4e7135", 0.04);
          if (spear) polygon([[-0.3, -0.6], [-0.2, -0.82], [0.06, -0.9], [0.28, -0.78], [0.3, -0.6]],
            "#7a4a8a", OUT, 0.04);
          if (back) disk(0, -0.56, 0.28, 0.24, spear ? "#7a4a8a" : "#7cb84a");
          eyes(0.02, -0.56, "#2b3237", 1.1);
          if (spear) {
            line([[0.34, 0.3], [0.62, -0.92]], "#8a6a3a", 0.07);
            polygon([[0.56, -0.9], [0.66, -1.12], [0.72, -0.88]], "#c8d0d4", OUT, 0.03);
          } else {
            line([[0.36, -0.02], [0.62, -0.36]], "#dfe6ea", 0.09);
          }
          break;
        }
        case "Skeleton": {
          line([[-0.12, 0.14], [-0.16, 0.5]], "#e7e4ce", 0.08);
          line([[0.12, 0.14], [0.16, 0.5]], "#e7e4ce", 0.08);
          disk(-0.3, -0.06, 0.17, 0.21, fill, OUT, 0.05);
          rounded(-0.2, -0.3, 0.4, 0.46, 0.1, w("#e7e4ce"), "#7d7a68", 0.05);
          for (const ry of [-0.2, -0.08, 0.04]) line([[-0.12, ry], [0.12, ry]], "#7d7a68", 0.04);
          disk(0, -0.56, 0.3, 0.28, w("#efecd8"), "#7d7a68", 0.06);
          if (!back) {
            disk(0.13, -0.58, 0.08, 0.1, "#323a42");
            disk(-0.07, -0.58, 0.08, 0.1, "#323a42");
            rounded(-0.04, -0.38, 0.16, 0.06, 0.02, "#5b5650");
          }
          line([[0.3, -0.04], [0.56, -0.44]], "#dfe6ea", 0.08);
          break;
        }
        case "MiniPekka":
        case "Pekka": {
          const mini = unit === "MiniPekka", armor = mini ? "#5f78a8" : "#3f3d66", rim = mini ? "#2f3f63" : "#24223f";
          legs(rim, 0.1, 0.42, mini ? 0.2 : 0.26, mini ? 0.16 : 0.22);
          rounded(mini ? -0.36 : -0.5, -0.36, mini ? 0.72 : 1.0, 0.64, 0.2, w(armor), rim, 0.08);
          disk(mini ? -0.38 : -0.52, -0.26, mini ? 0.15 : 0.22, 0.14, fill, rim, 0.05);
          disk(mini ? 0.4 : 0.54, -0.2, mini ? 0.14 : 0.2, 0.14, fill, rim, 0.05);
          disk(0, mini ? -0.6 : -0.66, mini ? 0.4 : 0.34, mini ? 0.34 : 0.32, w(armor), rim, 0.07);
          const hy = mini ? -0.66 : -0.74;
          polygon([[-0.26, hy], [-0.5, hy - 0.36], [-0.12, hy - 0.16]], mini ? "#d7dde4" : "#5a568a", rim, 0.04);
          polygon([[0.26, hy], [0.5, hy - 0.36], [0.12, hy - 0.16]], mini ? "#d7dde4" : "#5a568a", rim, 0.04);
          if (!back) {
            if (mini) rounded(-0.18, -0.64, 0.42, 0.08, 0.03, "#bfe8ff");
            else disk(0.1, -0.66, 0.08, 0.06, "#b7f2ff", "#ffffff", 0.02);
          }
          line([[0.48, 0.02], [mini ? 0.82 : 0.96, mini ? -0.78 : -1.02]], mini ? "#dfe6ea" : "#c9d5ff", mini ? 0.12 : 0.14);
          line([[0.34, -0.04], [0.62, 0.1]], "#5c5c66", 0.08);
          break;
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
        const unit = groundUnit(name, e[18], rad, flying);
        if (unit) drawGroundTroop(unit, px, py, r, fill, edge, hit, poseOf(screenX, screenY));
        else drawTroop(name, px, py, r, fill, edge, hit, facing);
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
        if (f.kind === "boom") {
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
          col = sp[0] === 0 ? C.blue : C.red;
        ctx.strokeStyle = col;
        ctx.fillStyle = "#7a4a1f";
        ctx.lineWidth = 2;
        if (sp[6] === "ROLLING") {
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

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
    // Terrain, sampled from Arena 1 reference frames and toned down slightly.
    grassA: "#acc547",
    grassB: "#a2bc41",
    lane: "#93aa40",
    water: "#34dcc8",
    waterLight: "#7cf0dc",
    waterShade: "#2f6a52",
    waterDeep: "#2ab9a8",
    bankShadow: "#6d7e27",
    tuft: "#86a033",
    lily: "#4cb772",
    lilyEdge: "#2f8a55",
    bridge: "#e8bd6a",
    bridgeLight: "#f6d996",
    bridgeEdge: "#b98a49",
    bridgeDark: "#8f6532",
    plankSeam: "rgba(150,104,48,.75)",
    plankGrain: "rgba(176,128,64,.55)",
    fence: "#7f5838",
    fenceDark: "#553823",
    dirt: "#6e5a32",
    edgeShade: "rgba(60,70,20,.28)",
    bush: "#5daa3c",
    bushEdge: "#33772a",
    bushLight: "#86c95a",
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
      // Arena 1 terrain, colour-matched to sampled frames of the reference video.
      // Water and bridge cells come from the simulator grid; nothing is assumed
      // about where the river or bridges sit.
      const half = arena.half,
        grid = arena.grid,
        water = arena.water_half_rows,
        W = TX * T,
        H = TY * T,
        cell = T / half,
        isWater = (hy, hx) => !!(grid[hy][hx] & arena.bits.WATER);
      // Screen rectangle of a tile-space box, whichever way the board is flipped.
      const box = (x0, y0, x1, y1) => {
        const ax = X(x0),
          bx = X(x1),
          ay = Y(y0),
          by = Y(y1);
        return [Math.min(ax, bx), Math.min(ay, by), Math.abs(bx - ax), Math.abs(by - ay)];
      };
      // Bridges: runs of non-water cells within each river half-row.
      const runs = [];
      for (let hy = water[0]; hy <= water[1]; hy++)
        for (let hx = 0; hx < grid[hy].length; ) {
          if (isWater(hy, hx)) {
            hx++;
            continue;
          }
          const start = hx;
          while (hx < grid[hy].length && !isWater(hy, hx)) hx++;
          runs.push({ hy, x0: start / half, x1: hx / half });
        }
      // A bridge is the vertical union of overlapping runs; its deck extends
      // a little onto both banks, as in the reference.
      const bridges = [];
      for (const r of runs) {
        const b = bridges.find((q) => r.x0 < q.x1 && r.x1 > q.x0 && r.hy === q.hy1 + 1);
        if (b) {
          b.x0 = Math.min(b.x0, r.x0);
          b.x1 = Math.max(b.x1, r.x1);
          b.hy1 = r.hy;
        } else bridges.push({ x0: r.x0, x1: r.x1, hy0: r.hy, hy1: r.hy });
      }
      const riverY0 = water[0] / half,
        riverY1 = (water[1] + 1) / half,
        lip = 0.5;

      // Grass: a soft two-tone tile checker.
      ctx.fillStyle = C.grassA;
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = C.grassB;
      for (let ty = 0; ty < TY; ty++)
        for (let tx = (ty + 1) % 2; tx < TX; tx += 2) ctx.fillRect(...box(tx, ty, tx + 1, ty + 1));
      // Worn lanes run from each bridge towards the princess towers.
      ctx.fillStyle = C.lane;
      for (const b of bridges) {
        const inset = Math.min(0.35, (b.x1 - b.x0) * 0.2);
        ctx.fillRect(...box(b.x0 + inset, TY * 0.22, b.x1 - inset, riverY0));
        ctx.fillRect(...box(b.x0 + inset, riverY1, b.x1 - inset, TY * 0.78));
      }

      // River: water cells only, with a shaded upper bank and a bright lower lip.
      for (let hy = water[0]; hy <= water[1]; hy++)
        for (let hx = 0; hx < grid[hy].length; hx++)
          if (isWater(hy, hx)) {
            ctx.fillStyle = C.water;
            ctx.fillRect(...box(hx / half, hy / half, (hx + 1) / half, (hy + 1) / half).map((v, i) => (i > 1 ? v + 0.6 : v)));
          }
      const [, ry, , rh] = box(0, riverY0, TX, riverY1);
      for (let hy = water[0]; hy <= water[1]; hy++)
        for (let hx = 0; hx < grid[hy].length; hx++) {
          if (!isWater(hy, hx)) continue;
          const [x] = box(hx / half, 0, (hx + 1) / half, 1);
          ctx.fillStyle = C.waterShade;
          ctx.fillRect(x, ry, cell + 0.6, rh * 0.2);
          ctx.fillStyle = C.waterDeep;
          ctx.fillRect(x, ry + rh * 0.2, cell + 0.6, rh * 0.08);
          ctx.fillStyle = C.waterLight;
          ctx.fillRect(x, ry + rh * 0.9, cell + 0.6, rh * 0.1);
        }
      // Lily pads at fixed spots, kept off bridges.
      for (let tx = 1; tx < TX - 1; tx++) {
        if (grain(tx, 7) < 0.6) continue;
        const px = tx + 0.2 + grain(tx, 3) * 0.6,
          py = riverY0 + (riverY1 - riverY0) * (0.35 + grain(tx, 5) * 0.4),
          hx = Math.floor(px * half),
          hy = Math.floor(py * half);
        if (!grid[hy] || !isWater(hy, hx) || !isWater(hy, Math.max(0, hx - 1)) || !isWater(hy, Math.min(grid[hy].length - 1, hx + 1))) continue;
        disk(X(px), Y(py), T * 0.32, T * 0.24, C.lily, C.lilyEdge, Math.max(1, T * 0.05));
      }
      // Bank edges: a dark lip above the water and grass tufts over both edges.
      ctx.fillStyle = C.bankShadow;
      ctx.fillRect(0, ry - T * 0.08, W, T * 0.08);
      ctx.strokeStyle = C.tuft;
      ctx.lineWidth = Math.max(1, T * 0.05);
      ctx.beginPath();
      for (let i = 0; i <= TX * 4; i++) {
        const x = (i / 4) * T,
          up = grain(i, 11) * T * 0.1;
        ctx.moveTo(x, ry - T * 0.08);
        ctx.lineTo(x + T * 0.05, ry - T * 0.08 + T * 0.06 + up);
        ctx.moveTo(x, ry + rh);
        ctx.lineTo(x + T * 0.05, ry + rh - T * 0.05 - up);
      }
      ctx.stroke();

      // Bridges: plank decks sized from the grid runs, with rails on both sides.
      for (const b of bridges) {
        const y0 = b.hy0 / half - (b.hy0 === water[0] ? lip : 0),
          y1 = (b.hy1 + 1) / half + (b.hy1 === water[1] ? lip : 0),
          [x, y, w, h] = box(b.x0, y0, b.x1, y1),
          rail = Math.max(2, T * 0.12);
        ctx.fillStyle = "rgba(20,60,40,.28)";
        ctx.fillRect(x + T * 0.12, y + T * 0.12, w, h);
        ctx.fillStyle = C.bridge;
        ctx.fillRect(x, y, w, h);
        // Planks run along the crossing, so seams are vertical on screen.
        const planks = Math.max(2, Math.round(((b.x1 - b.x0) * 4) / 2));
        ctx.strokeStyle = C.plankSeam;
        ctx.lineWidth = Math.max(1, T * 0.04);
        ctx.beginPath();
        for (let i = 1; i < planks; i++) {
          const sx = x + (w * i) / planks;
          ctx.moveTo(sx, y + 1);
          ctx.lineTo(sx, y + h - 1);
        }
        ctx.stroke();
        // Wavy grain, deterministic per plank.
        ctx.strokeStyle = C.plankGrain;
        ctx.lineWidth = Math.max(1, T * 0.025);
        ctx.beginPath();
        for (let i = 0; i < planks; i++) {
          const gx = x + (w * (i + 0.5)) / planks,
            amp = (w / planks) * 0.12;
          ctx.moveTo(gx, y + h * 0.08);
          for (let k = 1; k <= 8; k++) ctx.lineTo(gx + (k % 2 ? amp : -amp) * (0.5 + grain(i, k)), y + h * (0.08 + k * 0.105));
        }
        ctx.stroke();
        ctx.fillStyle = C.bridgeEdge;
        ctx.fillRect(x, y, rail, h);
        ctx.fillRect(x + w - rail, y, rail, h);
        ctx.fillStyle = C.bridgeLight;
        ctx.fillRect(x + rail, y, w - 2 * rail, Math.max(1, T * 0.06));
        ctx.fillStyle = C.bridgeDark;
        ctx.fillRect(x, y + h - Math.max(2, T * 0.1), w, Math.max(2, T * 0.1));
      }

      // Border: a wooden palisade on the sides and a dirt edge top and bottom.
      const post = Math.max(3, T * 0.2);
      ctx.fillStyle = C.edgeShade;
      ctx.fillRect(post, 0, T * 0.12, H);
      ctx.fillRect(W - post - T * 0.12, 0, T * 0.12, H);
      ctx.fillStyle = C.fence;
      ctx.fillRect(0, 0, post, H);
      ctx.fillRect(W - post, 0, post, H);
      ctx.fillStyle = C.fenceDark;
      for (let i = 0; i < TY * 2; i++) {
        const y = (i * T) / 2;
        ctx.fillRect(0, y, post, Math.max(1, T * 0.05));
        ctx.fillRect(W - post, y, post, Math.max(1, T * 0.05));
      }
      ctx.fillStyle = C.edgeShade;
      ctx.fillRect(0, post, W, T * 0.1);
      ctx.fillRect(0, H - post - T * 0.1, W, T * 0.1);
      ctx.fillStyle = C.dirt;
      ctx.fillRect(0, 0, W, post);
      ctx.fillRect(0, H - post, W, post);
      // Bushes where the river meets the palisade.
      for (const ex of [0, TX])
        for (const ey of [riverY0 - 0.35, riverY1 + 0.35]) {
          disk(X(ex), Y(ey), T * 0.62, T * 0.5, C.bush, C.bushEdge, Math.max(1, T * 0.05));
          disk(X(ex), Y(ey) - T * 0.12, T * 0.36, T * 0.26, C.bushLight);
        }
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

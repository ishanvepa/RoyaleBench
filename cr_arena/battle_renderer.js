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
  // Indicator inks: a dark outline keeps bars and text legible on grass, water and units alike.
  const INK = "#111823",
    TRACK = ["#17345e", "#5c2516"],
    TEXT = ["#d7e8ff", "#ffdcca"],
    STUN = "#fff06a",
    CHIP_MS = 700;
  const KING = 2,
    PRINCESS = 3,
    BUILDING = 1;
  // Enlarge troop art for phone screens; buildings and towers retain their arena footprints.
  const TROOP_SCALE = 1.5;
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
  // Flying units from the classic decks. height: flying_height / 1000 (tiles) from RoyaleAPI's
  // cards_stats.json; span: shadow half-width and size: miniature scale, both relative to the unit
  // radius. Other flyers keep the
  // generic winged miniature.
  const AIR = Object.freeze({
    Minions: { height: 1.5, span: 1.15, size: 1.3, flap: 110 },
    MegaMinion: { height: 1.5, span: 1.25, size: 1.35, flap: 130 },
    Bats: { height: 2, span: 1.2, size: 1.25, flap: 70 },
    Balloon: { height: 3, span: 0.95, size: 1.4, flap: 0 },
    BabyDragon: { height: 3.5, span: 1.3, size: 1.45, flap: 150 },
    LavaPups: { height: 3.5, span: 1.1, size: 1.3, flap: 90 },
    LavaHound: { height: 4, span: 1.35, size: 1.45, flap: 220 },
  });
  const AIR_LIFT = 0.3; // screen tiles of lift per tile of flying height (top-down camera)
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
      stunMax = new Map(),
      chip = new Map(),
      towerSites = new Map(),
      spellFrom = new Map(),
      spellSeen = new Map();
    let previous = null,
      drawn = [],
      bars = [];
    const X = (tx) => (flip ? TX - tx : tx) * T;
    const Y = (ty) => (flip ? ty : TY - ty) * T;
    function reset() {
      previous = null;
      fx = [];
      firstSeen.clear();
      hitAt.clear();
      shieldMax.clear();
      stunMax.clear();
      chip.clear();
      towerSites.clear();
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
          else if (n[6] < e[6] || (n[15] || 0) < (e[15] || 0)) {
            hitAt.set(uid, now);
            if (n[6] < e[6]) {
              // Recent damage stays visible on the bar briefly; repeated hits extend one chip.
              const c = chip.get(uid);
              chip.set(uid, { from: c && now - c.at < CHIP_MS ? c.from : e[6], at: now });
            }
          }
        }
      }
      for (const e of s.en) {
        if (e[2] === KING || e[2] === PRINCESS) towerSites.set(e[0], e);
        if (!firstSeen.has(e[0])) firstSeen.set(e[0], prev ? now : -1e9);
        // A stun's full length is the most it has been since it started, so its ring can drain.
        const was = prev?.by.get(e[0]);
        if (!(e[13] > 0)) stunMax.delete(e[0]);
        else if (!stunMax.has(e[0]) || e[13] > (was?.[13] || 0)) stunMax.set(e[0], e[13]);
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
    function bar(x, y, w, h, frac, color, track) {
      const left = x - w / 2;
      ctx.fillStyle = INK;
      ctx.beginPath();
      ctx.roundRect(left - 1, y - 1, w + 2, h + 2, Math.min(3, h / 2 + 1));
      ctx.fill();
      ctx.fillStyle = track;
      ctx.fillRect(left, y, w, h);
      ctx.fillStyle = color;
      ctx.fillRect(left, y, w * Math.max(0, Math.min(1, frac)), h);
    }
    function shieldBar(x, y, w, frac) {
      bar(x, y, w, 3, frac, "#cfe3ff", "#3c4a5c");
    }
    // Health against max, with recently lost health as a pale segment that fades out.
    function hpBar(x, y, w, h, frac, team, lost, lostAlpha) {
      bar(x, y, w, h, frac, team === 0 ? C.blue : C.red, TRACK[team] || TRACK[1]);
      const left = x - w / 2,
        f = Math.max(0, Math.min(1, frac)),
        g = Math.max(f, Math.min(1, lost));
      if (g > f && lostAlpha > 0) {
        ctx.globalAlpha = 0.85 * lostAlpha;
        ctx.fillStyle = "#fff4c2";
        ctx.fillRect(left + w * f, y, w * (g - f), h);
        ctx.globalAlpha = 1;
      }
      if (h >= 5) {
        ctx.fillStyle = "rgba(255,255,255,.32)";
        ctx.fillRect(left, y, w * f, Math.max(1, h * 0.28));
      }
    }
    // Recording canvases used by tests may not measure text; estimate from the font size then.
    function textWidth(text) {
      const w = ctx.measureText(text)?.width;
      return Number.isFinite(w) ? w : text.length * (parseFloat(/(\d+)px/.exec(ctx.font)?.[1]) || 11) * 0.6;
    }
    function outlined(text, x, y, fill, width = 3) {
      ctx.lineWidth = width;
      ctx.strokeStyle = INK;
      ctx.strokeText(text, x, y);
      ctx.fillStyle = fill;
      ctx.fillText(text, x, y);
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
    function drawTower(e, px, py, r, hit, ruined = false) {
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
      const king = e[2] === KING,
        near = (e[5] < TY / 2) !== flip,
        blue = e[1] === 0,
        roof = blue ? "#287ec1" : "#cf404d",
        roofLight = blue ? "#64b6ed" : "#f2767b",
        roofDark = blue ? "#164c83" : "#872d3b";
      // Ground contact stays at the supplied footprint. The camera-facing
      // elevation changes with flipping, while the masonry remains upright.
      polygon([
        [left + width * .1, top + height * .51],
        [left + width * .92, top + height * .71],
        [left + width * .82, top + height * 1.04],
        [left - width * .08, top + height * 1.07],
      ], ruined ? "rgba(32,30,22,.18)" : "rgba(24,31,28,.32)");
      ctx.save();
      // Clip decoration to the exact simulator outline, including optional
      // non-square princess footprints. This does not change tooltip targets.
      ctx.beginPath();
      ctx.roundRect(left, top, width, height, Math.min(6, r * 0.3));
      ctx.clip();
      ctx.translate(left, top);
      ctx.scale(width, height);
      const rect = (x, y, w, h, color) => { ctx.fillStyle = color; ctx.fillRect(x, y, w, h); },
        poly = (points, color, edge = null, line = .012) => polygon(points, color, edge, line),
        oval = (x, y, rx, ry, color, edge = null, line = .012) => disk(x, y, rx, ry, color, edge, line),
        crown = (x, y, w, h) => {
          poly([[x,y+h],[x,y],[x+w*.27,y+h*.31],[x+w*.5,y-h*.13],
            [x+w*.73,y+h*.31],[x+w,y],[x+w,y+h]], "#edbf4b", "#71562e", .018);
          rect(x + w*.07, y + h*.72, w*.86, h*.16, "#ffe58b");
        },
        cap = (x, y, w, h) => {
          rect(x, y + .035, w, h, "#91969a");
          poly([[x,y+.025],[x+.025,y],[x+w,y],[x+w,y+h],
            [x,y+h]], hit > 0 ? "#fff" : "#e7e5da");
          rect(x + .022, y + .012, w - .038, .025, "#faf7e9");
          rect(x + w - .025, y + .028, .025, h - .028, "#bec1bb");
        };
      if (ruined) {
        // The reference leaves a low, pale stone ring and splintered deck,
        // rather than fire or an intact dark tower at zero health.
        poly([[.08,.43],[.76,.37],[.94,.57],[.85,.94],[.13,.92]], "#95866b");
        rect(.22, .51, .57, .3, "#b1976e");
        for (const [x,y] of [[.24,.53],[.38,.56],[.5,.49]])
          poly([[x,y],[x+.045,y-.02],[x+.26,y+.28],[x+.2,y+.3]], "#e2bd7e", "#8d6b43", .01);
        for (const [x,y,w,h] of [[.12,.46,.15,.3],[.27,.4,.25,.13],
          [.56,.43,.27,.12],[.77,.58,.12,.22],[.23,.8,.25,.13],[.54,.79,.19,.12]]) cap(x,y,w,h);
        for (const [x,y] of [[.08,.85],[.82,.9],[.48,.34],[.86,.48]])
          poly([[x,y],[x+.06,y-.02],[x+.095,y+.035],[x+.025,y+.065]], "#ded9c8");
        ctx.restore();
        return;
      }
      const inset = king ? .025 : .12,
        l = inset, rr = 1 - inset, w = rr - l;
      // A shallow side face and staggered cool-gray blocks give the wall
      // depth without moving its simulator anchor or changing its radius.
      poly([[l,.44],[rr,.44],[rr,.88],[rr-.05,.94],[l+.025,.94]], "#515e6a", "#3b4650");
      poly([[rr-.08,.48],[rr,.44],[rr,.88],[rr-.08,.93]], "#46525f");
      poly([[l,.47],[l+.07,.52],[l+.07,.92],[l+.025,.94]], "#7d858b");
      const stones = ["#7e878d", "#747e87", "#879097", "#6d7882"];
      for (let row = 0; row < 3; row++) {
        const y = .54 + row * .12, count = row % 2 ? 4 : 3;
        for (let col = 0; col < count; col++) {
          const bw = (w - .16) / count, x = l + .08 + col * bw;
          rect(x + .006, y, bw - .013, .105, hit > 0 ? "#fff" : stones[(row + col) % stones.length]);
          rect(x + .018, y + .008, bw - .037, .012, "rgba(232,237,227,.16)");
        }
      }
      rect(l+.06, .89, w-.12, .035, "#424f5c");
      for (const x of [l+.13, .5, rr-.13])
        poly([[x-.04,.873],[x+.04,.873],[x,.915]], "#a4aeb4");
      // Timber fighting platform, team-colored coping, and ivory merlons.
      rect(l+.055, .16, w-.11, .4, "#5b4735");
      rect(l+.13, .19, w-.26, .34, "#ac8552");
      for (let i = 0; i < 5; i++) rect(l+.14 + i*(w-.28)/5, .2, .012, .31, "#765a3b");
      rect(l+.015, .25, .13, .29, roofDark);
      rect(rr-.145, .25, .13, .29, roofDark);
      rect(l+.02, .25, .11, .2, roof);
      rect(rr-.135, .25, .11, .2, roof);
      rect(l+.025, .255, .1, .035, roofLight);
      rect(rr-.13, .255, .1, .035, roofLight);
      cap(l, .14, .22, .13); cap(rr-.22, .14, .22, .13);
      if (king && near) {
        // The near king is seen from behind: blue/red hipped roof, recessed
        // doorway and steps, with the gold-rimmed cannon above the ridge.
        rect(.35, .71, .3, .22, "#35434e");
        poly([[.39,.78],[.43,.72],[.57,.72],[.61,.78],[.61,.99],[.39,.99]], roofDark);
        for (let i = 0; i < 4; i++) rect(.405, .81 + i*.043, .19, .02, roof);
        poly([[.2,.52],[.28,.23],[.65,.19],[.79,.55]], "#172e43");
        poly([[.21,.49],[.3,.2],[.65,.2],[.77,.52]], roof, roofDark, .018);
        poly([[.3,.2],[.48,.16],[.65,.2],[.57,.34],[.26,.34]], roofLight);
        poly([[.65,.2],[.77,.52],[.59,.49],[.57,.34]], roofDark);
        rect(.26, .48, .48, .035, roofDark);
        oval(.49,.235,.135,.08,"#273b4b");
        poly([[.39,.22],[.405,.055],[.575,.055],[.61,.22]], "#3d5260", "#1a2937");
        oval(.49,.069,.096,.066,"#dcb748", "#71542a", .018);
        oval(.49,.069,.073,.05,"#101d25");
      } else {
        // Tower occupants belong to the tower miniature, not troop rendering.
        if (king) {
          oval(.5,.37,.2,.13,roofDark);
          poly([[.3,.2],[.69,.2],[.66,.46],[.34,.46]], roof, "#513e35");
          rect(.34,.34,.32,.045,"#523c2e");
          rect(.46,.33,.08,.065,"#edc04c");
          oval(.5,.19,.14,.14,"#dea575", "#724d3a");
          poly([[.37,.18],[.4,.31],[.5,.35],[.61,.29],[.64,.17],[.58,.23],[.43,.23]], "#372c2b");
          oval(.453,.2,.023,.016,"#302b2a"); oval(.547,.2,.023,.016,"#302b2a");
          rect(.44,.265,.12,.02,"#f6e2c6");
          crown(.36,.045,.28,.1);
          oval(.29,.35,.065,.055,"#e6b68a"); oval(.71,.35,.065,.055,"#e6b68a");
          // The reference shows the cannon on the far king after activation.
          // HP loss is the only activation cue present in this drawing contract.
          if (e[6] < e[7]) {
            poly([[.33,.4],[.65,.37],[.69,.51],[.34,.54]], "#303d49");
            rect(.36,.395,.26,.105,"#87939b");
            for (const x of [.38,.47,.59]) rect(x,.39,.025,.12,"#b6bec0");
            oval(.34,.46,.045,.075,"#25313c", "#687782");
          }
        } else {
          oval(.5,.355,.14,.105,roofDark);
          poly([[.39,.24],[.61,.24],[.65,.43],[.35,.43]], roof, roofDark);
          oval(.5,.19,.105,.11,near ? "#333640" : "#dba27f", "#33323a");
          poly([[.394,.19],[.4,.095],[.5,.055],[.595,.1],[.61,.18],[.51,.135],[.43,.21]], "#333640");
          oval(.47,.1,.033,.018,"#a4b7c6");
          if (!near) {
            oval(.46,.2,.014,.015,"#302a30"); oval(.54,.2,.014,.015,"#302a30");
            rect(.455,.248,.09,.018,"#edcaab");
          }
          // Bow, string, and diagonal arrow remain attached to the platform.
          poly([[.36,.28],[.66,.34],[.64,.38],[.35,.32]], "#b98150", "#644b37", .01);
          ctx.strokeStyle = "#d6b17d"; ctx.lineWidth = .025;
          ctx.beginPath(); ctx.moveTo(.39,.22); ctx.quadraticCurveTo(.73,.22,.65,.43); ctx.stroke();
          ctx.strokeStyle = "#eee4c4"; ctx.lineWidth = .009;
          ctx.beginPath(); ctx.moveTo(.39,.22); ctx.lineTo(.65,.43); ctx.stroke();
        }
      }
      cap(l, .46, .22, .13); cap(rr-.22, .46, .22, .13);
      cap(l+.22, .51, w-.44, .08);
      if (!near) {
        rect(.315, .65, .37, .22, "#46515a");
        crown(.35,.68,.3,.14);
      } else if (!king) {
        // Two rails and rungs on the rear wall are prominent in the sample.
        for (const x of [.39,.59]) rect(x,.59,.035,.4,"#bea278");
        for (let i=0; i<4; i++) rect(.4,.65+i*.09,.22,.025,"#dec092");
      }
      // Low-HP reference towers keep their silhouette: no invented fire,
      // missing roof, or percentage-based cracks. Hit flash remains transient.
      ctx.restore();
    }
    // Classic-deck buildings, drawn in units of the entity radius around its centre. Shapes follow
    // gameplay footage (see docs/rendering.md); the weapon turns toward `aim`, 0 meaning screen-up.
    function line(points, stroke, width) {
      ctx.beginPath();
      ctx.moveTo(points[0][0], points[0][1]);
      for (let i = 1; i < points.length; i++) ctx.lineTo(points[i][0], points[i][1]);
      ctx.strokeStyle = stroke;
      ctx.lineWidth = width;
      ctx.stroke();
    }
    function octagon(rx, ry) {
      const pts = [];
      for (let i = 0; i < 8; i++) {
        const a = Math.PI / 8 + (i * Math.PI) / 4;
        pts.push([Math.cos(a) * rx, Math.sin(a) * ry]);
      }
      return pts;
    }
    const BUILDING_ART = {
      Cannon(fill, edge, body, aim) {
        disk(0.1, 0.45, 0.95, 0.38, "rgba(20,29,21,.3)");
        ctx.lineCap = "round";
        for (const [dx, dy] of [[-1, -1], [1, -1], [-1, 1], [1, 1]]) {
          line([[0, 0.05], [dx * 0.76, 0.05 + dy * 0.58]], "#45301d", 0.34);
          line([[0, 0.05], [dx * 0.72, 0.05 + dy * 0.55]], "#a8743f", 0.18);
        }
        polygon(octagon(0.6, 0.52), body("#7d838b"), "#2b3036", 0.1);
        disk(0, -0.02, 0.43, 0.36, fill, edge, 0.08);
        ctx.save();
        ctx.translate(0, -0.05);
        ctx.rotate(aim);
        ctx.fillStyle = body("#4a535e");
        ctx.strokeStyle = "#15191e";
        ctx.lineWidth = 0.08;
        ctx.beginPath();
        ctx.roundRect(-0.2, -1.02, 0.4, 1.02, 0.1);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = "rgba(255,255,255,.28)";
        ctx.fillRect(-0.12, -0.95, 0.07, 0.85);
        ctx.fillStyle = fill;
        ctx.fillRect(-0.23, -0.78, 0.46, 0.15);
        disk(0, -1.0, 0.17, 0.08, "#0d1013");
        ctx.restore();
        disk(0, -0.05, 0.22, 0.2, "#3d444d", "#15191e", 0.05);
      },
      Tombstone(fill, edge, body) {
        disk(0.08, 0.5, 0.85, 0.3, "rgba(20,29,21,.3)");
        disk(0, 0.42, 0.64, 0.25, "#3b2d21", "#241a12", 0.06);
        ctx.beginPath();
        ctx.moveTo(-0.5, 0.45);
        ctx.lineTo(-0.42, -0.38);
        ctx.quadraticCurveTo(-0.42, -0.8, 0, -0.82);
        ctx.quadraticCurveTo(0.42, -0.8, 0.42, -0.38);
        ctx.lineTo(0.5, 0.45);
        ctx.closePath();
        ctx.fillStyle = body("#ccb08d");
        ctx.fill();
        ctx.strokeStyle = "#6b533a";
        ctx.lineWidth = 0.07;
        ctx.stroke();
        polygon([[0.22, -0.66], [0.42, -0.38], [0.5, 0.45], [0.3, 0.45]], "rgba(96,64,32,.22)");
        ctx.fillStyle = fill;
        ctx.strokeStyle = edge;
        ctx.lineWidth = 0.06;
        ctx.beginPath();
        ctx.roundRect(-0.24, -0.2, 0.48, 0.52, 0.06);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = "rgba(255,255,255,.3)";
        ctx.fillRect(-0.19, -0.15, 0.38, 0.08);
        disk(0, -0.5, 0.17, 0.15, "#f3eee2", "#6b533a", 0.04);
        ctx.fillStyle = "#f3eee2";
        ctx.fillRect(-0.08, -0.41, 0.16, 0.08);
        disk(-0.065, -0.51, 0.045, 0.05, "#2a1f16");
        disk(0.065, -0.51, 0.045, 0.05, "#2a1f16");
        disk(-0.44, 0.52, 0.12, 0.07, "#8a7863");
        disk(0.45, 0.48, 0.1, 0.06, "#8a7863");
      },
      InfernoTower(fill, edge, body, aim) {
        disk(0.1, 0.45, 0.9, 0.36, "rgba(20,29,21,.3)");
        disk(0, 0.25, 0.72, 0.38, "#5a2611", "#2e130a", 0.06);
        disk(0, 0.22, 0.58, 0.29, "#ef7322");
        disk(0, 0.2, 0.4, 0.19, "#ffd45c");
        polygon([[-0.36, 0.22], [-0.24, -0.78], [0.24, -0.78], [0.36, 0.22]], body("#3b4048"), "#1c2025", 0.08);
        polygon([[-0.3, 0.18], [-0.21, -0.74], [-0.1, -0.74], [-0.14, 0.18]], "rgba(255,255,255,.14)");
        ctx.fillStyle = "#23272d";
        ctx.fillRect(-0.33, -0.06, 0.66, 0.08);
        ctx.fillStyle = fill;
        ctx.strokeStyle = edge;
        ctx.lineWidth = 0.05;
        ctx.fillRect(-0.29, -0.62, 0.58, 0.17);
        ctx.strokeRect(-0.29, -0.62, 0.58, 0.17);
        ctx.save();
        ctx.translate(0, -0.86);
        disk(0, 0, 0.3, 0.2, "#e1a93b", "#74501a", 0.06);
        ctx.rotate(aim);
        polygon([[-0.11, 0], [-0.06, -0.36], [0.06, -0.36], [0.11, 0]], "#f4cd52", "#74501a", 0.05);
        disk(0, -0.38, 0.08, 0.06, "#ff6a2a");
        ctx.restore();
        disk(0, -0.86, 0.12, 0.08, "#ff9a3a");
      },
      Tesla(fill, edge, body) {
        disk(0.08, 0.42, 0.8, 0.3, "rgba(20,29,21,.3)");
        disk(0, 0.32, 0.62, 0.25, body("#908a7b"), "#4b4941", 0.07);
        ctx.lineCap = "round";
        const braces = [
          [[-0.38, 0.22], [0.38, 0.22]],
          [[-0.29, -0.24], [0.29, -0.24]],
          [[-0.36, 0.2], [0.28, -0.22]],
          [[0.36, 0.2], [-0.28, -0.22]],
          [[-0.28, -0.26], [0.23, -0.64]],
          [[0.28, -0.26], [-0.23, -0.64]],
        ];
        for (const b of braces) line(b, "#6f4a28", 0.09);
        for (const s of [-1, 1]) {
          line([[s * 0.42, 0.32], [s * 0.22, -0.72]], "#3a2817", 0.2);
          line([[s * 0.42, 0.32], [s * 0.22, -0.72]], "#a8743f", 0.11);
        }
        ctx.fillStyle = body("#5b7ea8");
        ctx.strokeStyle = "#22344a";
        ctx.lineWidth = 0.06;
        ctx.beginPath();
        ctx.roundRect(-0.36, -1.0, 0.72, 0.34, 0.12);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = fill;
        ctx.fillRect(-0.36, -0.81, 0.72, 0.1);
        disk(0, -1.0, 0.22, 0.12, "#bfe8ff", "#22344a", 0.05);
        line([[0.16, -1.04], [0.34, -1.1], [0.3, -1.2], [0.5, -1.26]], "#e2f7ff", 0.06);
        line([[-0.16, -1.04], [-0.32, -1.16], [-0.24, -1.22]], "#e2f7ff", 0.05);
      },
      Xbow(fill, edge, body, aim) {
        disk(0.1, 0.45, 0.95, 0.38, "rgba(20,29,21,.3)");
        const hex = [];
        for (let i = 0; i < 6; i++) {
          const a = (i * Math.PI) / 3;
          hex.push([Math.cos(a) * 0.66, 0.08 + Math.sin(a) * 0.52]);
        }
        polygon(hex, body("#606a76"), "#252b32", 0.09);
        disk(0, 0.06, 0.46, 0.35, fill, edge, 0.07);
        disk(0, 0.02, 0.2, 0.17, "#2e343c");
        ctx.save();
        ctx.rotate(aim);
        ctx.lineCap = "round";
        ctx.fillStyle = "#7a5230";
        ctx.strokeStyle = "#37240f";
        ctx.lineWidth = 0.06;
        ctx.beginPath();
        ctx.roundRect(-0.11, -0.95, 0.22, 1.42, 0.06);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = fill;
        ctx.fillRect(-0.12, -0.12, 0.24, 0.13);
        for (const [stroke, width] of [["#37240f", 0.22], ["#b37c44", 0.12]]) {
          ctx.beginPath();
          ctx.moveTo(-0.9, -0.36);
          ctx.quadraticCurveTo(0, -0.98, 0.9, -0.36);
          ctx.strokeStyle = stroke;
          ctx.lineWidth = width;
          ctx.stroke();
        }
        line([[-0.9, -0.36], [0, 0.16], [0.9, -0.36]], "#f1e8d0", 0.05);
        disk(-0.9, -0.36, 0.08, 0.08, "#cfd8e0", "#4b5560", 0.03);
        disk(0.9, -0.36, 0.08, 0.08, "#cfd8e0", "#4b5560", 0.03);
        ctx.fillStyle = "#5b4228";
        ctx.fillRect(-0.04, -1.1, 0.08, 1.0);
        polygon([[-0.1, -1.06], [0, -1.3], [0.1, -1.06]], "#d7dfe6", "#4b5560", 0.04);
        ctx.restore();
      },
    };
    function drawBuilding(name, px, py, r, fill, edge, hit, aim = 0) {
      ctx.save();
      ctx.translate(px, py);
      ctx.scale(r, r);
      const art = Object.hasOwn(BUILDING_ART, name) ? BUILDING_ART[name] : null;
      if (art) {
        art(fill, edge, (color) => (hit > 0 ? "#fff" : color), aim);
        ctx.restore();
        return;
      }
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
    // A classic-deck flying unit, or null. Lava Pups reuse the hound's card id; only their
    // smaller radius (0.45 vs 0.75 tiles) or, in traces without radii, their health tells them apart.
    function airOf(e) {
      if (!(e[9] & 1) || e[2] === KING || e[2] === PRINCESS || e[2] === BUILDING) return null;
      const name = cards[e[3]]?.[0];
      if (name === "LavaHound" && (e[8] > 0 ? e[8] < 0.6 : e[7] < 1000)) return "LavaPups";
      return AIR[name] ? name : null;
    }
    // Screen pixels between a flyer's ground point (its shadow) and its body, with a slow hover.
    function airLift(air, uid, now) {
      return (AIR[air].height * AIR_LIFT + Math.sin(now / 260 + uid * 1.7) * 0.04) * T;
    }
    function unitRadius(e, now = Infinity) {
      const pop = Math.min(1, Math.max(0, (now - (firstSeen.get(e[0]) ?? 0)) / 160));
      const scale = e[2] === BUILDING || e[2] === KING || e[2] === PRINCESS ? 1 : TROOP_SCALE;
      return Math.max(T * 0.48, e[8] * T) * scale * (0.6 + 0.4 * pop);
    }
    // Shadows sit on the true ground position, under every ground unit and building.
    function drawAirShadow(e, air, x, y, now) {
      const r = unitRadius(e, now),
        h = AIR[air].height,
        w = r * AIR[air].span * AIR[air].size * (1 - h * 0.05);
      ctx.globalAlpha = e[9] & 2 ? 0.55 : 1;
      disk(X(x), Y(y), w, w * 0.45, `rgba(12,24,16,${0.36 - h * 0.03})`);
      ctx.strokeStyle = e[1] === 0 ? C.blueDk : C.redDk;
      ctx.globalAlpha *= 0.55;
      ctx.lineWidth = Math.max(1, T * 0.06);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }
    function wings(points, fill, stroke, width = 0.08) {
      for (const side of [-1, 1])
        polygon(points.map(([wx, wy]) => [wx * side, wy]), fill, stroke, width);
    }
    // Original miniatures, drawn in radius units facing -y; f is the wing-beat offset.
    function drawFlyer(air, px, py, r, fill, edge, hit, facing, f) {
      const flash = (c) => (hit > 0 ? "#fff" : c);
      ctx.save();
      ctx.translate(px, py);
      if (air !== "Balloon") ctx.rotate(facing);
      ctx.scale(r * AIR[air].size, r * AIR[air].size);
      if (air === "Bats") {
        wings([[0.12, -0.08], [0.55, -0.42 - f], [1.08, -0.28 - f], [0.95, 0.06],
          [0.74, -0.02], [0.56, 0.2], [0.36, 0.06], [0.14, 0.2]], "#6b4f93", edge);
        disk(0, 0.04, 0.24, 0.3, flash("#4a3566"), "#2a1f3a", 0.06);
        polygon([[-0.17, -0.34], [-0.21, -0.6], [-0.04, -0.44]], "#4a3566");
        polygon([[0.17, -0.34], [0.21, -0.6], [0.04, -0.44]], "#4a3566");
        disk(0, -0.3, 0.2, 0.18, flash("#57407a"), "#2a1f3a", 0.06);
        disk(-0.08, -0.33, 0.045, 0.045, "#ffd54a");
        disk(0.08, -0.33, 0.045, 0.045, "#ffd54a");
      } else if (air === "Minions" || air === "MegaMinion") {
        const mega = air === "MegaMinion",
          skin = mega ? "#5c6378" : "#7c98cc";
        wings([[0.22, -0.12], [0.88, -0.62 - f], [1.08, -0.16 - f], [0.78, 0.12], [0.32, 0.22]],
          mega ? "#3a3f55" : "#46548a", edge, 0.1);
        disk(0, 0.12, 0.38, 0.4, flash(skin), "#2d3a5c", 0.08);
        if (mega) {
          disk(-0.4, -0.04, 0.17, 0.15, fill, edge, 0.06);
          disk(0.4, -0.04, 0.17, 0.15, fill, edge, 0.06);
          polygon([[-0.4, -0.3], [-0.5, -0.82], [-0.2, -0.6], [0.2, -0.6], [0.5, -0.82], [0.4, -0.3],
            [0, -0.12]], flash("#7d849a"), "#2f344f", 0.07);
          ctx.fillStyle = "#b5dff0";
          ctx.fillRect(-0.2, -0.42, 0.4, 0.07);
        } else {
          disk(0, 0.12, 0.38, 0.12, fill); // team sash
          polygon([[-0.2, -0.5], [-0.32, -0.74], [-0.08, -0.56]], "#e8e2cf");
          polygon([[0.2, -0.5], [0.32, -0.74], [0.08, -0.56]], "#e8e2cf");
          disk(0, -0.34, 0.3, 0.27, flash(skin), "#2d3a5c", 0.07);
          disk(-0.11, -0.38, 0.06, 0.07, "#fff");
          disk(0.11, -0.38, 0.06, 0.07, "#fff");
          disk(-0.11, -0.39, 0.03, 0.035, "#1d2433");
          disk(0.11, -0.39, 0.03, 0.035, "#1d2433");
        }
      } else if (air === "BabyDragon") {
        polygon([[-0.13, 0.4], [0.13, 0.4], [0.04, 0.98], [0, 1.1], [-0.04, 0.98]], "#55a03c", "#2f5d23", 0.06);
        wings([[0.25, -0.15], [0.95, -0.6 - f], [1.05, -0.05 - f], [0.82, 0.05], [0.66, 0.22], [0.3, 0.24]],
          "#4e9a3a", edge, 0.1);
        disk(0, 0.15, 0.42, 0.45, flash("#6cbf4a"), "#2f5d23", 0.08);
        disk(0, 0.2, 0.24, 0.3, "#ead78f");
        polygon([[-0.18, -0.55], [-0.28, -0.8], [-0.06, -0.62]], "#f2e7c4");
        polygon([[0.18, -0.55], [0.28, -0.8], [0.06, -0.62]], "#f2e7c4");
        disk(0, -0.44, 0.31, 0.27, flash("#74c851"), "#2f5d23", 0.07);
        disk(0, -0.66, 0.18, 0.13, flash("#8ad466"), "#2f5d23", 0.05);
        disk(-0.12, -0.46, 0.06, 0.07, "#20301a");
        disk(0.12, -0.46, 0.06, 0.07, "#20301a");
      } else if (air === "Balloon") {
        ctx.strokeStyle = "#e6d1a8";
        ctx.lineWidth = 0.06;
        for (const side of [-0.4, 0, 0.4]) {
          ctx.beginPath();
          ctx.moveTo(side, 0.2);
          ctx.lineTo(side * 0.5, 0.62);
          ctx.stroke();
        }
        ctx.fillStyle = "#7a5634";
        ctx.fillRect(-0.28, 0.58, 0.56, 0.32);
        ctx.strokeStyle = "#4a3320";
        ctx.lineWidth = 0.06;
        ctx.strokeRect(-0.28, 0.58, 0.56, 0.32);
        disk(0, 0.6, 0.17, 0.15, "#30343c", "#15181d", 0.05); // the bomb
        disk(0, -0.38, 0.8, 0.84, flash(fill), edge, 0.12);
        ctx.strokeStyle = edge;
        ctx.lineWidth = 0.06;
        for (const k of [-0.45, 0.45]) {
          ctx.beginPath();
          ctx.ellipse(0, -0.38, Math.abs(k), 0.84, 0, 0, 7);
          ctx.stroke();
        }
        disk(-0.32, -0.7, 0.13, 0.22, "rgba(255,255,255,.35)");
      } else if (air === "LavaHound" || air === "LavaPups") {
        const hound = air === "LavaHound";
        wings(hound
          ? [[0.35, -0.2], [0.95, -0.55 - f], [1.0, -0.1 - f], [0.62, 0.12]]
          : [[0.3, -0.15], [0.95, -0.42 - f], [0.9, 0.05 - f], [0.4, 0.15]],
        "#4a3c37", edge, 0.1);
        if (hound) {
          for (const [lx, ly] of [[-0.42, 0.55], [0.42, 0.55], [-0.38, -0.28], [0.38, -0.28]])
            disk(lx, ly, 0.13, 0.13, "#3d302b");
        }
        disk(0, 0.08, hound ? 0.62 : 0.46, hound ? 0.66 : 0.48, flash("#5b4a44"), "#2a1f1b", 0.08);
        ctx.strokeStyle = "#ff8a2a";
        ctx.lineWidth = 0.07;
        ctx.beginPath();
        ctx.moveTo(-0.3, -0.05); ctx.lineTo(-0.08, 0.15); ctx.lineTo(-0.2, 0.4);
        ctx.moveTo(0.28, 0.0); ctx.lineTo(0.1, 0.25); ctx.lineTo(0.25, 0.42);
        ctx.stroke();
        disk(0, 0.1, 0.16, 0.16, "#ffb347");
        disk(0, -0.5, hound ? 0.36 : 0.3, hound ? 0.3 : 0.26, flash("#66544c"), "#2a1f1b", 0.07);
        disk(-0.13, -0.54, 0.06, 0.05, "#ffc23d");
        disk(0.13, -0.54, 0.06, 0.05, "#ffc23d");
        disk(0, -0.5, 0.36, 0.08, fill); // team collar
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
        tower = kind === KING || kind === PRINCESS,
        air = airOf(e);
      const elapsed = now - (hitAt.get(uid) ?? -1e9);
      const hit = elapsed < 0 ? 0 : Math.max(0, 1 - elapsed / 140);
      const px = X(x),
        py = Y(y) - (air ? airLift(air, uid, now) : flying ? T * 0.5 : 0);
      let r = unitRadius(e, now);
      ctx.globalAlpha = deploying ? 0.55 : 1;
      if (flying && !air) {
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
        drawTower(e, px, py, r, 0, hp <= 0);
      } else if (kind === BUILDING) {
        const screenX = flip ? -fxv : fxv,
          screenY = flip ? fyv : -fyv,
          aimed = Math.hypot(screenX, screenY) > 0.1,
          aim = aimed ? Math.atan2(screenX, -screenY) : mine !== flip ? 0 : Math.PI;
        drawBuilding(name, px, py, r, fill, edge, 0, aim);
      } else {
        const screenX = flip ? -fxv : fxv,
          screenY = flip ? fyv : -fyv,
          facing = Math.hypot(screenX, screenY) > 0.1 ? Math.atan2(screenX, -screenY) : 0;
        if (air) {
          const rate = AIR[air].flap;
          drawFlyer(air, px, py, r, fill, edge, 0, facing, rate ? Math.sin(now / rate + uid) * 0.1 : 0);
          // rings, bars and the hit target follow the miniature; the balloon's envelope rises higher
          r *= AIR[air].size * (air === "Balloon" ? 1.2 : 1);
        } else {
          const unit = groundUnit(name, e[18], rad, flying);
          if (unit) drawGroundTroop(unit, px, py, r, fill, edge, 0, poseOf(screenX, screenY));
          else drawTroop(name, px, py, r, fill, edge, 0, facing);
        }
      }
      ctx.globalAlpha = 1;
      if (hit > 0) {
        // Hit feedback is a brief light wash over the miniature; its team colors stay visible.
        ctx.globalAlpha = (tower ? 0.38 : 0.5) * hit;
        ctx.fillStyle = "#fff";
        if (tower) {
          const [x0, y0, x1, y1] = kind === PRINCESS && e[14] ? e[14] : [];
          const left = x0 === undefined ? px - r : Math.min(X(x0), X(x1)),
            top = x0 === undefined ? py - r : Math.min(Y(y0), Y(y1)),
            w = x0 === undefined ? 2 * r : Math.abs(x1 - x0) * T,
            h = x0 === undefined ? 2 * r : Math.abs(y1 - y0) * T;
          ctx.beginPath();
          ctx.roundRect(left, top, w, h, Math.min(6, r * 0.3));
          ctx.fill();
        } else {
          ctx.beginPath();
          ctx.arc(px, py, r * 0.85, 0, 7);
          ctx.fill();
        }
        ctx.globalAlpha = 1;
      }
      if (e[13] > 0) stunRing(px, py, r, e[13] / (stunMax.get(uid) || e[13]), now);
      if (deploying) deployRing(px, py, r, team, now);
      drawn.push({ p: [px, py], rad: r, entity: e });
      const shield = e[15] || 0,
        c = chip.get(uid),
        age = c ? now - c.at : Infinity;
      if (tower || hp < maxHp || shield > 0)
        bars.push({ tower, team, px, py, r, uid, shield, hp, maxHp,
          lost: age >= 0 && age < CHIP_MS && maxHp ? c.from / maxHp : 0,
          lostAlpha: age >= 0 && age < CHIP_MS ? 1 - age / CHIP_MS : 0 });
    }
    // A jagged electric ring; its bright arc drains as the stun wears off.
    function stunRing(px, py, r, left, now) {
      const R = r + 4,
        n = Math.max(10, Math.round(R / 2.5)),
        phase = Math.floor(now / 70) % 2;
      ctx.beginPath();
      for (let i = 0; i <= n; i++) {
        const a = (i / n) * Math.PI * 2,
          k = R + ((i + phase) % 2 ? 2 : -1.5);
        if (i) ctx.lineTo(px + Math.cos(a) * k, py + Math.sin(a) * k);
        else ctx.moveTo(px + Math.cos(a) * k, py + Math.sin(a) * k);
      }
      ctx.lineWidth = 3.5;
      ctx.strokeStyle = INK;
      ctx.globalAlpha = 0.55;
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.lineWidth = 1.5;
      ctx.strokeStyle = "#bfe9ff";
      ctx.stroke();
      ctx.lineWidth = 3;
      ctx.lineCap = "round";
      ctx.strokeStyle = STUN;
      ctx.beginPath();
      ctx.arc(px, py, R + 2.5, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * Math.max(0, Math.min(1, left)));
      ctx.stroke();
      ctx.lineCap = "butt";
    }
    // A unit still dropping in: a turning dashed ring in its team color over a dark edge.
    function deployRing(px, py, r, team, now) {
      ctx.lineWidth = 3.5;
      ctx.strokeStyle = INK;
      ctx.globalAlpha = 0.5;
      ctx.beginPath();
      ctx.arc(px, py, r + 3, 0, 7);
      ctx.stroke();
      ctx.globalAlpha = 1;
      ctx.lineWidth = 2;
      ctx.strokeStyle = team === 0 ? "#9cc8ff" : "#ffb08e";
      ctx.setLineDash([4, 3]);
      ctx.lineDashOffset = -(now / 40) % 7;
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.lineDashOffset = 0;
    }
    // Bars draw after every miniature, so a crowd never hides a unit's health. Tower bars draw last.
    function drawBars(boxes) {
      for (const pass of [false, true])
        for (const b of bars) {
          if (b.tower !== pass) continue;
          const w = b.tower ? 2 * b.r : Math.max(T * 0.9, Math.min(2 * b.r, T * 2.4)),
            h = b.tower ? Math.max(5, Math.round(T * 0.28)) : Math.max(4, Math.round(T * 0.2)),
            y = Math.max(b.tower ? 14 : 6, b.py - b.r - (b.tower ? 9 : 7));
          hpBar(b.px, y, w, h, b.maxHp ? b.hp / b.maxHp : 0, b.team, b.lost, b.lostAlpha);
          if (b.shield > 0)
            shieldBar(b.px, y - 5, w, b.shield / (shieldMax.get(b.uid) || b.shield));
          boxes.push([b.px - w / 2 - 1, y - (b.shield > 0 ? 6 : 1), w + 2, h + (b.shield > 0 ? 7 : 2)]);
          if (b.tower) {
            const size = Math.max(11, Math.round(T * 0.48));
            ctx.font = "800 " + size + "px ui-monospace, Menlo, monospace";
            ctx.textAlign = "center";
            ctx.textBaseline = "alphabetic";
            const text = String(Math.round(b.hp)),
              ty = Math.max(size, y - 3);
            outlined(text, b.px, ty, "#fff", 3);
            const tw = textWidth(text);
            boxes.push([b.px - tw / 2 - 2, ty - size, tw + 4, size + 2, 1]);
          }
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
      bars = [];
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
      // Remember only observed tower sites. Ruins have no collision or tooltip
      // entry, and reset/seek rebuilds them from the same snapshot history.
      for (const [uid, e] of towerSites) {
        if (b.by.has(uid)) continue;
        drawTower(e, X(e[4]), Y(e[5]), (e[2] === KING ? 1.55 : 1.5) * T, 0, true);
      }
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
      for (const [e, x, y] of list) {
        const air = airOf(e);
        if (air) drawAirShadow(e, air, x, y, now);
      }
      for (const [e, x, y, hp] of list) drawEntity(e, x, y, hp, now);
      const boxes = [];
      drawBars(boxes);
      // Spell names keep their places; troop labels make room for them.
      ctx.font = "600 11px system-ui";
      for (const sp of b.sp) {
        const text = isFlight(sp) ? (cards[sp[1]] ? pretty(cards[sp[1]][0]) : "") : pretty(cards[sp[1]]?.[0] || ""),
          tx = isFlight(sp) ? X(sp[4]) : X(sp[2]),
          ty = isFlight(sp) ? Y(sp[5]) - 2.4 * T : Y(sp[3]) - T - 3,
          w = textWidth(text);
        if (text) boxes.push([tx - w / 2 - 2, ty - 11, w + 4, 14, 1]);
      }
      for (const p of b.me?.pend || []) {
        // your own plays that have not landed yet: a stopwatch that runs down where the card will land
        const q = a.me?.pend?.find((o) => o[0] === p[0]),
          left = q ? lerp(q[4], p[4], t) : p[4],
          frac = Math.max(0, Math.min(1, left / Math.max(1, delayTicks)));
        const px = X(p[2]),
          py = Y(p[3]),
          R = Math.max(7, T * 0.55),
          name = cards[p[1]] ? pretty(cards[p[1]][0]) : "";
        ctx.fillStyle = "rgba(255,255,255,.18)";
        ctx.strokeStyle = "#fff";
        ctx.lineWidth = 1.5;
        ctx.setLineDash([4, 3]);
        ctx.beginPath();
        ctx.arc(px, py, T * 0.95, 0, 7);
        ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = INK;
        ctx.fillRect(px - R * 0.22, py - R - R * 0.38, R * 0.44, R * 0.4);
        disk(px, py, R + 1.5, R + 1.5, INK);
        disk(px, py, R, R, "#f7f3e6");
        if (frac > 0) {
          ctx.fillStyle = C.blue;
          ctx.beginPath();
          ctx.moveTo(px, py);
          ctx.arc(px, py, R * 0.82, -Math.PI / 2, -Math.PI / 2 + 2 * Math.PI * frac);
          ctx.closePath();
          ctx.fill();
        }
        ctx.strokeStyle = INK;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(px, py);
        ctx.lineTo(px, py - R * 0.8);
        ctx.stroke();
        ctx.font = "700 " + Math.max(10, Math.round(T * 0.46)) + "px system-ui";
        ctx.textAlign = "center";
        ctx.textBaseline = "alphabetic";
        const ty = py - R - R * 0.45 - 3,
          w = textWidth(name);
        outlined(name, px, ty, TEXT[0]);
        boxes.push([px - w / 2 - 2, ty - 12, w + 4, 14, 1], [px - R - 2, py - R * 1.4, 2 * R + 4, R * 2.4 + 2, 1]);
      }
      // One name per group of the same unit standing together. Newer units are named first. A name
      // that would cover a bar or another name moves above or beside its unit; failing that it may
      // cross a bar, and it is left out only when every place would cover other text.
      const named = [],
        size = Math.max(9, Math.round(T * 0.46));
      ctx.font = "700 " + size + "px system-ui";
      ctx.textAlign = "center";
      ctx.textBaseline = "top";
      ctx.lineJoin = "round";
      const order = list
        .filter(([e]) => e[2] !== KING && e[2] !== PRINCESS && cards[e[3]])
        .sort((p, q) => (firstSeen.get(q[0][0]) ?? 0) - (firstSeen.get(p[0][0]) ?? 0) || p[0][0] - q[0][0]);
      const clear = (box, textOnly) =>
        box[0] >= 0 && box[0] + box[2] <= TX * T && box[1] >= 0 && box[1] + box[3] <= TY * T &&
        !boxes.some((o) => (!textOnly || o[4]) &&
          box[0] < o[0] + o[2] && o[0] < box[0] + box[2] && box[1] < o[1] + o[3] && o[1] < box[1] + box[3]);
      for (const [e, x, y] of order) {
        const air = airOf(e), group = air === "LavaPups" ? "pups" : e[3];
        if (named.some((n) => n[0] === e[1] && n[1] === group && Math.abs(n[2] - x) < 2.2 && Math.abs(n[3] - y) < 2.2))
          continue;
        named.push([e[1], group, x, y]);
        const r = unitRadius(e) * (air ? AIR[air].size : 1),
          cy = Y(y) - (air ? airLift(air, e[0], now) : e[9] & 1 ? T * 0.5 : 0),
          label = pretty(air === "LavaPups" ? air : cards[e[3]][0]),
          w = textWidth(label) + 4,
          top = bars.find((bar) => bar.uid === e[0]) ? cy - r - 7 - Math.max(4, Math.round(T * 0.2)) - 2 : cy - r - 2;
        const ux = X(x),
          spots = [[ux, cy + r + 2], [ux, top - size - 2], [ux + r + 3 + w / 2, cy - size / 2],
            [ux - r - 3 - w / 2, cy - size / 2], [ux, cy + r + 2 + size]];
        const spot = spots.find(([lx, ly]) => clear([lx - w / 2, ly, w, size + 1], false)) ||
          spots.find(([lx, ly]) => clear([lx - w / 2, ly, w, size + 1], true));
        if (!spot) continue;
        boxes.push([spot[0] - w / 2, spot[1], w, size + 1, 1]);
        outlined(label, spot[0], spot[1], TEXT[e[1]] || TEXT[1]);
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
  // Aim previews for the eight classic-deck spells, in tiles. The engine does not report spell
  // areas, so these are display-only approximations; legality always comes from the mask.
  const SPELL_AIM = Object.freeze({
    Fireball: { radius: 2.5 },
    Zap: { radius: 2.5 },
    Arrows: { radius: 4 },
    Rocket: { radius: 2 },
    Lightning: { radius: 3.5 },
    Poison: { radius: 3.5 },
    GoblinBarrel: { radius: 1.5 },
    Log: { lane: [3.9, 10.1] }, // width, forward length (rolls toward the opponent)
  });
  // The mask, shading and tap all refer to the SAME half-cell. A mask cell
  // describes its centre; never expand it back into a whole-tile rectangle.
  const placement = Object.freeze({
    // Describe what to preview for a card: kind is the engine's TROOP / BUILDING / SPELL.
    cue(name, kind, footprint) {
      const k = String(kind || "").toUpperCase();
      if (k === "SPELL") return { kind: "spell", name, ...(SPELL_AIM[name] || { radius: 1 }) };
      if (k === "BUILDING") return { kind: "building", name, size: footprint > 0 ? footprint : 2 };
      return { kind: "troop", name };
    },
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
    // Shades every blocked half-cell (one fillRect each), outlines where blocked meets
    // allowed, then previews the card at the hovered half-cell's centre.
    draw(ctx, grid, scale, hover, cue = null) {
      const cell = scale / grid.half,
        W = grid.width,
        H = grid.height,
        blocked = (cx, cy) =>
          cx >= 0 && cx < W && cy >= 0 && cy < H && grid.m[cy * W + cx] === "0";
      ctx.fillStyle = "rgba(214,52,30,.36)";
      for (let cy = 0; cy < H; cy++)
        for (let cx = 0; cx < W; cx++) {
          if (blocked(cx, cy))
            ctx.fillRect(cx * cell, (H - cy - 1) * cell, cell, cell);
        }
      if (!ctx.beginPath) return; // shading-only contexts (tests) stop here
      ctx.beginPath();
      for (let cy = 0; cy < H; cy++)
        for (let cx = 0; cx < W; cx++) {
          if (!blocked(cx, cy)) continue;
          const x0 = cx * cell,
            y0 = (H - cy - 1) * cell;
          const edge = (nx, ny, ax, ay, bx, by) => {
            if (nx < 0 || nx >= W || ny < 0 || ny >= H || blocked(nx, ny)) return;
            ctx.moveTo(ax, ay);
            ctx.lineTo(bx, by);
          };
          edge(cx, cy + 1, x0, y0, x0 + cell, y0); // top on screen
          edge(cx, cy - 1, x0, y0 + cell, x0 + cell, y0 + cell);
          edge(cx - 1, cy, x0, y0, x0, y0 + cell);
          edge(cx + 1, cy, x0 + cell, y0, x0 + cell, y0 + cell);
        }
      ctx.strokeStyle = "rgba(255,112,84,.95)";
      ctx.lineWidth = 2;
      ctx.setLineDash([]);
      ctx.stroke();
      if (!hover) return;
      const ok = placement.allowed(grid, hover),
        px = hover.x * scale,
        py = (H / grid.half - hover.y) * scale,
        line = ok ? "#fff" : "#ff5a4a",
        wash = ok ? "rgba(255,255,255,.22)" : "rgba(255,90,74,.28)";
      ctx.lineWidth = 2;
      ctx.strokeStyle = line;
      ctx.fillStyle = wash;
      let top = py - scale * 0.75;
      if (cue && cue.kind === "spell" && cue.lane) {
        const [w, len] = cue.lane;
        ctx.setLineDash([6, 4]);
        ctx.fillRect(px - (w / 2) * scale, py - len * scale, w * scale, len * scale);
        ctx.strokeRect(px - (w / 2) * scale, py - len * scale, w * scale, len * scale);
        ctx.setLineDash([]);
        top = py - scale * 0.9;
      } else if (cue && cue.kind === "spell") {
        ctx.beginPath();
        ctx.arc(px, py, cue.radius * scale, 0, 7);
        ctx.fill();
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.setLineDash([]);
        top = py - cue.radius * scale;
      } else if (cue && cue.kind === "building") {
        const s = cue.size * scale;
        ctx.fillRect(px - s / 2, py - s / 2, s, s);
        ctx.strokeRect(px - s / 2, py - s / 2, s, s);
        top = py - s / 2;
      } else {
        ctx.beginPath();
        ctx.arc(px, py, scale * 0.75, 0, 7);
        ctx.fill();
        ctx.stroke();
      }
      // The snapped half-cell itself: where the play is sent.
      ctx.fillStyle = line;
      ctx.fillRect(px - cell / 2 + 1, py - cell / 2 + 1, cell - 2, cell - 2);
      if (!cue || !cue.name) return;
      const label = cue.name.replace(/([a-z])([A-Z])/g, "$1 $2") + (ok ? "" : " — not here");
      ctx.font = "700 " + Math.max(11, Math.round(scale * 0.62)) + "px system-ui";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      const tw = ctx.measureText ? ctx.measureText(label).width : label.length * 7,
        lh = Math.max(16, scale * 0.95),
        ly = Math.max(lh / 2 + 2, top - lh / 2 - 6),
        lx = Math.min(Math.max(px, tw / 2 + 8), (W / grid.half) * scale - tw / 2 - 8);
      ctx.fillStyle = ok ? "rgba(12,20,34,.82)" : "rgba(120,20,12,.88)";
      if (ctx.roundRect) {
        ctx.beginPath();
        ctx.roundRect(lx - tw / 2 - 7, ly - lh / 2, tw + 14, lh, lh / 2);
        ctx.fill();
      } else ctx.fillRect(lx - tw / 2 - 7, ly - lh / 2, tw + 14, lh);
      ctx.fillStyle = "#fff";
      ctx.fillText(label, lx, ly);
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

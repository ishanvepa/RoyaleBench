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
    grassA: "#7fb85e",
    grassB: "#76ae56",
    water: "#3f9bd8",
    bridge: "#b48a5c",
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
        water = arena.water_half_rows;
      for (let hy = 0; hy < grid.length; hy++)
        for (let hx = 0; hx < grid[hy].length; hx++) {
          const v = grid[hy][hx],
            x0 = X(hx / half),
            y0 = Y(hy / half);
          const x1 = X((hx + 1) / half),
            y1 = Y((hy + 1) / half);
          const x = Math.min(x0, x1),
            y = Math.min(y0, y1),
            w = T / half + 0.5;
          const inRiver = hy >= water[0] && hy <= water[1];
          ctx.fillStyle =
            v & arena.bits.WATER
              ? C.water
              : inRiver
                ? C.bridge
                : (Math.floor(hx / half) + Math.floor(hy / half)) % 2
                  ? C.grassB
                  : C.grassA;
          ctx.fillRect(x, y, w, w);
          if (!inRiver) {
            ctx.fillStyle =
              hy < water[0] ? "rgba(59,142,240,.07)" : "rgba(240,112,60,.07)";
            ctx.fillRect(x, y, w, w);
          }
          if (v & arena.bits.NO_DEPLOY) {
            ctx.fillStyle = "rgba(40,60,30,.18)";
            ctx.fillRect(x, y, w, w);
          }
        }
    }
    function shieldBar(x, y, w, frac) {
      ctx.fillStyle = "rgba(0,0,0,.55)";
      ctx.fillRect(x - w / 2, y, w, 3);
      ctx.fillStyle = "#cfe3ff";
      ctx.fillRect(x - w / 2, y, w * Math.max(0, Math.min(1, frac)), 3);
    }
    function hpBar(x, y, w, frac) {
      ctx.fillStyle = "rgba(0,0,0,.55)";
      ctx.fillRect(x - w / 2, y, w, 4);
      ctx.fillStyle = frac > 0.6 ? "#3ecf4a" : frac > 0.3 ? C.gold : "#f0503c";
      ctx.fillRect(x - w / 2, y, w * Math.max(0, Math.min(1, frac)), 4);
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
      ctx.fillStyle = hit > 0 ? "#fff" : fill;
      ctx.strokeStyle = flying ? "#fff" : edge;
      ctx.lineWidth = tower ? 2.5 : 1.5;
      if (tower || kind === BUILDING) {
        if (tower) r = (kind === KING ? 1.55 : 1.5) * T;
        ctx.beginPath();
        if (kind === PRINCESS && e[14]) {
          const [x0, y0, x1, y1] = e[14];
          const left = Math.min(X(x0), X(x1)),
            top = Math.min(Y(y0), Y(y1));
          const width = Math.abs(x1 - x0) * T,
            height = Math.abs(y1 - y0) * T;
          r = Math.max(width, height) / 2;
          ctx.roundRect(left, top, width, height, Math.min(6, r * 0.3));
        } else {
          ctx.roundRect(px - r, py - r, 2 * r, 2 * r, Math.min(6, r * 0.3));
        }
        ctx.fill();
        ctx.stroke();
      } else {
        ctx.beginPath();
        ctx.arc(px, py, r, 0, 7);
        ctx.fill();
        ctx.stroke();
        const n = Math.hypot(fxv, fyv);
        if (n > 0 && r > 5) {
          // a small nose in the direction the unit faces
          ctx.fillStyle = "#fff";
          ctx.beginPath();
          ctx.arc(
            px + ((flip ? -fxv : fxv) / n) * r * 0.72,
            py - ((flip ? -fyv : fyv) / n) * r * 0.72,
            Math.max(1.5, r * 0.2),
            0,
            7,
          );
          ctx.fill();
        }
      }
      ctx.globalAlpha = 1;
      if (e[13] > 0) {
        ctx.strokeStyle = "#ffd400";
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.arc(px, py, r + 3.5, 0, 7);
        ctx.stroke();
      }
      const name = tower
        ? kind === KING
          ? "👑"
          : "🏰"
        : cards[cid]
          ? cards[cid][0]
          : "?";
      const pic = tower ? name : iconOf(name);
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      if (pic) {
        ctx.fillStyle = "#fff";
        ctx.font =
          Math.round(Math.max(10, r * (tower ? 0.95 : 1.25))) + "px system-ui";
        ctx.fillText(pic, px, py + 1);
      } else if (r >= 6) {
        ctx.fillStyle = hit > 0 ? "#222" : "#fff";
        ctx.font =
          "600 " +
          Math.round(Math.min(12, Math.max(8, r * 0.95))) +
          "px system-ui";
        ctx.fillText(name.slice(0, 2), px, py + 0.5);
      }
      const shield = e[15] || 0;
      if (tower || hp < maxHp || shield > 0)
        hpBar(px, py - r - 8, Math.max(16, 2 * r), maxHp ? hp / maxHp : 0);
      if (shield > 0)
        shieldBar(px, py - r - 12, Math.max(16, 2 * r), shield / (shieldMax.get(uid) || shield));
      if (tower) {
        ctx.fillStyle = "#16202e";
        ctx.font = "700 11px ui-monospace, Menlo, monospace";
        ctx.textAlign = "center";
        ctx.textBaseline = "alphabetic";
        ctx.fillText(Math.round(hp), px, py - r - 11);
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

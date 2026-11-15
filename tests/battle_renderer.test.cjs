const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const { join } = require('node:path');

const window = {};
runInNewContext(readFileSync(join(__dirname, '../cr_arena/battle_renderer.js'), 'utf8'), {window});
const arena = {tiles_x: 18, tiles_y: 32, half: 1, water_half_rows: [15, 16],
  bits: {WATER: 1, NO_DEPLOY: 2}, grid: Array.from({length: 32}, () => Array(18).fill(0))};
const cards = {0: ['Knight'], 1: ['Fireball'], 2: ['Log'], 3: ['Poison']};

function fixture() {
  const operations = [];
  const ctx = new Proxy({}, {
    get: (_, key) => (...args) => {
      for (const arg of args.flat()) if (typeof arg === 'number') assert.ok(Number.isFinite(arg), `${key}: ${arg}`);
      operations.push([key, ...args]);
    },
    set: (_, key, value) => { operations.push([key, value]); return true; },
  });
  const renderer = window.BattleRenderer.create({width: 360, getContext: () => ctx}, arena);
  const a = {en: [[1, 0, 0, 0, 2, 6, 100, 100, .5, 0, -1, 1, 0]], sp: [], pr: []};
  const b = {en: [[1, 0, 0, 0, 4, 8, 80, 100, .5, 0, -1, 1, 0]],
    sp: [[0, 1, 4, 8, 6, 10, 'FLIGHT'], [1, 2, 7, 9, 7, 7, 'ROLLING'], [1, 3, 9, 9, 9, 9, 'AREA']],
    pr: [[0, 4, 9]]};
  return {renderer, a, b, operations};
}

test('live-style snapshots draw every spell motion without replay-only state', () => {
  const {renderer, a, b} = fixture();
  renderer.observe(a, 0); renderer.observe(b, 100);
  const hits = renderer.draw(a, b, .5, 50, {scale: 20, cards});
  assert.equal(hits.length, 4);
  assert.equal(hits[0].p[0], 60);
  assert.equal(hits[0].p[1], 500);
  assert.equal(hits.filter(hit => hit.spell).length, 3);
});

test('board flipping transforms graphics and tooltip targets together', () => {
  const {renderer, a, b} = fixture();
  renderer.observe(a, 0); renderer.observe(b, 100);
  const hit = renderer.draw(a, b, .5, 50, {scale: 20, cards, flip: true})[0];
  assert.equal(hit.p[0], 300);
  assert.equal(hit.p[1], 140);
});

test('rebuilding animation history after a seek reproduces the same drawing', () => {
  const {renderer, a, b, operations} = fixture();
  const draw = () => {
    renderer.observe(a, 0); renderer.observe(b, 100);
    operations.length = 0;
    renderer.draw(a, b, .5, 150, {scale: 20, cards});
    return JSON.stringify(operations);
  };
  const original = draw();
  renderer.reset();
  assert.equal(draw(), original);
});

function placementMask() {
  const cells = Array(36 * 64).fill('1');
  for (let cy = 3; cy < 9; cy++) for (let cx = 15; cx < 21; cx++) cells[cy * 36 + cx] = '0';
  return {half: 2, width: 36, height: 64, m: cells.join('')};
}

test('placement shading uses the king block at x7.5–10.5, y1.5–4.5', () => {
  const rects = [];
  window.BattleRenderer.placement.draw({fillRect: (...args) => rects.push(args)}, placementMask(), 40, null);
  assert.equal(rects.length, 36);
  assert.equal(Math.min(...rects.map(r => r[0])), 7.5 * 40);
  assert.equal(Math.max(...rects.map(r => r[0] + r[2])), 10.5 * 40);
  assert.equal(Math.min(...rects.map(r => r[1])), (32 - 4.5) * 40);
  assert.equal(Math.max(...rects.map(r => r[1] + r[3])), (32 - 1.5) * 40);
});

test('clicks on either side of every king-block edge use the shaded cell', () => {
  const p = window.BattleRenderer.placement, grid = placementMask();
  for (const [x, y, legal] of [[7.49, 3, true], [7.5, 3, false], [10.49, 3, false], [10.5, 3, true],
    [9, 1.49, true], [9, 1.5, false], [9, 4.49, false], [9, 4.5, true]]) {
    const hit = p.at(x, y, grid);
    assert.equal(p.allowed(grid, hit), legal, `${x},${y}`);
    assert.equal(Math.floor(hit.x * 2), hit.cx);
    assert.equal(Math.floor(hit.y * 2), hit.cy);
  }
  assert.equal(p.at(-.01, 3, grid), null);
  assert.equal(p.at(18, 3, grid), null);
});

test('princess graphics and hit targets follow the supplied footprint in both orientations', () => {
  for (const flip of [false, true]) {
    const {renderer, a, operations} = fixture();
    // Use a non-default width to prove the renderer reads the actual footprint.
    a.en = [[2, 0, 3, -1, 3.5, 6.5, 3052, 3052, 1, 0, 1, 0, 0, 0, [1.5, 5, 5.5, 8]]];
    renderer.observe(a, 0);
    const hit = renderer.draw(a, a, 0, 100, {scale: 20, cards, flip})[0];
    const rect = operations.find(op => op[0] === 'roundRect');
    assert.equal(rect[1], (flip ? 18 - 5.5 : 1.5) * 20);
    assert.equal(rect[2], (flip ? 5 : 32 - 8) * 20);
    assert.equal(rect[3], 80);
    assert.equal(rect[4], 60);
    assert.equal(hit.rad, 40);
  }
});

test('old replay rows without footprints use the three-tile princess size', () => {
  const {renderer, a, operations} = fixture();
  a.en = [[2, 0, 3, -1, 3.5, 6.5, 3052, 3052, 1, 0, 1, 0, 0]];
  renderer.observe(a, 0);
  renderer.draw(a, a, 0, 100, {scale: 20, cards});
  const rect = operations.find(op => op[0] === 'roundRect');
  assert.equal(rect[3], 60);
  assert.equal(rect[4], 60);
});

test('a shield is drawn above the health bar and its loss flashes the unit', () => {
  const {renderer, operations} = fixture();
  const a = {en: [[1, 0, 0, 0, 4, 8, 100, 100, .5, 0, -1, 1, 0, 0, null, 50, 0, -1]], sp: [], pr: []};
  const b = {en: [[1, 0, 0, 0, 4, 8, 100, 100, .5, 0, -1, 1, 0, 0, null, 20, 0, -1]], sp: [], pr: []};
  renderer.observe(a, 0); renderer.observe(b, 100);
  operations.length = 0;
  renderer.draw(a, b, 1, 110, {scale: 20, cards});
  assert.ok(operations.some(op => op[0] === 'fillStyle' && op[1] === '#cfe3ff'), 'shield bar drawn');
  assert.ok(operations.some(op => op[0] === 'fillStyle' && op[1] === '#fff'), 'hit flash after shield damage');
});

function recordingCtx() {
  const ops = [];
  let fill = null;
  const ctx = new Proxy({}, {
    get: (_, key) => key === 'measureText' ? (t) => ({width: t.length * 6})
      : (...args) => { ops.push([key, fill, ...args]); },
    set: (_, key, value) => { if (key === 'fillStyle') fill = value; ops.push([key, value]); return true; },
  });
  return {ctx, ops};
}
const SHADE = 'rgba(214,52,30,.36)';

test('classic-deck cues: buildings use engine footprints, the eight spells have aim areas', () => {
  const p = window.BattleRenderer.placement;
  for (const [name, size] of [['Cannon', 3], ['InfernoTower', 3], ['Tesla', 2], ['Tombstone', 3], ['Xbow', 3]])
    assert.deepEqual({...p.cue(name, 'BUILDING', size)}, {kind: 'building', name, size});
  for (const name of ['Fireball', 'Zap', 'Arrows', 'Rocket', 'Lightning', 'Poison', 'GoblinBarrel'])
    assert.ok(p.cue(name, 'SPELL', 0).radius > 0, name);
  assert.equal(p.cue('Log', 'SPELL', 0).lane.length, 2);
  assert.equal(p.cue('Knight', 'TROOP', 0).kind, 'troop');
});

test('a full canvas keeps one shaded rect per blocked half-cell and outlines the block', () => {
  const {ctx, ops} = recordingCtx();
  window.BattleRenderer.placement.draw(ctx, placementMask(), 40, null);
  assert.equal(ops.filter(op => op[0] === 'fillRect' && op[1] === SHADE).length, 36);
  // The 6x6 half-cell block has 24 boundary edges.
  assert.equal(ops.filter(op => op[0] === 'moveTo').length, 24);
});

test('hover cues are centred on the snapped half-cell centre with the card size', () => {
  const p = window.BattleRenderer.placement, grid = placementMask(), scale = 40;
  const hover = p.at(4.2, 10.9, grid); // centre (4.25, 10.75)
  const px = 4.25 * scale, py = (32 - 10.75) * scale;
  {
    const {ctx, ops} = recordingCtx();
    p.draw(ctx, grid, scale, hover, p.cue('Tesla', 'BUILDING', 2));
    const rect = ops.find(op => op[0] === 'strokeRect');
    assert.deepEqual(rect.slice(2), [px - scale, py - scale, 2 * scale, 2 * scale]);
    assert.ok(ops.some(op => op[0] === 'fillText' && op[2] === 'Tesla'));
  }
  {
    const {ctx, ops} = recordingCtx();
    p.draw(ctx, grid, scale, hover, p.cue('Fireball', 'SPELL', 0));
    const arc = ops.find(op => op[0] === 'arc');
    assert.deepEqual(arc.slice(2, 5), [px, py, 2.5 * scale]);
  }
  {
    const {ctx, ops} = recordingCtx();
    p.draw(ctx, grid, scale, p.at(9, 3, grid), p.cue('Knight', 'TROOP', 0));
    assert.ok(ops.some(op => op[0] === 'fillText' && op[2] === 'Knight — not here'));
  }
});


const troop = (uid, card, x, y, hp, extra = {}) => {
  const e = [uid, extra.team ?? 0, 0, card, x, y, hp, 100, .5, extra.flags ?? 0, -1, 0, 1, extra.stun ?? 0, null, 0, 0, -1];
  return e;
};

test('drawing leaves snapshots unchanged and health bars draw above every miniature', () => {
  const {renderer, operations} = fixture();
  const a = {en: [troop(1, 0, 4, 8, 100), troop(2, 0, 4, 7.6, 100)], sp: [], pr: []};
  const b = {en: [troop(1, 0, 4, 8, 60), troop(2, 0, 4, 7.6, 100)], sp: [], pr: []};
  const frozen = JSON.stringify([a.en, b.en]);
  renderer.observe(a, 0); renderer.observe(b, 100);
  operations.length = 0;
  renderer.draw(a, b, 1, 120, {scale: 20, cards});
  assert.equal(JSON.stringify([a.en, b.en]), frozen);
  const lastArt = operations.findLastIndex(op => op[0] === 'ellipse');
  const firstBar = operations.findIndex(op => op[0] === 'fillStyle' && op[1] === '#17345e');
  assert.ok(firstBar > lastArt, 'bars follow all unit art');
  assert.ok(operations.some(op => op[0] === 'fillStyle' && op[1] === '#fff4c2'), 'recent damage shows on the bar');
  operations.length = 0;
  renderer.draw(a, b, 1, 1000, {scale: 20, cards});
  assert.ok(!operations.some(op => op[0] === 'fillStyle' && op[1] === '#fff4c2'), 'the damage segment expires');
});

test('a stun ring drains with the stun time left in both orientations', () => {
  for (const flip of [false, true]) {
    const {renderer, operations} = fixture();
    const a = {en: [troop(1, 0, 4, 8, 100, {stun: 20})], sp: [], pr: []};
    const b = {en: [troop(1, 0, 4, 8, 100, {stun: 10})], sp: [], pr: []};
    renderer.observe(a, 0); renderer.observe(b, 100);
    operations.length = 0;
    renderer.draw(a, b, 1, 120, {scale: 20, cards, flip});
    const arc = operations.find(op => op[0] === 'arc' && Math.abs(op[4] + Math.PI / 2) < 1e-9);
    assert.ok(arc, 'stun arc drawn');
    assert.ok(Math.abs(arc[5] - Math.PI / 2) < 1e-9, 'half the stun remains');
  }
});

test('crowded troop labels never draw on top of each other', () => {
  for (const flip of [false, true]) {
    const {renderer, operations} = fixture();
    const crowd = {0: ['Knight'], 4: ['MiniPekka'], 5: ['BattleRam'], 6: ['ElectroWizard'], 7: ['Giant']};
    const s = {en: [0, 4, 5, 6, 7].map((c, i) => troop(i + 1, c, 9 + (i % 2) * .4, 16 + i * .3, 50)), sp: [], pr: []};
    renderer.observe(s, 0);
    operations.length = 0;
    renderer.draw(s, s, 0, 500, {scale: 20, cards: crowd, flip});
    const labels = operations.filter(op => op[0] === 'fillText' && /[A-Z]/.test(op[1]));
    for (let i = 0; i < labels.length; i++)
      for (let j = i + 1; j < labels.length; j++) {
        const [, p, px, py] = labels[i], [, q, qx, qy] = labels[j];
        const overlap = Math.abs(px - qx) * 2 < (p.length + q.length) * 9 * .6 + 8 && Math.abs(py - qy) < 10;
        assert.ok(!overlap, `${p} and ${q} overlap`);
      }
    assert.ok(labels.length >= 4, `most of the crowd is named (${labels.length})`);
  }
});


// Classic-deck flyers: [uid, team, kind, card, x, y, hp, maxHp, radius, flags, slot, fx, fy]
const airCards = {0: ['Knight'], 5: ['Minions'], 6: ['Balloon'], 15: ['BabyDragon'], 29: ['LavaHound'],
  37: ['InfernoDragon'], 39: ['MegaMinion'], 49: ['Bats']};
const airHeight = {5: 1.5, 6: 3, 15: 3.5, 39: 1.5, 49: 2};
function airDraw(en, options = {}, prev = null) {
  const {renderer, operations} = fixture();
  const a = {en: prev || en, sp: [], pr: []}, b = {en, sp: [], pr: []};
  renderer.observe(a, 0); renderer.observe(b, 100);
  operations.length = 0;
  // now = 0 keeps the hover term at sin(uid * 1.7)
  const hits = renderer.draw(a, b, options.t ?? 1, options.now ?? 0, {scale: 20, cards: airCards, ...options});
  return {hits, operations};
}
const hover = uid => Math.sin(uid * 1.7) * 0.04 * 20;

test('each classic flyer is lifted by its own flying height above an unchanged ground point', () => {
  for (const flip of [false, true])
    for (const [card, height] of Object.entries(airHeight)) {
      const {hits} = airDraw([[3, 1, 0, +card, 4, 8, 100, 100, .5, 1, -1, 0, 1]], {flip});
      assert.equal(hits[0].p[0], (flip ? 18 - 4 : 4) * 20);
      const groundY = (flip ? 8 : 32 - 8) * 20;
      assert.ok(Math.abs(hits[0].p[1] - (groundY - (height * 0.3 * 20 + hover(3)))) < 1e-9, `card ${card}`);
    }
});

test('flyer shadows sit on the interpolated ground point before any ground unit is drawn', () => {
  const prev = [[1, 0, 0, 0, 4, 6, 100, 100, .5, 0, -1, 0, 1], [2, 0, 0, 49, 2, 6, 100, 100, .5, 1, -1, 0, 1]];
  const now = [[1, 0, 0, 0, 4, 6, 100, 100, .5, 0, -1, 0, 1], [2, 0, 0, 49, 4, 10, 100, 100, .5, 1, -1, 0, 1]];
  const {hits, operations} = airDraw(now, {t: .5}, prev);
  const shadow = operations.findIndex(op => op[0] === 'fillStyle' && /^rgba\(12,24,16/.test(op[1]));
  const ellipse = operations.slice(0, shadow).reverse().find(op => op[0] === 'ellipse');
  assert.deepEqual(ellipse.slice(1, 3), [3 * 20, (32 - 8) * 20]);
  const knightBase = operations.findIndex(op => op[0] === 'fillStyle' && op[1] === '#d3c49d');
  assert.ok(shadow > 0 && shadow < knightBase, 'shadow precedes the ground knight');
  assert.equal(hits[1].entity[0], 2, 'flyers are drawn, and hit-tested, after ground units');
  assert.equal(hits[1].p[0], 3 * 20);
});

test('Lava Pups spawned by the hound are told apart by radius and labelled as pups', () => {
  const en = [[7, 1, 0, 29, 9, 20, 3581, 3581, .75, 1, -1, 0, -1], [8, 1, 0, 29, 9, 16, 215, 215, .45, 1, -1, 0, -1]];
  const {hits, operations} = airDraw(en);
  const labels = operations.filter(op => op[0] === 'fillText').map(op => op[1]);
  assert.deepEqual(labels.sort(), ['Lava Hound', 'Lava Pups']);
  assert.ok(Math.abs(hits[0].p[1] - ((32 - 20) * 20 - (4 * 0.3 * 20 + hover(7)))) < 1e-9);
  assert.ok(Math.abs(hits[1].p[1] - ((32 - 16) * 20 - (3.5 * 0.3 * 20 + hover(8)))) < 1e-9);
  // traces without radii fall back to health
  const old = airDraw([[8, 1, 0, 29, 9, 16, 215, 215, 0, 1, -1, 0, -1]]);
  assert.ok(old.operations.some(op => op[0] === 'fillText' && op[1] === 'Lava Pups'));
});

test('flyers outside the classic decks keep the generic half-tile lift', () => {
  const {hits} = airDraw([[4, 0, 0, 37, 4, 8, 100, 100, .5, 1, -1, 0, 1]]);
  assert.equal(hits[0].p[1], (32 - 8) * 20 - 10);
});

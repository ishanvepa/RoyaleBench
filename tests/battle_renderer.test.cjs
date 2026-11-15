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

const classic = {1: ['Arrows'], 2: ['Fireball'], 3: ['GoblinBarrel'], 4: ['Lightning'], 5: ['Log'], 6: ['Poison'],
  7: ['Rocket'], 8: ['Zap']};
const generic = Object.fromEntries(Object.keys(classic).map(id => [id, ['Spell' + id]]));

function classicFrames() {
  const a = {en: [], pr: [], sp: [[0, 1, 5, 8, 3.5, 25.5, 'FLIGHT'], [0, 1, 7, 4, 3.5, 25.5, 'FLIGHT'],
    [0, 2, 8, 6, 14.5, 25.5, 'FLIGHT'], [0, 3, 8, 6, 3.5, 28, 'FLIGHT'], [0, 7, 9, 5, 14.5, 28, 'FLIGHT'],
    [1, 5, 14.5, 20, 14.5, 17.5, 'AIRBORNE'], [1, 5, 3.5, 20, 3.5, 10, 'ROLLING'], [1, 6, 9, 9, 9, 9, 'PULSING'],
    [1, 4, 14.5, 9, 14.5, 9, 'STRIKES'], [1, 8, 9, 13, 9, 13, 'AREA']]};
  const b = structuredClone(a);
  for (const sp of b.sp) if (sp[6] === 'FLIGHT' || sp[6] === 'AIRBORNE') {
    sp[2] += (sp[4] - sp[2]) * 0.2; sp[3] += (sp[5] - sp[3]) * 0.2;
  }
  b.sp[6][3] = 18;
  return {a, b};
}

test('classic spell art keeps every spell position and hit target of the generic drawing', () => {
  for (const flip of [false, true]) {
    const hits = [classic, generic].map(names => {
      const {renderer} = fixture(), {a, b} = classicFrames();
      renderer.observe(a, 0); renderer.observe(b, 50);
      return renderer.draw(a, b, .4, 30, {scale: 20, cards: names, flip}).map(h => [h.p, h.rad]);
    });
    assert.deepEqual(hits[0], hits[1]);
    assert.equal(hits[0].length, 9);  // one per spell key, as before
  }
});

test('every classic spell draws travel, ground and impact art with finite geometry', () => {
  for (const flip of [false, true]) {
    const {renderer, operations} = fixture(), {a, b} = classicFrames();
    renderer.observe(a, 0); renderer.observe(b, 50);
    renderer.draw(a, b, .5, 60, {scale: 20, cards: classic, flip});  // travel and ground art
    const c = {en: [], pr: [], sp: []};
    renderer.observe(c, 100);  // all of them land or end
    for (const now of [120, 300]) renderer.draw(b, c, .5, now, {scale: 20, cards: classic, flip});
    assert.ok(operations.some(op => op[0] === 'roundRect'), 'barrel, rocket or log bodies drawn');
    assert.ok(operations.some(op => op[0] === 'fillStyle' && op[1] === '#fff4b8'), 'fireball flash drawn');
  }
});

test('all three Arrows volleys are drawn and an early volley landing gets its own impact', () => {
  const {renderer, operations} = fixture();
  const row = (x, y) => [0, 1, x, y, 3.5, 25.5, 'FLIGHT'];
  const a = {en: [], pr: [], sp: [row(5, 18), row(6, 14), row(7, 10)]};
  const b = {en: [], pr: [], sp: [row(5.5, 16), row(6.5, 12)]};
  renderer.observe(a, 0); renderer.observe(b, 50);
  operations.length = 0;
  renderer.draw(a, b, .5, 60, {scale: 20, cards: classic});
  const shafts = operations.filter(op => op[0] === 'strokeStyle' && op[1] === '#6b4a2b').length;
  assert.equal(shafts, 2 * 7 + 11, 'two volleys of seven arrows in flight, eleven stuck at the landing');
});

test('other spells and effect objects keep the generic drawing', () => {
  const {renderer, operations} = fixture(), {a, b} = classicFrames();
  renderer.observe(a, 0); renderer.observe(b, 50);
  operations.length = 0;
  renderer.draw(a, b, .4, 30, {scale: 20, cards: generic});
  assert.ok(!operations.some(op => op[0] === 'fillStyle' && ['#9a6434', '#7a4a22', '#e2b43c'].includes(op[1])));
});

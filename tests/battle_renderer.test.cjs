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

test('king artwork keeps the existing size and tooltip anchor for both teams and flips', () => {
  for (const flip of [false, true]) for (const team of [0, 1]) {
    const {renderer, a, operations} = fixture();
    const y = team ? 29 : 3;
    a.en = [[10, team, 2, -1, 9, y, 4824, 4824, 1, 0, 0, 0, 0]];
    renderer.observe(a, 0);
    const hit = renderer.draw(a, a, 0, 100, {scale: 20, cards, flip})[0];
    assert.deepEqual(Array.from(hit.p), [180, (flip ? y : 32 - y) * 20]);
    assert.equal(hit.rad, 31);
    const rect = operations.find(op => op[0] === 'roundRect');
    assert.deepEqual(rect.slice(1, 5), [149, hit.p[1] - 31, 62, 62]);
  }
});

test('destroyed towers leave footprint-aligned ruins without tooltip targets, and seeks clear them', () => {
  for (const flip of [false, true]) {
    const {renderer, a, operations} = fixture();
    a.en = [[2, 0, 3, -1, 3.5, 6.5, 10, 3052, 1, 0, 1, 0, 0, 0, [1.5, 5, 5.5, 8]]];
    const gone = {en: [], sp: [], pr: []};
    renderer.observe(a, 0); renderer.observe(gone, 100);
    const draw = () => {
      operations.length = 0;
      const hits = renderer.draw(gone, gone, 0, 1000, {scale: 20, cards, flip});
      assert.equal(hits.length, 0);
      return operations.filter(op => op[0] === 'roundRect');
    };
    const ruins = draw();
    assert.equal(ruins.length, 1);
    assert.deepEqual(ruins[0].slice(1, 5), [(flip ? 18 - 5.5 : 1.5) * 20,
      (flip ? 5 : 32 - 8) * 20, 80, 60]);
    renderer.reset();
    renderer.observe(gone, 100);
    assert.equal(draw().length, 0, 'reset must not remember a future destroyed tower');
    renderer.reset();
    renderer.observe(a, 0); renderer.observe(gone, 100);
    assert.deepEqual(draw(), ruins, 'rebuilding history must reproduce the same ruins');
  }
});

test('low health preserves tower masonry, while an immediate hit still flashes', () => {
  const {renderer, a, operations} = fixture();
  a.en = [[2, 1, 3, -1, 3.5, 25.5, 3052, 3052, 1, 0, 1, 0, 0]];
  const damaged = {en: [a.en[0].map((value, i) => i === 6 ? 10 : value)], sp: [], pr: []};
  const art = (s, now) => {
    operations.length = 0;
    renderer.draw(s, s, 0, now, {scale: 20, cards});
    // Exclude the unchanged HUD path (health bar and number) after tower restore.
    return operations.slice(0, operations.findIndex(op => op[0] === 'restore') + 1);
  };
  renderer.observe(a, 0);
  const healthy = art(a, 0);
  renderer.observe(damaged, 100);
  const hit = art(damaged, 110);
  assert.ok(hit.some(op => op[0] === 'fillStyle' && op[1] === '#fff'));
  assert.equal(JSON.stringify(art(damaged, 1000)), JSON.stringify(healthy));
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

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

function troopScene(card, unit, facing, options = {}) {
  const {renderer, operations} = fixture();
  const names = {0: [card], 1: ['Tombstone'], 2: ['Minions']};
  const row = [7, options.team || 0, 0, 0, 6, 9, 100, 100, options.radius ?? .5, options.flags || 0, -1,
    facing[0], facing[1], 0, null, 0, 0, -1];
  if (unit !== undefined) row.push(unit);
  const s = {en: [row], sp: [], pr: []};
  renderer.observe(s, 0);
  const hits = renderer.draw(s, s, 0, 500, {scale: 20, cards: names, flip: !!options.flip});
  return {hits, operations, ops: JSON.stringify(operations)};
}

test('classic ground troops stand upright and mirror instead of rotating', () => {
  for (const card of ['Archer', 'BattleRam', 'ElectroWizard', 'Giant', 'Golem', 'HogRider', 'IceGolemite',
    'IceSpirits', 'Knight', 'MiniPekka', 'Musketeer', 'Pekka', 'Princess', 'Wizard']) {
    const right = troopScene(card, card, [1, 0]), left = troopScene(card, card, [-1, 0]);
    assert.ok(!right.operations.some(op => op[0] === 'rotate'), card);
    assert.ok(right.operations.some(op => op[0] === 'scale' && op[1] === 10 && op[2] === 10), card);
    assert.ok(left.operations.some(op => op[0] === 'scale' && op[1] === -10 && op[2] === 10), card);
  }
});

test('flipping the board mirrors a ground troop with its screen motion', () => {
  const plain = troopScene('Knight', 'Knight', [1, 0]), flipped = troopScene('Knight', 'Knight', [1, 0], {flip: true});
  assert.ok(plain.operations.some(op => op[0] === 'scale' && op[1] === 10));
  assert.ok(flipped.operations.some(op => op[0] === 'scale' && op[1] === -10));
  // walking up the screen shows the back; the same motion seen from the other side shows the face
  assert.notEqual(troopScene('Knight', 'Knight', [0, 1]).ops, troopScene('Knight', 'Knight', [0, -1]).ops);
});

test('ground troop poses keep the entity position and hit target', () => {
  for (const facing of [[1, 0], [-1, 0], [0, 1], [0, -1], [0, 0]]) {
    const hit = troopScene('Pekka', 'Pekka', facing, {radius: .75}).hits[0];
    assert.deepEqual([...hit.p], [120, 460]);
    assert.equal(hit.rad, 15);
  }
});

test('spawned units are drawn by unit type, with a radius fallback for old traces', () => {
  const golem = troopScene('Golem', 'Golem', [1, 0], {radius: .75}).ops;
  const golemite = troopScene('Golem', 'Golemite', [1, 0], {radius: .5}).ops;
  assert.notEqual(golem.replace(/15/g, '10'), golemite);
  assert.equal(troopScene('Golem', undefined, [1, 0], {radius: .5}).ops, golemite);
  assert.equal(troopScene('BattleRam', undefined, [1, 0], {radius: .5}).ops,
    troopScene('BattleRam', 'Barbarian', [1, 0], {radius: .5}).ops);
  assert.notEqual(troopScene('GoblinGang', 'Goblin_Stab', [1, 0]).ops, troopScene('GoblinGang', 'SpearGoblin', [1, 0]).ops);
  assert.equal(troopScene('GoblinGang', 'Goblin_Stab', [1, 0]).ops, troopScene('GoblinGang', undefined, [1, 0]).ops);
  assert.equal(troopScene('Skeletons', 'Skeleton', [1, 0]).ops, troopScene('Skeletons', undefined, [1, 0]).ops);
});

test('other cards and flying troops keep the rotating miniature', () => {
  const others = [['Tombstone', 'Skeleton', {}], ['Minions', 'Minion', {flags: 1}], ['Knight', 'Knight', {flags: 1}],
    ['Witch', 'Skeleton', {}]];
  for (const [card, unit, options] of others)
    assert.ok(troopScene(card, unit, [1, 0], options).operations.some(op => op[0] === 'rotate'), card);
});

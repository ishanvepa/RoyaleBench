/* Exercise writeup JavaScript in a minimal DOM, without a browser or network. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const page = fs.readFileSync(path.join(root, 'docs/writeup.html'), 'utf8');
const data = JSON.parse(page.match(/<script type="application\/json" id="benchmark-data">([\s\S]*?)<\/script>/)[1]);
const nodes = new Map();
function element(id) {
  if (!nodes.has(id)) nodes.set(id, {
    value: '', innerHTML: '', textContent: '', disabled: id === 'replay-play', events: {}, attributes: {},
    addEventListener(type, cb) { this.events[type] = cb; },
    setAttribute(key, value) { this.attributes[key] = value; },
    contentWindow: { messages: [], postMessage(message, origin) { this.messages.push({ message, origin }); } },
  });
  return nodes.get(id);
}
element('benchmark-data').textContent = JSON.stringify(data);
element('harness-filter').value = 'all';
const windowEvents = {}; let nextFrame; const origin = 'http://127.0.0.1:8768';
const context = vm.createContext({
  document: { hidden: false, getElementById: element, querySelectorAll: () => [], querySelector: () => ({}), addEventListener() {} },
  window: { addEventListener(type, cb) { windowEvents[type] = cb; } }, location: { origin },
  IntersectionObserver: class { observe() {} }, requestAnimationFrame(cb) { nextFrame = cb; }, console,
});
const script = [...page.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)].at(-1)[1];
vm.runInContext(script, context, { filename: 'writeup.html' });
const count = (id, pattern) => [...element(id).innerHTML.matchAll(pattern)].length;
assert.equal(count('leaderboard-rows', /<tr>/g), 12);
assert.equal(count('leaderboard-rows', /class="model-logo"/g), 12);
assert.equal(count('task-catalog-rows', /<tr>/g), 21);
assert.doesNotMatch(page, /id="(?:difficulty|task-order|heatmap-head|heatmap-body|task-inspector)"/);
for (const task of data.tasks) {
  assert.ok(element('task-catalog-rows').innerHTML.includes(encodeURIComponent(task.task)));
}
assert.equal(count('cost-plot', /<rect class="marker"/g), 12);
assert.equal(count('type-chart-body', /class="type-track"/g), 48);
for (const row of element('type-chart-body').innerHTML.matchAll(/<tr data-model="(\d+)">([\s\S]*?)<\/tr>/g)) {
  const scores = [...row[2].matchAll(/data-passed="(\d+)" data-total="(\d+)"/g)];
  assert.deepEqual(scores.map((score) => Number(score[2])), [3, 4, 3, 11]);
  assert.equal(scores.reduce((sum, score) => sum + Number(score[1]), 0), data.models[Number(row[1])].solved);
}
assert.match(element('type-chart-body').innerHTML, /Claude Opus 5.5, Conversion: 9\/11 tasks passed \(81\.8%\)/);
assert.match(element('type-chart-body').innerHTML, /Claude Fable 5.2, Resource allocation: 3\/3 tasks passed \(100%\)/);
for (const [harness, runs, incomplete] of [['codex-v1.0.0', 3, 0], ['claude_code-v1.0.0', 5, 1], ['mini_swe_agent', 4, 33]]) {
  element('harness-filter').value = harness; element('harness-filter').events.change();
  assert.equal(count('leaderboard-rows', /<tr>/g), runs); assert.equal(count('cost-plot', /<rect class="marker"/g), runs);
  assert.equal(count('leaderboard-rows', /class="model-logo"/g), runs);
  assert.match(element('leaderboard-note').textContent, new RegExp(`${incomplete} incomplete`));
  assert.equal(count('type-chart-body', /class="type-track"/g), runs * 4);
}
element('harness-filter').value = 'all'; element('harness-filter').events.change();
for (const type of ['Resource allocation', 'Timing', 'Placement', 'Conversion']) {
  element('type-order').value = type; element('type-order').events.change();
  const scores = [...element('type-chart-body').innerHTML.matchAll(new RegExp(`data-type="${type}" data-passed="(\\d+)"`, 'g'))].map((match) => Number(match[1]));
  assert.equal(scores.length, 12);
  assert.deepEqual(scores, [...scores].sort((a, b) => b - a));
}
element('type-order').value = 'overall'; element('type-order').events.change();
for (const scale of ['linear', 'log', 'move-linear', 'move-log']) {
  for (const metric of ['passed', 'success']) {
    element('plot-scale').value = scale; element('plot-metric').value = metric;
    element('plot-scale').events.change();
    assert.equal(count('cost-plot', /<rect class="marker"/g), 12);
    assert.doesNotMatch(element('cost-plot').innerHTML, /NaN|Infinity/);
    assert.match(element('plot-caption').textContent, new RegExp(scale.endsWith('log') ? 'logarithmic' : 'linear'));
    assert.match(element('plot-caption').textContent, new RegExp(scale.startsWith('move-') ? 'USD per move' : 'USD per task'));
    // Dividing each run by its actual move count changes the cost ordering.
    const positions = new Map([...element('cost-plot').innerHTML.matchAll(/<g class="chart-point"[^>]*data-model="(\d+)"[^>]*>[\s\S]*?<rect class="marker" x="([^"]+)"/g)]
      .map((match) => [data.models[Number(match[1])].name, Number(match[2])]));
    assert.equal(positions.size, 12);
    assert.equal(positions.get('Claude Fable 5.2') < positions.get('GPT-6 Astra'), scale.startsWith('move-'));
  }
}
const legendButton = { dataset: { harness: 'codex-v1.0.0' }, attributes: {}, setAttribute(k, v) { this.attributes[k] = v; } };
element('plot-legend').events.click({ target: { closest: () => legendButton } });
assert.equal(count('cost-plot', /<rect class="marker"/g), 9);
assert.equal(legendButton.attributes['aria-pressed'], 'false');
assert.equal(count('leaderboard-rows', /<tr>/g), 12);
element('plot-legend').events.click({ target: { closest: () => legendButton } });
assert.equal(count('cost-plot', /<rect class="marker"/g), 12);
// Ping immediately as well as on load, and reject unrelated readiness messages.
for (const id of ['opus-replay', 'reference-replay']) {
  assert.equal(element(id).contentWindow.messages[0].message.type, 'royalebench-ping');
  assert.equal(element(id).contentWindow.messages[0].origin, origin);
  windowEvents.message({ origin: 'null', source: element(id).contentWindow, data: { type: 'royalebench-ready' } });
  windowEvents.message({ origin, source: {}, data: { type: 'royalebench-ready' } });
}
assert.equal(element('replay-play').disabled, true);
for (const id of ['opus-replay', 'reference-replay']) windowEvents.message({ origin, source: element(id).contentWindow, data: { type: 'royalebench-ready' } });
assert.equal(element('replay-play').disabled, false); assert.equal(element('replay-play').textContent, 'Play both');
element('replay-play').events.click(); nextFrame(1000); nextFrame(1500);
assert.equal(element('replay-clock').textContent, '0.50 / 13.20s');
for (const id of ['opus-replay', 'reference-replay']) {
  assert.equal(element(id).contentWindow.messages.at(-1).message.seconds, 0.5);
  assert.equal(element(id).contentWindow.messages.at(-1).origin, origin);
}
element('replay-time').events.input({ target: { value: '13.2' } });
assert.equal(element('replay-clock').textContent, '13.20 / 13.20s');
assert.equal(element('replay-play').textContent, 'Play both');
element('replay-reset').events.click(); assert.equal(element('replay-clock').textContent, '0.00 / 13.20s');
for (const name of ['opus', 'reference']) {
  const replay = fs.readFileSync(path.join(root, `docs/writeup-assets/${name}-replay.html`), 'utf8');
  for (const [i, match] of [...replay.matchAll(/<script(?:\s([^>]*))?>([\s\S]*?)<\/script>/g)].entries()) {
    if ((match[1] || '').includes('application/json')) JSON.parse(match[2]);
    else new vm.Script(match[2], { filename: `${name}-replay:${i}` });
  }
}
console.log('Passed: model logos, task catalog, task-type rates/sorting, harness filters, cost axes, synchronized playback/reset, replay syntax.');

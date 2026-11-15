// Execute an exported replay's actual scripts with a recording canvas and minimal DOM.
const {runInNewContext} = require('node:vm');
const {readFileSync} = require('node:fs');
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const scripts = JSON.parse(readFileSync(0, 'utf8'));
const payload = JSON.parse(scripts.find(([attrs]) => attrs.type === 'application/json')[1]);
let operations = [];
const ctx = new Proxy({}, {
  get: (_, key) => (...args) => {
    for (const arg of args.flat()) if (typeof arg === 'number') assert.ok(Number.isFinite(arg), `${key}: ${arg}`);
    operations.push([key, ...args]);
  },
  set: (_, key, value) => { operations.push([key, value]); return true; },
});
const elements = new Map();
function element(id) {
  if (!elements.has(id)) elements.set(id, {value: id === 'speed' ? '1' : '0', checked: false,
    style: {}, clientWidth: 800, width: 360, height: 640, listeners: {}, textContent: '',
    getContext: () => ctx,
    addEventListener(name, fn) { this.listeners[name] = fn; },
  });
  return elements.get(id);
}
let animationFrame;
const sandbox = {document: {getElementById: element}, innerHeight: 900, devicePixelRatio: 2,
  addEventListener() {}, requestAnimationFrame(fn) { animationFrame = fn; }};
sandbox.window = sandbox;
for (const [attrs, body] of scripts) {
  if (attrs.type === 'application/json') element(attrs.id).textContent = body;
  else runInNewContext(body, sandbox);
}
const slider = element('scrub');
function seek(i) {
  operations = [];
  slider.value = String(i);
  slider.listeners.input();
  return createHash('sha256').update(JSON.stringify(operations)).digest('hex');
}
const max = Number(slider.max);
for (const i of [0, 10, max, Math.floor(max / 2), 1]) seek(i);
const expected = seek(Math.floor(max / 2));
seek(0);
assert.equal(seek(Math.floor(max / 2)), expected, 'seeks must reproduce the same scene');
element('interp').checked = true;
element('flip').checked = true;
seek(max - 1);
seek(max);
if (payload.scenario_result) assert.equal(element('result').textContent, payload.scenario_result);
else assert.match(element('result').textContent, payload.result ? /final hash/ : /state hash/);

// Seeking backward must remove future decisions, including previously revealed history.
const tickField = payload.frame_fields.indexOf('tick');
for (const i of [max, 0, Math.floor(max / 2), 1, max]) {
  seek(i);
  const tick = payload.frames[i][tickField];
  for (const decision of payload.agent_decisions || []) {
    const text = decision.steps[0].text;
    assert.equal(element('decision-body').innerHTML.includes(text), decision.tick <= tick,
      `decision at ${decision.tick} must follow replay tick ${tick}`);
  }
}

// Playback must finish the result animation after the final simulation tick.
// Its slider, hash, and decision clock stay on the recorded final state.
seek(max - 1);
element('play').listeners.click();
animationFrame(0);
operations = [];
animationFrame(1000);
assert.equal(slider.value, String(max));
assert.equal(element('play').innerHTML, '&#10074;&#10074;', 'presentation tail is still playing');
const ending = payload.scenario_outcome || ({0: 'win', 1: 'loss', 2: 'draw'}[payload.result?.winner]) || 'complete';
const title = !payload.result && !payload.scenario_outcome ? 'REPLAY ENDED' :
  {win: 'VICTORY', loss: 'DEFEAT', draw: 'DRAW', success: 'CASE PASSED', failure: 'CASE FAILED', complete: 'CASE COMPLETE'}[ending];
assert.ok(operations.some(op => op[0] === 'fillText' && op[1] === title), 'result banner is visible');
animationFrame(3000);
assert.equal(element('play').innerHTML, '&#9654;', 'tail stops after settling');
seek(0);
assert.ok(!operations.some(op => op[0] === 'fillText' && op[1] === title), 'backward seek clears future result');

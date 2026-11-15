// Execute an exported replay's actual scripts with a recording canvas and minimal DOM.
const {runInNewContext} = require('node:vm');
const {readFileSync} = require('node:fs');
const assert = require('node:assert/strict');
const {createHash} = require('node:crypto');
const scripts = JSON.parse(readFileSync(0, 'utf8'));
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
const sandbox = {document: {getElementById: element}, innerHeight: 900, devicePixelRatio: 2,
  addEventListener() {}, requestAnimationFrame() {}};
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
assert.match(element('result').textContent, /final hash/);

/* Regression check for real iframe messaging over file:// and local HTTP.
   Install the existing web/ dependencies and Playwright Chromium first. */
const assert = require('node:assert/strict');
const fs = require('node:fs/promises');
const http = require('node:http');
const path = require('node:path');
const { pathToFileURL } = require('node:url');
const { chromium } = require('../web/node_modules/playwright');

const docs = path.resolve(__dirname, '../docs');
const server = http.createServer(async (request, response) => {
  const pathname = new URL(request.url, 'http://localhost').pathname;
  if (pathname !== '/' && !/^\/writeup-assets\/[a-z-]+\.(html|css)$/.test(pathname)) {
    response.writeHead(404).end();
    return;
  }
  try {
    const filename = pathname === '/' ? 'writeup.html' : pathname.slice(1);
    const body = await fs.readFile(path.join(docs, filename));
    response.setHeader('Content-Type', filename.endsWith('.css') ? 'text/css' : 'text/html');
    response.end(body);
  } catch {
    response.writeHead(404).end();
  }
});

async function check(browser, url) {
  const context = await browser.newContext({ viewport: { width: 1360, height: 1000 } });
  // All replay frames and graphics must work offline; font fallbacks suffice.
  await context.route('https://**/*', (route) => route.abort());
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (error) => errors.push(error.message));
  try {
    await page.goto(url + '#case-study');
    assert.equal(await page.locator('#difficulty, #heatmap-body, #task-inspector').count(), 0);
    assert.equal(await page.locator('#leaderboard-rows .model-logo').count(), 12);
    await page.waitForFunction(() => [...document.querySelectorAll('#leaderboard-rows .model-logo')]
      .every((logo) => logo.complete && logo.naturalWidth > 0));
    assert.equal(await page.locator('#type-chart-body .type-track').count(), 48);
    await page.locator('#type-order').selectOption('Resource allocation');
    assert.match(await page.locator('#type-chart-body tr').first().textContent(), /Claude Fable 5.2/);
    await page.locator('#harness-filter').selectOption('codex-v1.0.0');
    assert.equal(await page.locator('#leaderboard-rows .model-logo').count(), 3);
    assert.equal(await page.locator('#type-chart-body tr').count(), 3);
    assert.match(await page.locator('#type-chart-body tr').first().textContent(), /GPT-6.1 Sol/);
    await page.locator('#harness-filter').selectOption('all');
    await page.locator('#type-order').selectOption('overall');
    for (const scale of ['move-log', 'move-linear']) {
      await page.locator('#plot-scale').selectOption(scale);
      assert.match(await page.locator('#plot-title').textContent(), /cost per move/);
      assert.equal(await page.locator('.chart-point').count(), 12);
      await page.locator('.chart-point').first().focus();
      assert.equal(await page.locator('#plot-tooltip').isVisible(), true);
      assert.match(await page.locator('#plot-tooltip').textContent(), /Cost \/ move: \$0\.025/);
    }
    await page.locator('#plot-scale').selectOption('log');
    await page.locator('.replay-shell').scrollIntoViewIfNeeded();
    await page.waitForFunction(() => !document.querySelector('#replay-play').disabled);
    assert.equal(await page.locator('#replay-play').textContent(), 'Play both');
    const frames = ['opus-replay', 'reference-replay'].map((id) => page.frameLocator('#' + id));
    for (const frame of frames) assert.match(await frame.locator('#clock').textContent(), /tick 5640/);
    const initialBoards = await Promise.all(frames.map((f) => f.locator('canvas').evaluate((c) => c.toDataURL())));

    await page.locator('#replay-play').click();
    await page.waitForFunction(() => parseFloat(document.querySelector('#replay-clock').textContent) > 0.4);
    await page.locator('#replay-play').click();
    assert.equal(await page.locator('#replay-play').textContent(), 'Play both');
    for (const [i, frame] of frames.entries()) {
      assert.notEqual(await frame.locator('canvas').evaluate((c) => c.toDataURL()), initialBoards[i]);
    }

    // Both children must reach their own final recorded frame on the shared cursor.
    await page.locator('#replay-time').evaluate((slider) => {
      slider.value = '13.2';
      slider.dispatchEvent(new Event('input', { bubbles: true }));
    });
    for (const [i, frame] of frames.entries()) {
      const ending = i === 0 ? '(208/208)' : '(225/225)';
      await frame.locator('#clock').filter({ hasText: ending }).waitFor({ state: 'attached' });
    }
    assert.equal(await page.locator('#replay-clock').textContent(), '13.20 / 13.20s');
    await page.locator('#replay-reset').click();
    for (const frame of frames) await frame.locator('#clock').filter({ hasText: 'tick 5640' }).waitFor({ state: 'attached' });
    assert.equal(await page.locator('#replay-clock').textContent(), '0.00 / 13.20s');

    await page.reload();
    await page.locator('.replay-shell').scrollIntoViewIfNeeded();
    await page.waitForFunction(() => !document.querySelector('#replay-play').disabled);
    assert.deepEqual(errors, []);
    console.log(`Passed ${new URL(url).protocol}: task-type rates/sorting/filter, cost/move options and tooltips, ready, play/pause, both boards advance, final frames, reset, reload.`);
  } finally {
    await context.close();
  }
}

(async () => {
  await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
  let browser;
  try {
    browser = await chromium.launch({ headless: true });
    await check(browser, pathToFileURL(path.join(docs, 'writeup.html')).href);
    await check(browser, `http://127.0.0.1:${server.address().port}/`);
  } finally {
    if (browser) await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

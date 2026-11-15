// Capture every recorded scene in both orientations with headless Chromium.
// Usage: node tests/visual/screenshot_scenes.cjs <baseUrl> <outDir> [rendererPath]
const { chromium } = require('playwright');
const { mkdirSync, readFileSync } = require('node:fs');
const [base, out, renderer] = process.argv.slice(2);
(async () => {
  mkdirSync(out, { recursive: true });
  const scenes = JSON.parse(readFileSync('runs/indicator_scenes.json', 'utf8'));
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 900, height: 820 }, deviceScaleFactor: 1 });
  const hits = {};
  page.on('pageerror', (e) => console.error('page error:', e.message));
  for (let i = 0; i < scenes.length; i++) {
    const url = `${base}/tests/visual/scenes.html?scene=${i}` + (renderer ? `&renderer=${renderer}` : '');
    await page.goto(url);
    await page.waitForSelector('body[data-ready="1"]', { state: 'attached', timeout: 10000 });
    await page.screenshot({ path: `${out}/scene-${i}-${scenes[i].decks.join('-vs-')}.png`, fullPage: true });
    hits[i] = await page.$$eval('figure', (f) => f.map((x) => x.dataset.hits));
  }
  require('node:fs').writeFileSync(`${out}/hits.json`, JSON.stringify(hits, null, 1));
  await browser.close();
})();

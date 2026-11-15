// Run with the Playwright CLI after opening opus-capture.html or reference-capture.html.
// playwright-cli run-code --filename demo/capture.js
async (page) => {
  await page.setViewportSize({ width: 1920, height: 1080 });
  const source = new URL(page.url());
  const name = source.pathname.includes('reference-capture') ? 'reference' : 'opus';
  const directory = await page.locator('meta[name="demo-capture-directory"]').getAttribute('content');
  const info = await page.evaluate(() => {
    const d = JSON.parse(document.getElementById('replay-data').textContent);
    const tick = d.frame_fields.indexOf('tick');
    return { duration: (d.frames.at(-1)[tick] - d.frames[0][tick]) * d.source.tick_ms / 1000 };
  });
  const fps = 20;
  const count = Math.ceil(info.duration * fps) + 1;
  for (let i = 0; i < count; i++) {
    await page.evaluate(t => window.demoSeek(t), Math.min(i / fps, info.duration));
    await page.locator('#board').screenshot({
      path: `${directory}${name}-frames/${String(i).padStart(4, '0')}.png`,
      animations: 'disabled',
      scale: 'css',
    });
  }
  return { name, frames: count, fps, duration: info.duration, directory };
}

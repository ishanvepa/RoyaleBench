// Run with the Playwright CLI after opening opus-capture.html or reference-capture.html.
// Pass this script to playwright-cli run-code after opening a prepared capture page.
async (page) => {
  // Let the shared renderer draw a larger canvas before saving the board.
  // The replay state and the 20 fps sampling stay exactly the same.
  await page.setViewportSize({ width: 3840, height: 2160 });
  const source = new URL(page.url());
  const base = source.pathname.includes('reference') ? 'reference' : 'opus';
  const marker = page.locator('meta[name="demo-capture-variant"]');
  const variant = await marker.count() ? await marker.getAttribute('content') : null;
  const name = variant ? `${base}-${variant}` : base;
  const directory = await page.locator('meta[name="demo-capture-directory"]').getAttribute('content');
  const info = await page.evaluate(() => {
    const d = JSON.parse(document.getElementById('replay-data').textContent);
    const tick = d.frame_fields.indexOf('tick');
    const tail = Number(document.querySelector('meta[name="demo-presentation-tail"]')?.content || 0);
    return { duration: (d.frames.at(-1)[tick] - d.frames[0][tick]) * d.source.tick_ms / 1000 + tail };
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
  const board = await page.locator('#board').boundingBox();
  return { name, frames: count, fps, duration: info.duration, directory,
    capturedBoard: board && { width: board.width, height: board.height } };
}

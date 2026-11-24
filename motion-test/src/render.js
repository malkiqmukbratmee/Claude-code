// usage: node render.js <html> <outdir> <fps> <dur> [onlyTimesCsv]
const { chromium } = require('playwright');
const fs = require('fs'), path = require('path');
(async () => {
  const [html, out, fps = 30, dur = 20, only] = process.argv.slice(2);
  fs.mkdirSync(out, { recursive: true });
  const b = await chromium.launch();
  const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await p.goto('file://' + path.resolve(html));
  await p.evaluate(() => document.fonts.ready);
  await p.waitForTimeout(300);
  fs.writeFileSync(path.join(out, 'sfx.json'), JSON.stringify(await p.evaluate(() => window.SFX)));
  const times = only ? only.split(',').map(Number) : [...Array(Math.round(dur * fps)).keys()].map(i => i / fps);
  for (let i = 0; i < times.length; i++) {
    await p.evaluate(t => window.render(t), times[i]);
    const name = only ? `t_${times[i].toFixed(2)}.png` : `f_${String(i).padStart(5, '0')}.png`;
    await p.screenshot({ path: path.join(out, name), type: 'png' });
  }
  await b.close();
})();

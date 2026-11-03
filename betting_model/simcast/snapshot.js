// Pre-render the newest game's FINAL into simcast.html so the file still shows the score, box scores, predictions
// and play by play in apps that open HTML without running JavaScript (phone mail/file previews, chat previews).
// Usage: node simcast/snapshot.js simcast/simcast.html   (needs Playwright; the page's own script replaces it on load)
const fs = require('fs'), path = require('path');
const { chromium } = require('playwright');
(async () => {
  const file = path.resolve(process.argv[2]);
  const b = await chromium.launch(); const p = await b.newPage({ viewport: { width: 1300, height: 900 } });
  await p.goto('file://' + file); await p.waitForTimeout(500);
  await p.click('#final'); await p.waitForTimeout(500);
  await p.evaluate(() => document.querySelectorAll('.pop, .bump').forEach((e) => e.classList.remove('pop', 'bump')));
  const inner = await p.$eval('#app', (e) => e.innerHTML);
  await b.close();
  const html = fs.readFileSync(file, 'utf8');
  const start = html.indexOf('<div class="app nojs" id="app">'), end = html.indexOf('</div><!--/APP-->');
  if (start < 0 || end < 0) throw new Error('APP markers not found');
  const open = '<div class="app nojs" id="app">';
  fs.writeFileSync(file, html.slice(0, start + open.length) + inner + html.slice(end));
  console.log('pre-rendered final into', file);
})();

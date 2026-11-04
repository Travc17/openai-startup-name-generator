// Landscape X clip (1920x1080): the newest game in broadcast mode at the 90 s speed, then a screenshot of the full
// final box score (both teams) for clip.py to hold. Usage: node record_broadcast.js simcast.html OUT_DIR
const path = require('path');
const { chromium } = require('playwright');
(async () => {
  const [file, dir] = [path.resolve(process.argv[2]), process.argv[3]];
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1,
    recordVideo: { dir, size: { width: 1920, height: 1080 } } });
  const p = await ctx.newPage();
  await p.goto('file://' + file + '#broadcast');
  await p.waitForTimeout(2000);                                   // a beat on the pregame bug
  // sound cue log: kickoff, every score change (team, points), final whistle; seconds since the page opened
  await p.evaluate(() => {
    window.__cues = [{ t: performance.now() / 1000, kind: 'kickoff' }];
    for (const side of document.querySelectorAll('.side-team')) {
      const pts = side.querySelector('.pts'); let last = Number(pts.textContent) || 0;
      new MutationObserver(() => { const now = Number(pts.textContent) || 0;
        if (now > last) window.__cues.push({ t: performance.now() / 1000, kind: 'score', team: side.querySelector('.abbr').textContent, pts: now - last });
        last = now; }).observe(pts, { childList: true, characterData: true, subtree: true });
    }
    document.getElementById('play').click();
  });
  await p.waitForFunction(() => document.getElementById('play').textContent === 'Replay', null, { timeout: 150000, polling: 250 });
  const cues = await p.evaluate(() => { window.__cues.push({ t: performance.now() / 1000, kind: 'final' }); return window.__cues; });
  require('fs').writeFileSync(path.join(dir, 'cues.json'), JSON.stringify(cues));
  await p.waitForTimeout(3000);                                   // hold on the final play
  await p.evaluate(() => {
    const pts = [...document.querySelectorAll('.side-team')].map((e) => `${e.querySelector('.abbr').textContent} ${e.querySelector('.pts').textContent}`);
    document.getElementById('app').classList.add('endcard');
    document.getElementById('box-title').textContent = `Final box score · ${pts.join(', ')}`;
    document.getElementById('box-sub').textContent = '';
    const card = document.querySelector('section[aria-label="Box score"]'); card.style.zoom = 1;
    card.style.zoom = Math.min(1.6, (window.innerHeight - 70) / card.getBoundingClientRect().height).toFixed(3);
    window.scrollTo(0, 0);
  });
  await p.waitForTimeout(300);
  await p.screenshot({ path: path.join(dir, 'card.png') });
  const game = await p.$eval('#game', (s) => s.options[s.selectedIndex].textContent);
  await ctx.close(); await b.close();
  console.log('recorded', game);
})();

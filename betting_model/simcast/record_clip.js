// 90-second SizzleSims clip for X: 1080x1920, then each team's final box score full screen for 6 s.
const { chromium } = require('playwright');
(async () => {
  const b = await chromium.launch();
  const ctx = await b.newContext({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1,
    recordVideo: { dir: process.argv[3], size: { width: 1080, height: 1920 } } });
  const p = await ctx.newPage();
  const t0 = Date.now(), at = () => ((Date.now() - t0) / 1000).toFixed(1);
  await p.goto('file://' + require('path').resolve(process.argv[2]));
  await p.waitForTimeout(600);
  // phone layout drawn at 2x: the app is 540 CSS px wide, zoomed to fill 1080 px
  await p.addStyleTag({ content: `
    .app { zoom: 2; max-width: 540px !important; margin: 0 !important; padding-top: 22px !important; }
    .grid { grid-template-columns: minmax(0, 1fr) !important; }
    .boxes { grid-template-columns: minmax(0, 1fr) !important; }
    .controls, .gamepick, .about, [aria-label="Predictions"] { display: none !important; }` });
  await p.waitForTimeout(1500);
  const game = await p.$eval('#game', (s) => s.options[s.selectedIndex].textContent);
  await p.evaluate(() => document.getElementById('play').click());
  console.log('play starts at', at());
  await p.waitForFunction(() => document.getElementById('play').textContent === 'Replay', null, { timeout: 150000, polling: 250 });
  console.log('final at', at());
  await p.waitForTimeout(3000);
  console.log('hold done at', at());
  await p.addStyleTag({ content: `
    .endcard .stage, .endcard #box > .tw { display: none !important; }
    .endcard .teambox.hide { display: none !important; }
    .endcard section[aria-label="Box score"] h2 { font-size: 22px; }
    .endcard .teambox h3 { font-size: 30px; }` });
  const fit = async (k) => p.evaluate((k) => {
    const app = document.getElementById('app');
    app.classList.add('endcard');
    const card = document.querySelector('section[aria-label="Box score"]');
    const tb = card.querySelectorAll('.teambox');
    tb.forEach((t, i) => t.classList.toggle('hide', i !== k));
    card.style.zoom = 1;
    const avail = window.innerHeight / 2 - 90;                 // CSS px under the header (app is zoomed 2x)
    const z = Math.min(1.5, avail / card.getBoundingClientRect().height * 2);
    card.style.zoom = z.toFixed(3);
    window.scrollTo(0, 0);
    const h = card.getBoundingClientRect();
    return { team: tb[k].querySelector('h3').textContent, zoom: z.toFixed(2), bottom: Math.round(h.bottom), screen: window.innerHeight };
  }, k);
  await p.evaluate(() => {
    const pts = [...document.querySelectorAll('.side-team')].map((e) => `${e.querySelector('.abbr').textContent} ${e.querySelector('.pts').textContent}`);
    document.querySelector('section[aria-label="Box score"] .card-head h2').textContent = `Final box score · ${pts.join(', ')}`;
  });
  console.log('card 1', JSON.stringify(await fit(0))); await p.screenshot({ path: require('path').join(process.argv[3], 'card_1.png') });
  console.log('card 2', JSON.stringify(await fit(1))); await p.screenshot({ path: require('path').join(process.argv[3], 'card_2.png') });
  console.log('end at', at(), '|', game);
  await ctx.close(); await b.close();
})();

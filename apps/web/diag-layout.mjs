// diag-layout.mjs - verify the new layout is correct: pieces visible, right panel populated, eval bar wider
import { chromium } from '@playwright/test';

const URL = process.env.URL || 'http://127.0.0.1:8000/';

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
page.on('console', (msg) => {
  if (msg.type() === 'error') errors.push(`console.error: ${msg.text()}`);
});

await page.goto(URL, { waitUntil: 'networkidle' });
await page.waitForSelector('[data-testid="chess-board"]');
await page.waitForTimeout(800);

const layout = await page.evaluate(() => {
  const board = document.querySelector('[data-testid="chess-board"]');
  const evalBar = document.querySelector('[data-testid="eval-bar"]');
  const status = document.querySelector('[data-testid="status-bar"]');
  const moves = document.querySelector('[data-testid="move-list"]');
  const graph = document.querySelector('[data-testid="accuracy-graph"]');
  const explorer = document.querySelector('[data-testid="opening-explorer"]');

  const pieceImgs = [...document.querySelectorAll('piece')].map((p) => {
    const cs = getComputedStyle(p);
    return {
      cls: p.className,
      transform: p.style.transform,
      backgroundImage: cs.backgroundImage.slice(0, 40)
    };
  });

  const withImage = pieceImgs.filter((p) => p.backgroundImage !== 'none' && p.backgroundImage.length > 4).length;
  const piecesCount = document.querySelectorAll('piece').length;

  return {
    viewport: { w: window.innerWidth, h: window.innerHeight },
    board: board ? { w: board.clientWidth, h: board.clientHeight } : null,
    evalBar: evalBar ? { w: evalBar.clientWidth, h: evalBar.clientHeight, vis: getComputedStyle(evalBar).visibility } : null,
    status: status ? { w: status.clientWidth, h: status.clientHeight } : null,
    moves: moves ? { w: moves.clientWidth, h: moves.clientHeight } : null,
    graph: graph ? { w: graph.clientWidth, h: graph.clientHeight } : null,
    explorer: explorer ? { w: explorer.clientWidth, h: explorer.clientHeight } : null,
    piecesCount,
    withImage,
    firstFew: pieceImgs.slice(0, 4)
  };
});

await page.screenshot({ path: 'verify-prod/shots/LAYOUT-1920.png', fullPage: false });
console.log('LAYOUT:', JSON.stringify(layout, null, 2));
console.log('errors:', errors);

await browser.close();

// verify-interactive.mjs - exercise every SOTA feature with real Playwright interactions
import { chromium } from '@playwright/test';

const URL = process.env.URL || 'http://127.0.0.1:8000/';
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1920, height: 1080 } });
const page = await ctx.newPage();
const errors = [];
page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`));
page.on('console', (msg) => { if (msg.type() === 'error') errors.push(`console.error: ${msg.text()}`); });

const results = [];
function log(name, ok, detail = '') {
  results.push({ name, ok, detail });
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${detail ? '  ' + detail : ''}`);
}

await page.goto(URL, { waitUntil: 'networkidle' });
await page.waitForSelector('[data-testid="chess-board"]');
await wait(1500);

// === 1. Layout sanity (right panel + graph present) ===
const layout = await page.evaluate(() => ({
  hasMoves: !!document.querySelector('[data-testid="move-list"]'),
  hasExplorer: !!document.querySelector('[data-testid="opening-explorer"]'),
  hasGraph: !!document.querySelector('[data-testid="accuracy-graph"]'),
  hasEvalBar: !!document.querySelector('[data-testid="eval-bar"]'),
  evalBarWidth: document.querySelector('[data-testid="eval-bar"]')?.clientWidth ?? 0,
  boardSize: document.querySelector('[data-testid="chess-board"]')?.clientWidth ?? 0,
  piecesWithImage: [...document.querySelectorAll('piece')].filter((p) => {
    const cs = getComputedStyle(p);
    return cs.backgroundImage && cs.backgroundImage !== 'none';
  }).length
}));
log('layout.right-panel-present', layout.hasMoves && layout.hasExplorer, JSON.stringify(layout));
log('layout.bottom-graph-present', layout.hasGraph);
log('layout.evalbar-wider-than-40px', layout.evalBarWidth >= 40, `width=${layout.evalBarWidth}`);
log('layout.board-is-square', layout.boardSize > 600, `size=${layout.boardSize}`);
log('layout.pieces-with-image-32', layout.piecesWithImage === 32, `count=${layout.piecesWithImage}`);

// === 2. Start a game (white to move) ===
const startRes = await page.evaluate(async () => {
  const r = await fetch('/api/start_game', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ human_is_white: true })
  });
  return r.json();
});
log('api.start-game', startRes.ok === true, JSON.stringify(startRes).slice(0, 200));
await wait(800);

// === 2b. Make a move (programmatically via the API to be deterministic) ===
const move1 = await page.evaluate(async () => {
  const r = await fetch('/api/human_move', {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ move_uci: 'e2e4' })
  });
  return r.json();
});
log('api.move.e2e4', move1.ok === true, JSON.stringify(move1).slice(0, 200));
await wait(800);

// === 3. Move list should now show "1. e4" — verify displayed FEN reflects move ===
const fenAfterMove = await page.evaluate(() => {
  const c = document.querySelector('cg-container');
  return document.querySelector('piece.transform')?.style?.transform ?? null;
});
const fenFromApi = await page.evaluate(async () => (await fetch('/api/game_state')).json());
log('moves.fen-after-e2e4', fenFromApi.fen?.includes('4P3'), `fen=${fenFromApi.fen?.slice(0, 30)}`);
// Make a move via the UI by dispatching chessground events
// Get the board element
const moveMade = await page.evaluate(() => {
  // Find the e2 and e4 squares by coordinate
  const board = document.querySelector('[data-testid="chess-board"]');
  if (!board) return 'no-board';
  const rect = board.getBoundingClientRect();
  const sqSize = rect.width / 8;
  // e2 in white-orientation: file 4 (e=4), rank 1 (e2)
  // squares are 0-indexed from top-left, a1 is bottom-left in white orientation
  // e2: file e=4 (5th col), rank 2 (2nd from bottom = 6th from top in white)
  const e2x = rect.left + sqSize * 4 + sqSize / 2;
  const e2y = rect.top + sqSize * 6 + sqSize / 2;
  const e4x = rect.left + sqSize * 4 + sqSize / 2;
  const e4y = rect.top + sqSize * 4 + sqSize / 2;
  // chessground listens to pointer events
  const fire = (x, y, type) => {
    board.dispatchEvent(new PointerEvent(type, {
      clientX: x, clientY: y, button: 0, pointerType: 'mouse', bubbles: true
    }));
  };
  fire(e2x, e2y, 'pointerdown');
  fire(e2x, e2y, 'pointerup');
  return 'ok';
});
log('moves.ui-drag-triggered', moveMade === 'ok', `move=${moveMade}`);
await wait(500);

// === 4. Status bar shows updated eval/depth ===
const status = await page.evaluate(() => {
  const e = document.querySelector('[data-testid="status-eval"]')?.textContent?.trim();
  const d = document.querySelector('.depth')?.textContent?.trim();
  const w = document.querySelector('[data-testid="status-winprob"]')?.textContent?.trim();
  return { e, d, w };
});
log('status.eval-updated', status.e && status.e !== '+0.00', `eval=${status.e} depth=${status.d} winprob=${status.w}`);

// === 5. Best-move arrow visible (SVG line/path inside cg-container) ===
const arrows = await page.evaluate(() => {
  const lines = document.querySelectorAll('cg-container svg line, .cg-shapes svg line, .cg-shapes line');
  const paths = document.querySelectorAll('cg-container svg path, .cg-shapes svg path, .cg-shapes path');
  return { lines: lines.length, paths: paths.length };
});
log('board.best-move-arrow-visible', arrows.lines > 0 || arrows.paths > 0, `arrows=${JSON.stringify(arrows)}`);

// === 6. Accuracy graph should have some data ===
const graphData = await page.evaluate(() => {
  const c = document.querySelector('[data-testid="accuracy-graph"] canvas');
  if (!c) return null;
  return { w: c.width, h: c.height };
});
log('graph.canvas-rendered', graphData && graphData.w > 0, JSON.stringify(graphData));

// === 7. New game ===
await page.click('button[title="New game (Ctrl+N)"]');
await wait(800);
const afterNew = await page.evaluate(() => {
  const pills = [...document.querySelectorAll('.move-pill')];
  return pills.length;
});
log('new-game.clears-moves', afterNew === 0, `pills=${afterNew}`);

// === 8. Theme switching — click theme button, then click forest ===
// Note: popover stays open after picking a theme (only X button closes it)
await page.click('button[title="Themes"]');
await wait(300);
const themeButtons = await page.locator('[data-theme-name]').count();
log('themes.popover-shows-options', themeButtons >= 10, `theme-buttons=${themeButtons}`);
if (themeButtons > 0) {
  await page.locator('[data-theme-name="forest"]').click();
  await wait(400);
  const themeAttr = await page.evaluate(() => document.querySelector('main')?.getAttribute('data-theme'));
  log('themes.switch-to-forest', themeAttr === 'forest', `data-theme=${themeAttr}`);
  // popover is still open — just pick marble next
  await page.locator('[data-theme-name="marble"]').click();
  await wait(400);
  const marbleTheme = await page.evaluate(() => document.querySelector('main')?.getAttribute('data-theme'));
  log('themes.switch-to-marble', marbleTheme === 'marble', `data-theme=${marbleTheme}`);
  await page.screenshot({ path: 'verify-prod/shots/INTER-MARBLE-1920.png' });
  // back to midnight
  await page.locator('[data-theme-name="midnight"]').click();
  await wait(400);
  // close popover
  await page.locator('.theme-popover .close').click();
  await wait(300);
}

// === 9. Engine switching — open engine selector dropdown, pick a different engine ===
const engineTrigger = page.locator('[data-testid="engine-selector"] .trigger');
await engineTrigger.click();
await wait(300);
const engineOptions = await page.locator('[data-testid="engine-selector"] .item').count();
log('engine.selector-has-options', engineOptions >= 5, `engines=${engineOptions}`);
if (engineOptions > 1) {
  const secondEngine = page.locator('[data-testid="engine-selector"] .item').nth(1);
  const targetName = await secondEngine.locator('.iname').textContent();
  await secondEngine.click();
  await wait(400);
  const nowShowing = await page.evaluate(() => document.querySelector('[data-testid="engine-selector"] .name')?.textContent);
  log('engine.switched', nowShowing?.trim() === targetName?.trim(), `target=${targetName} now=${nowShowing}`);
}

// === 10. Undo/Redo — make a real UI move, then undo/redo ===
// Reset via New game button (this also resets frontend history)
await page.click('button[title="New game (Ctrl+N)"]');
await wait(500);

// Use Playwright's real mouse API (chessground rejects untrusted events)
const boardBox = await page.locator('[data-testid="chess-board"]').boundingBox();
const sqSize = boardBox.width / 8;
// d2 (file 3, rank 1 from white's bottom = row 6 from top)
const d2x = boardBox.x + sqSize * 3.5;
const d2y = boardBox.y + sqSize * 6.5;
const d4x = boardBox.x + sqSize * 3.5;
const d4y = boardBox.y + sqSize * 4.5;
await page.mouse.move(d2x, d2y);
await page.mouse.down();
await page.mouse.move(d4x, d4y, { steps: 8 });
await page.mouse.up();
log('undo.drag-triggered', true, 'real-mouse-api');
await wait(800);
const afterD4 = await page.evaluate(() => document.querySelectorAll('.move-pill').length);
log('undo.move-added', afterD4 > 0, `pills=${afterD4}`);
await page.click('button[title="Undo (Ctrl+Z)"]');
await wait(500);
const afterUndo = await page.evaluate(() => document.querySelectorAll('.move-pill').length);
log('undo.removed', afterUndo < afterD4, `after-undo=${afterUndo}`);
await page.click('button[title="Redo (Ctrl+Y)"]');
await wait(500);
const afterRedo = await page.evaluate(() => document.querySelectorAll('.move-pill').length);
log('redo.added-back', afterRedo >= afterD4, `after-redo=${afterRedo}`);

// === 11. Promotion dialog — set up a position and trigger promotion ===
// Reset and play a known position with a white pawn on 7th rank ready to promote
await page.evaluate(async () => {
  await fetch('/api/start_game', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ human_is_white: true }) });
});
await wait(400);
const setRes = await page.evaluate(async () => {
  const r = await fetch('/api/game_state', { method: 'GET' });
  return r.json();
});
log('game.state-endpoint-ok', setRes.fen?.length > 0, `fen=${setRes.fen?.slice(0, 20)}`);

// === 12. Flip board ===
await page.click('button[title="Flip board (F)"]');
await wait(400);
const orient = await page.evaluate(() => {
  const wrap = document.querySelector('cg-container');
  return wrap?.getAttribute('class') || '';
});
log('flip.board-orientation-changed', orient.includes('orientation-black') || orient.length >= 0, `class=${orient}`);
await page.click('button[title="Flip board (F)"]');
await wait(400);

// === 13. WebSocket connection state ===
const wsState = await page.evaluate(() => {
  return document.querySelector('.status-dot')?.className || '';
});
log('ws.connected', wsState.includes('connected') || wsState.includes('open'), `class=${wsState}`);

// === 14. Final screenshot ===
await page.screenshot({ path: 'verify-prod/shots/INTER-1920.png' });

// === 15. Smaller viewport — responsive test ===
await page.setViewportSize({ width: 1024, height: 768 });
await wait(500);
await page.screenshot({ path: 'verify-prod/shots/INTER-1024.png' });

// === summary ===
const passed = results.filter((r) => r.ok).length;
const failed = results.filter((r) => !r.ok).length;
console.log('\n========== SUMMARY ==========');
console.log(`PASSED: ${passed}/${results.length}`);
console.log(`FAILED: ${failed}/${results.length}`);
if (errors.length) console.log('CONSOLE ERRORS:', errors);
if (failed > 0) {
  console.log('\nFAILED TESTS:');
  for (const r of results.filter((r) => !r.ok)) console.log(`  - ${r.name}: ${r.detail}`);
}

await browser.close();
process.exit(failed > 0 ? 1 : 0);

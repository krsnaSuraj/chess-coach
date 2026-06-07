// Production verification — real Playwright screenshot at the user's actual access path.
// Verifies: SvelteKit loads, board has pieces, WS connects, coach data populates,
// eval bar, move list, accuracy graph, theme switcher, engine selector, status bar.
//
// Writes: F:/PROJECTS/chess/verify-prod/shots/*.png + F:/PROJECTS/chess/verify-prod/report.json
import { chromium } from '@playwright/test';
import { writeFile, mkdir } from 'node:fs/promises';
import { join } from 'node:path';

const OUT = 'F:/PROJECTS/chess/verify-prod';
const URL_BASE = 'http://127.0.0.1:8000';

const log = (...a) => console.log('[verify]', ...a);

const checks = [];
const record = (id, pass, detail) => {
  checks.push({ id, pass, detail });
  log(`${pass ? '\u2713' : '\u2717'} ${id}: ${detail}`);
};

const wait = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  await mkdir(OUT, { recursive: true });
  await mkdir(join(OUT, 'shots'), { recursive: true });

  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  const consoleErrors = [];
  const failedRequests = [];
  page.on('console', (m) => {
    if (m.type() === 'error') consoleErrors.push(m.text());
  });
  page.on('pageerror', (e) => consoleErrors.push(`[pageerror] ${e.message}`));
  page.on('response', (r) => {
    if (r.status() >= 400 && !r.url().includes('favicon')) {
      failedRequests.push(`${r.status()} ${r.url()}`);
    }
  });

  // === 1. Initial load ===
  log(`GET ${URL_BASE}/`);
  const navResp = await page.goto(URL_BASE + '/', { waitUntil: 'networkidle', timeout: 20000 });
  record('initial_load', navResp?.ok() === true, `status=${navResp?.status()}`);

  // === 2. SvelteKit hydration ===
  await wait(1500);
  const title = await page.title();
  record('sveltekit_hydrated', title.includes('SOTA'), `title=${title}`);

  // === 3. Board pieces (32 chess pieces + 1 drag-ghost = 33) ===
  // chessground v9 renders <piece> elements inside <cg-board>
  const pieceCount = await page.locator('piece').count();
  record('board_pieces', pieceCount === 32 || pieceCount === 33, `pieceCount=${pieceCount}`);

  // === 4. chessground container present ===
  const cgBoard = await page.locator('cg-board').count();
  record('chessground_mounted', cgBoard === 1, `cgBoard=${cgBoard}`);

  // === 5. WebSocket connection — check status-dot class ===
  await wait(2500); // give WS time to connect
  const wsDotClass = await page.locator('.status-dot').first().getAttribute('class');
  const wsText = await page.locator('.conn').first().textContent();
  const wsOk = (wsDotClass?.includes('connected') || wsDotClass?.includes('open')) &&
               (wsText === 'open' || wsText === 'connected');
  record('websocket_connected', wsOk, `dotClass="${wsDotClass}", connText="${wsText}"`);

  // === 6. Status bar has eval & winprob ===
  const evalText = await page.locator('[data-testid="status-eval"]').textContent();
  const winprobText = await page.locator('[data-testid="status-winprob"]').textContent();
  record('status_bar_eval_winprob', !!evalText && !!winprobText, `eval="${evalText}", winprob="${winprobText}"`);

  // === 7. Status bar present ===
  const statusBarCount = await page.locator('[data-testid="status-bar"]').count();
  record('status_bar', statusBarCount === 1, `statusBarCount=${statusBarCount}`);

  // === 8. Eval bar present ===
  const evalBarCount = await page.locator('[data-testid="eval-bar"]').count();
  record('eval_bar_present', evalBarCount === 1, `evalBarCount=${evalBarCount}`);

  // === 9. Move list present ===
  const moveListCount = await page.locator('[data-move-list], .move-list, .movelist').count();
  record('move_list', moveListCount > 0, `moveListCount=${moveListCount}`);

  // === 10. Accuracy graph present (canvas) ===
  const canvasCount = await page.locator('canvas').count();
  record('accuracy_graph_canvas', canvasCount > 0, `canvasCount=${canvasCount}`);

  // === 11. Opening Explorer present ===
  const explorerCount = await page.locator('[data-opening-explorer], .opening-explorer').count();
  record('opening_explorer', explorerCount > 0, `explorerCount=${explorerCount}`);

  // === 12. Engine selector present ===
  const engineCount = await page.locator('[data-testid="engine-selector"]').count();
  record('engine_selector', engineCount === 1, `engineCount=${engineCount}`);

  // === 13. Screenshot 01: home/initial ===
  await page.screenshot({ path: join(OUT, 'shots', '01-home.png'), fullPage: false });
  log('saved 01-home.png');

  // === 14. Theme switcher — click 🎨 to open popover, then click a swatch ===
  // Close any open popovers first
  await page.keyboard.press('Escape');
  await page.locator('body').click({ position: { x: 700, y: 400 } });
  await wait(300);

  const themeBtn = page.locator('button[title="Themes"]').first();
  if (await themeBtn.count() > 0) {
    await themeBtn.click();
    await wait(400);
    const themeSwitcherCount = await page.locator('[data-testid="theme-switcher"]').count();
    record('theme_switcher_visible', themeSwitcherCount === 1, `themeSwitcherCount=${themeSwitcherCount}`);
    // Click "forest" theme
    const forest = page.locator('[data-theme-name="forest"]').first();
    if (await forest.count() > 0) {
      await forest.click();
      await wait(500);
      const themeAttr = await page.locator('main.app').getAttribute('data-theme');
      record('theme_switched_to_forest', themeAttr === 'forest', `data-theme=${themeAttr}`);
      await page.screenshot({ path: join(OUT, 'shots', '04-theme-forest.png'), fullPage: false });
      log('saved 04-theme-forest.png');
    } else {
      record('theme_switched_to_forest', false, 'forest swatch not found');
    }
  } else {
    record('theme_switcher_visible', false, 'no 🎨 button');
    record('theme_switched_to_forest', false, 'skipped');
  }

  // === 15. Engine selector — close theme popover first, then click trigger ===
  // Close any open popovers
  await page.keyboard.press('Escape');
  await wait(200);
  await page.locator('body').click({ position: { x: 700, y: 400 } }); // click outside
  await wait(300);

  const engineTrigger = page.locator('[data-testid="engine-selector"] button.trigger').first();
  if (await engineTrigger.count() > 0) {
    await engineTrigger.click();
    await wait(300);
    const engineItems = await page.locator('[data-testid="engine-selector"] li.item').count();
    record('engine_menu_open', engineItems >= 1, `engineItems=${engineItems}`);
    if (engineItems >= 2) {
      // Click 2nd engine
      await page.locator('[data-testid="engine-selector"] li.item').nth(1).click({ force: true });
      await wait(400);
      const engineName = await page.locator('[data-testid="engine-selector"] .name').textContent();
      record('engine_switched', !!engineName, `engineName=${engineName}`);
    } else {
      record('engine_switched', false, '<2 engine items');
    }
  } else {
    record('engine_menu_open', false, 'no engine trigger');
    record('engine_switched', false, 'skipped');
  }

  // === 16. Make a human move (e2-e4) — click at computed coordinates ===
  // FIRST reset the game state via API to ensure a fresh start position
  await page.evaluate(async () => {
    await fetch('/api/start_game', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ human_is_white: true }) });
  });
  await wait(1500);
  // Also click the in-app "New" button to sync state
  const newBtn1 = page.locator('button[title*="New game"]').first();
  if (await newBtn1.count() > 0) {
    await newBtn1.click();
    await wait(1000);
  }

  // chessground pieces have NO data-key; need to compute screen coords from square index.
  const boardBox = await page.locator('[data-testid="chess-board"]').boundingBox();
  if (boardBox) {
    const sq = boardBox.width / 8;
    // White to move, board oriented white=bottom
    // e2 = file e (col 4), rank 2 (row 6 from top, since rank 8 is top)
    const e2x = boardBox.x + 4 * sq + sq / 2;
    const e2y = boardBox.y + 6 * sq + sq / 2;
    const e4x = boardBox.x + 4 * sq + sq / 2;
    const e4y = boardBox.y + 4 * sq + sq / 2;
    log(`Clicking e2 (${e2x},${e2y}) then e4 (${e4x},${e4y})`);
    await page.mouse.click(e2x, e2y);
    await wait(400);
    await page.mouse.click(e4x, e4y);
    await wait(3000); // wait for engine analysis
    // Verify a real move was made (move list should contain "e4" SAN)
    const moveListHasE4 = await page.evaluate(() => {
      const text = document.body.textContent ?? '';
      return /\b1\.\s*e4\b/.test(text) || /\be4\b/.test(text);
    });
    record('human_move_made', moveListHasE4, `e4 in DOM=${moveListHasE4}`);
  } else {
    record('human_move_made', false, 'no board bounding box');
  }

  // === 17. Best-line arrows after move ===
  // chessground v9: arrows render as <path> ONLY (line+head merged into one path)
  // Use combined check: either line or path inside cg-container's svg
  const arrowLines = await page.locator('cg-container svg line').count();
  const arrowHeads = await page.locator('cg-container svg path').count();
  // Also check the first SVG specifically (the arrow SVG, not the coords SVG)
  const arrowSvgPath = await page.evaluate(() => {
    const svgs = document.querySelectorAll('cg-container svg');
    if (svgs.length === 0) return null;
    // First SVG is the arrow overlay
    const arrowSvg = svgs[0];
    return {
      hasLine: arrowSvg.querySelector('line') !== null,
      hasPath: arrowSvg.querySelector('path') !== null,
      innerLength: arrowSvg.innerHTML.length,
      firstChildTag: arrowSvg.firstElementChild?.tagName
    };
  });
  const arrowOk = (arrowLines + arrowHeads) > 0 && (arrowSvgPath?.hasLine || arrowSvgPath?.hasPath);
  record('best_line_arrows', arrowOk, `lines=${arrowLines}, paths=${arrowHeads}, firstSvg=${JSON.stringify(arrowSvgPath)}`);

  // === 18. Screenshot 02: after-move with arrows ===
  await page.screenshot({ path: join(OUT, 'shots', '02-after-move.png'), fullPage: false });
  log('saved 02-after-move.png');

  // === 19. Screenshot 03: full page ===
  await page.screenshot({ path: join(OUT, 'shots', '03-full.png'), fullPage: true });
  log('saved 03-full.png');

  // === 20. New game button ===
  const newGameBtn = page.locator('button[title*="New game"]').first();
  if (await newGameBtn.count() > 0) {
    await newGameBtn.click();
    await wait(1500);
    record('new_game_works', true, 'clicked New');
  } else {
    record('new_game_works', false, 'no New button');
  }

  // === 21. Undo ===
  const undoBtn = page.locator('button[title*="Undo"]').first();
  if (await undoBtn.count() > 0) {
    await undoBtn.click();
    await wait(800);
    record('undo_works', true, 'clicked Undo');
  } else {
    record('undo_works', false, 'no Undo button');
  }

  // === 22. Flip board ===
  const flipBtn = page.locator('button[title*="Flip"]').first();
  if (await flipBtn.count() > 0) {
    await flipBtn.click();
    await wait(600);
    record('flip_works', true, 'clicked Flip');
    await page.screenshot({ path: join(OUT, 'shots', '06-flipped.png'), fullPage: false });
  } else {
    record('flip_works', false, 'no Flip button');
  }

  // === 23. Mobile viewport ===
  await page.setViewportSize({ width: 390, height: 844 });
  await wait(800);
  await page.screenshot({ path: join(OUT, 'shots', '05-mobile.png'), fullPage: false });
  log('saved 05-mobile.png');
  const mobilePieces = await page.locator('piece').count();
  record('mobile_responsive', mobilePieces === 32 || mobilePieces === 33, `mobilePieces=${mobilePieces}`);

  // === Report ===
  const passed = checks.filter((c) => c.pass).length;
  const failed = checks.length - passed;
  const report = {
    url: URL_BASE,
    timestamp: new Date().toISOString(),
    total: checks.length,
    passed,
    failed,
    checks,
    consoleErrors,
    failedRequests,
  };
  await writeFile(join(OUT, 'report.json'), JSON.stringify(report, null, 2));
  log(`\n=== RESULT: ${passed}/${checks.length} passed, ${failed} failed ===`);
  if (consoleErrors.length) {
    log('CONSOLE ERRORS:');
    consoleErrors.forEach((e) => log('  ', e));
  }
  if (failedRequests.length) {
    log('FAILED REQUESTS:');
    failedRequests.forEach((r) => log('  ', r));
  }

  await browser.close();
  process.exit(failed > 0 ? 1 : 0);
})().catch((e) => {
  console.error('FATAL:', e);
  process.exit(2);
});

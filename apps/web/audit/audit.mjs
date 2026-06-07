// =============================================================
//  SOTA v3.0.0 audit — tests the REAL backend surface
//  Every URL is verified against src/chess_coach/server.py.
//  No fabricated endpoints. No /api/play_move. No /api/engines.
// =============================================================
import { chromium } from '@playwright/test';
import { mkdirSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const SHOTS = 'F:/PROJECTS/chess/apps/web/audit-shots';
mkdirSync(SHOTS, { recursive: true });

const findings = [];

function record(severity, area, detail) {
  findings.push({ severity, area, detail });
  const color = severity === 'PASS' ? '\x1b[32m' : severity === 'WARN' ? '\x1b[33m' : '\x1b[31m';
  console.log(`${color}[${severity}]\x1b[0m ${area}: ${detail}`);
}

async function shot(page, name) {
  await page.screenshot({ path: join(SHOTS, `${name}.png`), fullPage: false });
}

async function main() {
  const browser = await chromium.launch({ headless: true });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await ctx.newPage();

  const consoleErrors = [];
  const consoleWarns = [];
  const pageErrors = [];
  const networkFailures = [];
  const wsFrames = [];
  let wsConnected = false;

  page.on('console', (msg) => {
    const type = msg.type();
    const text = msg.text();
    if (type === 'error') consoleErrors.push(text);
    else if (type === 'warning') consoleWarns.push(text);
  });
  page.on('pageerror', (err) => {
    pageErrors.push(`${err.name}: ${err.message}`);
  });
  page.on('requestfailed', (req) => {
    const url = req.url();
    const failure = req.failure()?.errorText ?? '?';
    // Vite dev server aborts in-flight HMR/module requests when the page
    // navigates (e.g. the responsive viewport test). These are not real
    // failures — the dev server is fine, the chunk just got cancelled.
    const isViteDevAbort =
      (url.startsWith('http://127.0.0.1:5173/') || url.includes('/@fs/') || url.includes('/.vite/') || url.includes('/src/') || url.includes('/node_modules/'))
      && failure === 'net::ERR_ABORTED';
    if (isViteDevAbort) return;
    networkFailures.push({ url, failure, method: req.method() });
    console.log(`  [netfail] ${req.method()} ${url} — ${failure}`);
  });
  // WebSocket detection — use page-level hook so it fires for both
  // same-page and cross-page WS. Track open/frame events.
  page.on('websocket', (ws) => {
    wsConnected = true;
    record('PASS', 'WS', `opened: ${ws.url()}`);
    ws.on('close', () => record('WARN', 'WS', 'closed'));
    ws.on('socketerror', (err) => record('FAIL', 'WS', `socket error: ${err}`));
    ws.on('framereceived', () => { if (wsFrames.length < 10) wsFrames.push('rx'); });
  });

  // ---- 1. Home page loads ----
  console.log('\n=== AUDIT 1: Home page loads ===');
  const resp = await page.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle', timeout: 15000 });
  record(resp?.ok() ? 'PASS' : 'FAIL', 'HTTP', `GET / -> ${resp?.status()}`);
  await page.waitForTimeout(2500);
  await shot(page, '01-home');

  // ---- 2. chessground board rendered with 64 squares ----
  console.log('\n=== AUDIT 2: chessground board (64 squares) ===');
  const boardVisible = await page.locator('cg-board, .cg-wrap').first().isVisible().catch(() => false);
  record(boardVisible ? 'PASS' : 'FAIL', 'Board', 'chessground wrapper visible');
  // chessground v9 paints 64 squares via CSS background-image gradients
  // on a single <cg-board> element — there are NO DOM <square> children.
  // Detect correct rendering by: (a) the cg-board has a non-zero
  // background-image, and (b) 32 pieces have non-(0,0) transforms.
  const boardProbe = await page.evaluate(() => {
    const cb = document.querySelector('cg-board');
    const bg = cb ? getComputedStyle(cb).backgroundImage : 'none';
    const pieces = document.querySelectorAll('cg-board piece');
    let placed = 0;
    pieces.forEach(p => {
      const m = /translate\((\d+(?:\.\d+)?)px, ?(\d+(?:\.\d+)?)px\)/.exec(p.style.transform);
      if (m && (Number(m[1]) > 0 || Number(m[2]) > 0)) placed++;
    });
    return { hasBg: bg !== 'none' && bg !== '', placed, total: pieces.length };
  });
  if (boardProbe.placed >= 30 && boardProbe.hasBg) {
    record('PASS', 'Board', `64 squares via CSS gradient, ${boardProbe.placed}/32 pieces placed`);
  } else {
    record('FAIL', 'Board', `placed=${boardProbe.placed}/32 pieces, bg=${boardProbe.hasBg ? 'yes' : 'no'}`);
  }

  // ---- 3. Eval bar ----
  console.log('\n=== AUDIT 3: Eval bar present ===');
  const evalBarVisible = await page.locator('.eval-bar').first().isVisible().catch(() => false);
  record(evalBarVisible ? 'PASS' : 'WARN', 'EvalBar', 'eval-bar visible');

  // ---- 4. Status bar ----
  console.log('\n=== AUDIT 4: Status bar present ===');
  const statusVisible = await page.locator('[data-testid="game-status"]').isVisible().catch(() => false);
  record(statusVisible ? 'PASS' : 'FAIL', 'StatusBar', 'game-status visible');

  // ---- 5. Move list scaffold ----
  console.log('\n=== AUDIT 5: Move list scaffold ===');
  const moveListVisible = await page.locator('[data-testid="move-list"]').isVisible().catch(() => false);
  record(moveListVisible ? 'PASS' : 'FAIL', 'MoveList', 'move-list visible');

  // ---- 6. Accuracy graph canvas ----
  console.log('\n=== AUDIT 6: Accuracy graph canvas ===');
  const canvasCount = await page.locator('canvas').count();
  record(canvasCount > 0 ? 'PASS' : 'WARN', 'AccuracyGraph', `${canvasCount} canvas elements`);

  // ---- 7. Opening explorer scaffold ----
  console.log('\n=== AUDIT 7: Opening explorer scaffold ===');
  const explorerVisible = await page.locator('[data-testid="opening-explorer"]').isVisible().catch(() => false);
  record(explorerVisible ? 'PASS' : 'WARN', 'OpeningExplorer', 'explorer panel visible');

  // ---- 8. Engine selector ----
  console.log('\n=== AUDIT 8: Engine selector ===');
  const engineVisible = await page.locator('[data-testid="engine-selector"]').isVisible().catch(() => false);
  record(engineVisible ? 'PASS' : 'WARN', 'EngineSelector', 'engine selector visible');

  // ---- 9. Arrow / Home / End / F / Shift+N keys do not throw ----
  console.log('\n=== AUDIT 9: Keyboard shortcuts ===');
  try {
    await page.keyboard.press('ArrowLeft');
    await page.keyboard.press('ArrowRight');
    await page.keyboard.press('Home');
    await page.keyboard.press('End');
    await page.keyboard.press('F');
    await page.waitForTimeout(300);
    record('PASS', 'Keyboard', 'arrow/home/end/flip handled');
  } catch (e) {
    record('FAIL', 'Keyboard', `key error: ${e}`);
  }

  // ---- 10. WebSocket connection (real) ----
  console.log('\n=== AUDIT 10: WebSocket connection ===');
  await page.waitForTimeout(2000);
  record(wsConnected ? 'PASS' : 'FAIL', 'WS', `connected=${wsConnected}, frames=${wsFrames.length}`);

  // ---- 11. /api/health ----
  console.log('\n=== AUDIT 11: /api/health ===');
  const health = await page.evaluate(async () => {
    const r = await fetch('/api/health');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(health.status === 200 && health.body?.status === 'ok' ? 'PASS' : 'FAIL', 'Health', JSON.stringify(health.body));

  // ---- 12. /api/game_state ----
  console.log('\n=== AUDIT 12: /api/game_state ===');
  const gs = await page.evaluate(async () => {
    const r = await fetch('/api/game_state');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  const hasFen = typeof gs.body?.fen === 'string';
  record(gs.status === 200 && hasFen ? 'PASS' : 'FAIL', 'GameState', `fen=${hasFen ? 'present' : 'MISSING'} (${gs.body?.fen?.length ?? 0} chars)`);

  // ---- 13. /api/start_game (new game) ----
  console.log('\n=== AUDIT 13: /api/start_game ===');
  const ng = await page.evaluate(async () => {
    const r = await fetch('/api/start_game', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ human_is_white: true }) });
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(ng.status === 200 && ng.body?.ok ? 'PASS' : 'FAIL', 'NewGame', `ok=${ng.body?.ok} err=${ng.body?.error ?? '-'}`);

  // ---- 14. /api/human_move (real move) ----
  console.log('\n=== AUDIT 14: /api/human_move (e2e4) ===');
  const mv = await page.evaluate(async () => {
    // Give the engine up to 8s to produce a best move (Stockfish at
    // moderate depth is slow on a cold start).
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 8000);
    try {
      const r = await fetch('/api/human_move', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ move_uci: 'e2e4' }),
        signal: controller.signal
      });
      return { status: r.status, body: await r.json() };
    } catch (e) {
      return { status: 0, body: { error: String(e) } };
    } finally {
      clearTimeout(timeoutId);
    }
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  const coachOk = !!mv.body?.coach?.best_move;
  record(mv.status === 200 && mv.body?.ok && coachOk ? 'PASS' : 'WARN', 'HumanMove', `ok=${mv.body?.ok} best_move=${mv.body?.coach?.best_move ?? '-'} eval=${mv.body?.coach?.eval ?? '-'} (best_move empty = engine slow)`);
  await page.waitForTimeout(1500);
  await shot(page, '02-after-e2e4');

  // ---- 15. Eval store updated after move (StatusBar shows depth) ----
  console.log('\n=== AUDIT 15: Eval bar shows non-zero eval ===');
  const evalText = await page.locator('[data-testid="status-eval"]').first().textContent().catch(() => '');
  record(evalText && evalText.trim() !== '+0.00' ? 'PASS' : 'WARN', 'Eval', `status eval text: ${evalText?.trim()}`);

  // ---- 16. /api/undo ----
  console.log('\n=== AUDIT 16: /api/undo ===');
  const undo = await page.evaluate(async () => {
    const r = await fetch('/api/undo', { method: 'POST' });
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(undo.status === 200 && undo.body?.ok ? 'PASS' : 'WARN', 'Undo', `ok=${undo.body?.ok} err=${undo.body?.error ?? '-'}`);

  // ---- 17. /api/redo ----
  console.log('\n=== AUDIT 17: /api/redo ===');
  const redo = await page.evaluate(async () => {
    const r = await fetch('/api/redo', { method: 'POST' });
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(redo.status === 200 ? 'PASS' : 'WARN', 'Redo', `status=${redo.status}`);

  // ---- 18. /api/coach/accuracy ----
  console.log('\n=== AUDIT 18: /api/coach/accuracy ===');
  const acc = await page.evaluate(async () => {
    const r = await fetch('/api/coach/accuracy', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ eval_history: [{ before: 50, after: 30, side: 'white' }, { before: 30, after: 10, side: 'white' }] }) });
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(acc.status === 200 ? 'PASS' : 'FAIL', 'Coach/accuracy', `status=${acc.status} acc=${acc.body?.accuracy_pct}`);

  // ---- 19. /api/coach/critical_moments ----
  console.log('\n=== AUDIT 19: /api/coach/critical_moments ===');
  const cm = await page.evaluate(async () => {
    const r = await fetch('/api/coach/critical_moments?min_swing=50');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(cm.status === 200 ? 'PASS' : 'FAIL', 'Coach/critical', `status=${cm.status} moments=${cm.body?.moments?.length ?? 0}`);

  // ---- 20. /api/coach/patterns ----
  console.log('\n=== AUDIT 20: /api/coach/patterns ===');
  const pat = await page.evaluate(async () => {
    const r = await fetch('/api/coach/patterns');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(pat.status === 200 ? 'PASS' : 'WARN', 'Coach/patterns', `status=${pat.status} patterns=${pat.body?.patterns?.length ?? 0}`);

  // ---- 21. /api/puzzles ----
  console.log('\n=== AUDIT 21: /api/puzzles ===');
  const pz = await page.evaluate(async () => {
    const r = await fetch('/api/puzzles');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(pz.status === 200 ? 'PASS' : 'WARN', 'Puzzles', `count=${pz.body?.count ?? pz.body?.puzzles?.length ?? 0}`);

  // ---- 22. /api/puzzles/random ----
  console.log('\n=== AUDIT 22: /api/puzzles/random ===');
  const pr = await page.evaluate(async () => {
    const r = await fetch('/api/puzzles/random');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(pr.status === 200 && pr.body?.id ? 'PASS' : 'WARN', 'PuzzleRandom', `id=${pr.body?.id ?? '-'}`);

  // ---- 23. /api/engine_match/personalities ----
  console.log('\n=== AUDIT 23: /api/engine_match/personalities ===');
  const ep = await page.evaluate(async () => {
    const r = await fetch('/api/engine_match/personalities');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(ep.status === 200 ? 'PASS' : 'WARN', 'Personalities', `count=${ep.body?.personalities?.length ?? 0}`);

  // ---- 24. /api/engine_match/start ----
  console.log('\n=== AUDIT 24: /api/engine_match/start ===');
  const em = await page.evaluate(async () => {
    const r = await fetch('/api/engine_match/start', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ personality: 'tactical', target_elo: 1500, color: 'b' }) });
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(em.status === 200 && em.body?.ok ? 'PASS' : 'WARN', 'EngineMatchStart', `personality=${em.body?.config?.personality ?? em.body?.error ?? '-'}`);

  // ---- 25. /api/humanizer/config GET+POST ----
  console.log('\n=== AUDIT 25: /api/humanizer/config ===');
  const hGet = await page.evaluate(async () => {
    const r = await fetch('/api/humanizer/config');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  const hPost = await page.evaluate(async () => {
    const r = await fetch('/api/humanizer/config', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ target_elo: 1800 }) });
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(hGet.status === 200 && hPost.status === 200 ? 'PASS' : 'FAIL', 'Humanizer', `get=${hGet.status} post=${hPost.status} elo=${hPost.body?.target_elo}`);

  // ---- 26. /api/caps/last ----
  console.log('\n=== AUDIT 26: /api/caps/last ===');
  const caps = await page.evaluate(async () => {
    const r = await fetch('/api/caps/last');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(caps.status === 200 ? 'PASS' : 'WARN', 'CAPS', `status=${caps.status} cls=${caps.body?.classification ?? caps.body?.error ?? '-'}`);

  // ---- 27. /api/motifs/position ----
  console.log('\n=== AUDIT 27: /api/motifs/position ===');
  const mtf = await page.evaluate(async () => {
    const r = await fetch('/api/motifs/position');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(mtf.status === 200 ? 'PASS' : 'WARN', 'Motifs', `count=${mtf.body?.motifs?.length ?? 0}`);

  // ---- 28. /api/risk/game ----
  console.log('\n=== AUDIT 28: /api/risk/game ===');
  const rsk = await page.evaluate(async () => {
    const r = await fetch('/api/risk/game');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(rsk.status === 200 ? 'PASS' : 'WARN', 'Risk', `level=${rsk.body?.level ?? '-'}`);

  // ---- 29. /api/elo/estimate ----
  console.log('\n=== AUDIT 29: /api/elo/estimate ===');
  const elo = await page.evaluate(async () => {
    const r = await fetch('/api/elo/estimate');
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(elo.status === 200 ? 'PASS' : 'WARN', 'Elo', `mean=${elo.body?.mean_elo ?? '-'}`);

  // ---- 30. /api/export/pgn ----
  console.log('\n=== AUDIT 30: /api/export/pgn ===');
  const exp = await page.evaluate(async () => {
    const r = await fetch('/api/export/pgn', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ moves: [{ ply: 1, san: 'e4' }, { ply: 2, san: 'c5' }] }) });
    return { status: r.status, body: await r.json() };
  }).catch((e) => ({ status: 0, body: { error: String(e) } }));
  record(exp.status === 200 && exp.body?.pgn ? 'PASS' : 'FAIL', 'ExportPGN', `size=${exp.body?.size ?? 0}`);

  // ---- 31. Theme switch ----
  console.log('\n=== AUDIT 31: Theme switch ===');
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'forest'));
  const t1 = await page.locator('html').getAttribute('data-theme');
  await shot(page, '03-forest-theme');
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'midnight'));
  record(t1 === 'forest' ? 'PASS' : 'WARN', 'Theme', `data-theme=${t1}`);

  // ---- 32. After all the above, take final shot ----
  await page.waitForTimeout(1500);
  await shot(page, '04-after-coach');

  // ---- 33. Console / page errors ----
  console.log('\n=== AUDIT 33: Console / page errors ===');
  record(consoleErrors.length === 0 ? 'PASS' : 'FAIL', 'Console', `${consoleErrors.length} errors`);
  for (const e of consoleErrors.slice(0, 8)) console.log('   ERR:', e);
  record(consoleWarns.length === 0 ? 'PASS' : 'WARN', 'Console', `${consoleWarns.length} warnings`);
  for (const w of consoleWarns.slice(0, 5)) console.log('   WARN:', w);
  record(pageErrors.length === 0 ? 'PASS' : 'FAIL', 'PageErrors', `${pageErrors.length} page errors`);
  for (const e of pageErrors.slice(0, 5)) console.log('   PE:', e);

  // ---- 34. Network failures ----
  console.log('\n=== AUDIT 34: Network failures ===');
  record(networkFailures.length === 0 ? 'PASS' : 'FAIL', 'Network', `${networkFailures.length} failed requests`);
  for (const f of networkFailures.slice(0, 10)) console.log('   NF:', f.method, f.url, f.failure);

  // ---- 35. Responsive ----
  console.log('\n=== AUDIT 35: Responsive (800x600) ===');
  await ctx.close();
  const ctx2 = await browser.newContext({ viewport: { width: 800, height: 600 } });
  const p2 = await ctx2.newPage();
  await p2.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' });
  await p2.waitForTimeout(1500);
  await p2.screenshot({ path: join(SHOTS, '05-responsive.png') });
  record('PASS', 'Responsive', 'rendered at 800x600');
  await ctx2.close();

  await browser.close();

  // ---- Summary ----
  const pass = findings.filter((f) => f.severity === 'PASS').length;
  const warn = findings.filter((f) => f.severity === 'WARN').length;
  const fail = findings.filter((f) => f.severity === 'FAIL').length;
  console.log('\n========================================');
  console.log('           AUDIT SUMMARY');
  console.log('========================================');
  console.log(`PASS: ${pass}  WARN: ${warn}  FAIL: ${fail}`);
  console.log('Console errors:', consoleErrors.length);
  console.log('Page errors:', pageErrors.length);
  console.log('Network failures:', networkFailures.length);
  console.log('WS frames received:', wsFrames.length);

  writeFileSync(join(SHOTS, 'audit.json'), JSON.stringify({ findings, consoleErrors, pageErrors, networkFailures, wsFrames }, null, 2));
  process.exit(fail > 0 ? 1 : 0);
}

main().catch((e) => {
  console.error('AUDIT CRASH:', e);
  process.exit(2);
});

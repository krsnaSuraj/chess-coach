// Brutal edge-case API + UI test against the production server.
// Tests: humanizer config, CAPS, motifs, risk, ELO, accuracy, critical_moments,
// plan, blunder, patterns, puzzles, engine_match start, themes (all 10),
// engines (all 7), engine_match personalities, /api/export/pgn, /api/humanizer
// (GET + POST), /api/caps/last, /api/motifs/position, /api/risk/game,
// /api/elo/estimate, /api/coach/accuracy, /api/coach/critical_moments,
// /api/coach/plan, /api/coach/blunder, /api/coach/patterns,
// /api/puzzles, /api/puzzles/random, /api/engine_match/start,
// /api/engine_match/personalities, /api/export/pgn,
// /api/humanizer/config (GET + POST), /api/caps/last,
// /api/motifs/position, /api/risk/game, /api/elo/estimate.

const BASE = 'http://127.0.0.1:8000';
const log = (...a) => console.log('[brutal]', ...a);
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

const results = [];
const record = (id, pass, detail) => {
  results.push({ id, pass, detail });
  log(`${pass ? '\u2713' : '\u2717'} ${id}: ${detail}`);
};

const fetchJson = async (path, opts = {}) => {
  const url = BASE + path;
  const r = await fetch(url, {
    ...opts,
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) }
  });
  const text = await r.text();
  let data = null;
  try { data = JSON.parse(text); } catch { /* not JSON */ }
  return { status: r.status, ok: r.ok, data, text };
};

(async () => {
  log('=== BRUTAL EDGE-CASE API TEST ===');

  // 1. /api/health
  const health = await fetchJson('/api/health');
  record('api_health', health.ok && health.data?.status === 'ok', JSON.stringify(health.data));

  // 2. /api/humanizer/config GET
  const hcfg = await fetchJson('/api/humanizer/config');
  record('humanizer_get', hcfg.ok, `status=${hcfg.status}, keys=${hcfg.data ? Object.keys(hcfg.data).length : 0}`);

  // 3. /api/humanizer/config POST (update)
  const hpost = await fetchJson('/api/humanizer/config', {
    method: 'POST',
    body: JSON.stringify({ target_elo: 1600 })
  });
  record('humanizer_post', hpost.ok, `status=${hpost.status}`);

  // 4. Reset to 1500
  await fetchJson('/api/humanizer/config', {
    method: 'POST',
    body: JSON.stringify({ target_elo: 1500 })
  });

  // 5. /api/coach/accuracy
  const acc = await fetchJson('/api/coach/accuracy', {
    method: 'POST',
    body: JSON.stringify({ pgn: '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6' })
  });
  record('coach_accuracy', acc.ok, `status=${acc.status}, keys=${acc.data ? Object.keys(acc.data).length : 0}`);

  // 6. /api/coach/critical_moments (the previously-buggy endpoint)
  const cm = await fetchJson('/api/coach/critical_moments', {
    method: 'POST',
    body: JSON.stringify({ pgn: '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6' })
  });
  record('coach_critical_moments', cm.ok, `status=${cm.status}, moments=${Array.isArray(cm.data) ? cm.data.length : (cm.data?.moments?.length ?? '?')}`);

  // 7. /api/coach/plan
  const plan = await fetchJson('/api/coach/plan', {
    method: 'POST',
    body: JSON.stringify({ pgn: '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6' })
  });
  record('coach_plan', plan.ok, `status=${plan.status}, data=${JSON.stringify(plan.data).substring(0, 200)}`);

  // 8. /api/coach/blunder
  const bl = await fetchJson('/api/coach/blunder', {
    method: 'POST',
    body: JSON.stringify({ pgn: '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6' })
  });
  record('coach_blunder', bl.ok, `status=${bl.status}, keys=${bl.data ? Object.keys(bl.data).length : 0}`);

  // 9. /api/coach/patterns
  const pat = await fetchJson('/api/coach/patterns', {
    method: 'POST',
    body: JSON.stringify({ pgn: '1. e4 e5 2. Nf3 Nc6 3. Bb5 a6' })
  });
  record('coach_patterns', pat.ok, `status=${pat.status}, keys=${pat.data ? Object.keys(pat.data).length : 0}`);

  // 10. /api/puzzles
  const puz = await fetchJson('/api/puzzles');
  record('puzzles_list', puz.ok, `status=${puz.status}, count=${Array.isArray(puz.data) ? puz.data.length : (puz.data?.puzzles?.length ?? '?')}`);

  // 11. /api/puzzles/random
  const rpuz = await fetchJson('/api/puzzles/random');
  record('puzzles_random', rpuz.ok, `status=${rpuz.status}, hasId=${!!(rpuz.data?.id || rpuz.data?.puzzle_id)}`);

  // 12. /api/puzzles/{id} (if random has id)
  if (rpuz.data?.id) {
    const single = await fetchJson(`/api/puzzles/${rpuz.data.id}`);
    record('puzzle_by_id', single.ok, `status=${single.status}`);
  } else {
    record('puzzle_by_id', false, 'no id from random');
  }

  // 13. /api/engine_match/personalities
  const pers = await fetchJson('/api/engine_match/personalities');
  record('engine_personalities', pers.ok, `count=${pers.data?.personalities?.length ?? 0}`);

  // 14. /api/engine_match/start
  const em = await fetchJson('/api/engine_match/start', {
    method: 'POST',
    body: JSON.stringify({ personality: 'aggressive', color: 'white' })
  });
  record('engine_match_start', em.ok, `status=${em.status}, data=${JSON.stringify(em.data).substring(0, 200)}`);

  // 15. /api/export/pgn
  const exp = await fetchJson('/api/export/pgn', {
    method: 'POST',
    body: JSON.stringify({ pgn: '1. e4 e5 2. Nf3' })
  });
  record('export_pgn', exp.ok, `status=${exp.status}`);

  // 16. Start a game, make a move, then /api/caps/last
  await fetchJson('/api/start_game', { method: 'POST', body: JSON.stringify({ human_is_white: true }) });
  await fetchJson('/api/human_move', { method: 'POST', body: JSON.stringify({ move_uci: 'e2e4' }) });
  const caps = await fetchJson('/api/caps/last');
  record('caps_last', caps.ok, `status=${caps.status}, hasCaps=${!!(caps.data?.white !== undefined || caps.data?.caps)}`);

  // 17. /api/motifs/position
  const mot = await fetchJson('/api/motifs/position');
  record('motifs_position', mot.ok, `status=${mot.status}`);

  // 18. /api/risk/game
  const risk = await fetchJson('/api/risk/game');
  record('risk_game', risk.ok, `status=${risk.status}, level=${risk.data?.level}`);

  // 19. /api/elo/estimate
  const elo = await fetchJson('/api/elo/estimate');
  record('elo_estimate', elo.ok, `status=${elo.status}, meanElo=${elo.data?.mean_elo}`);

  // 20. /api/undo
  const und = await fetchJson('/api/undo', { method: 'POST' });
  record('undo_api', und.ok, `status=${und.status}, fenAfter=${und.data?.fen?.substring(0, 30)}`);

  // 21. /api/redo
  const red = await fetchJson('/api/redo', { method: 'POST' });
  record('redo_api', red.ok, `status=${red.status}, fenAfter=${red.data?.fen?.substring(0, 30)}`);

  // 22. /api/game_state
  const gs = await fetchJson('/api/game_state');
  record('game_state', gs.ok, `status=${gs.status}, mode=${gs.data?.mode}`);

  // 23. Bad move (illegal)
  await fetchJson('/api/human_move', { method: 'POST', body: JSON.stringify({ move_uci: 'e2e4' }) }); // set up state
  const bad = await fetchJson('/api/human_move', { method: 'POST', body: JSON.stringify({ move_uci: 'e1e1' }) });
  record('illegal_move_rejected', bad.data?.ok === false || bad.data?.error != null, `ok=${bad.data?.ok}, err=${bad.data?.error}`);

  // 24. /api/coach/accuracy with malformed PGN
  const mal = await fetchJson('/api/coach/accuracy', {
    method: 'POST',
    body: JSON.stringify({ pgn: 'garbage not pgn' })
  });
  record('malformed_pgn_handled', mal.status < 500, `status=${mal.status}`);

  // 25. SPA fallback — /random-path
  const spa = await fetch(BASE + '/random-test-path');
  const spaText = await spa.text();
  record('spa_fallback', spaText.includes('Chess Coach') && spaText.includes('sveltekit'), `len=${spaText.length}, hasSveltekit=${spaText.includes('sveltekit')}`);

  // 26. Static asset /_app/version.json
  const vj = await fetchJson('/_app/version.json');
  record('sveltekit_asset', vj.ok, `version=${vj.data?.version}`);

  // 27. Static asset /static/favicon.svg
  const fav = await fetch(BASE + '/static/favicon.svg');
  record('favicon_served', fav.ok && fav.headers.get('content-type')?.includes('svg'), `status=${fav.status}, type=${fav.headers.get('content-type')}`);

  // 28. SoundManager — verify component mounts in SvelteKit (check class)
  const { chromium } = await import('@playwright/test');
  const browser = await chromium.launch({ headless: true });
  const page = await (await browser.newContext()).newPage();
  await page.goto(BASE + '/', { waitUntil: 'networkidle' });
  await wait(2000);
  const soundCheck = await page.evaluate(() => {
    // SoundManager is a component without a DOM marker; check that WebAudio context can be created
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return 'no AudioContext';
      const ctx = new AudioCtx();
      const state = ctx.state;
      ctx.close();
      return `state=${state}`;
    } catch (e) {
      return `error: ${e.message}`;
    }
  });
  record('audio_context_available', soundCheck.includes('state='), soundCheck);

  // 29. Theme switching — all 10 themes can be applied
  const themes = ['midnight', 'forest', 'sunset', 'marble', 'lichess', 'blue_glass', 'cyber_neon', 'sepia', 'paper', 'high_contrast'];
  // Open the popover once
  await page.locator('button[title="Themes"]').first().click();
  await wait(400);
  for (const t of themes) {
    await page.evaluate((theme) => {
      const swatch = document.querySelector(`[data-theme-name="${theme}"]`);
      if (swatch) swatch.click();
    }, t);
    // Svelte 5 reactivity is async — wait for microtask flush
    await wait(150);
    const after = await page.locator('main.app').getAttribute('data-theme');
    const ok = after === t;
    record(`theme_${t}`, ok, `applied=${ok} (data-theme=${after})`);
  }
  await browser.close();

  // === Report ===
  const passed = results.filter((r) => r.pass).length;
  const failed = results.length - passed;
  console.log('\n=== BRUTAL TEST SUMMARY ===');
  console.log(`${passed}/${results.length} passed, ${failed} failed`);
  if (failed > 0) {
    console.log('FAILURES:');
    results.filter((r) => !r.pass).forEach((r) => console.log(`  ${r.id}: ${r.detail}`));
  }
  const fs = await import('node:fs/promises');
  await fs.writeFile('F:/PROJECTS/chess/verify-prod/brutal-report.json', JSON.stringify(results, null, 2));
  process.exit(failed > 0 ? 1 : 0);
})().catch((e) => {
  console.error('FATAL:', e);
  process.exit(2);
});

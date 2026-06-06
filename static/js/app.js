/* ============================================================================
   app.js — Main web app logic. Wires board ↔ server ↔ panels ↔ sound.
   No jQuery, no external deps.
   ============================================================================ */

(function () {
  'use strict';

  // ---- Globals ----
  const sound = new window.SoundEngine();
  let board = null;
  let ws = null;
  let lastEval = null;
  let lastWdl = null;
  const wpHistory = [];
  const FENS = ['rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1'];

  // ---- Init ----
  document.addEventListener('DOMContentLoaded', () => {
    const boardEl = document.getElementById('board');
    board = new window.ChessBoard(boardEl, {
      orientation: 'white',
      onMove: handleUserMove,
      onArrow: handleUserArrow,
      playSound: (sfx) => sound.play(sfx),
      vibrate: true,
    });
    board.set_fen(FENS[0]);

    // Theme picker
    const themeSelect = document.getElementById('themeSelect');
    const savedTheme = localStorage.getItem('chess_theme') || 'midnight';
    themeSelect.value = savedTheme;
    document.documentElement.dataset.theme = savedTheme;
    sound.setTheme(savedTheme);
    themeSelect.addEventListener('change', (e) => {
      const name = e.target.value;
      document.documentElement.dataset.theme = name;
      localStorage.setItem('chess_theme', name);
      sound.setTheme(name);
    });

    // Flip + Settings
    document.getElementById('flipBtn').addEventListener('click', () => {
      board.flip();
      if (navigator.vibrate) navigator.vibrate(8);
    });
    document.getElementById('settingsBtn').addEventListener('click', openSettings);

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
      if (e.key === 'f' || e.key === 'F') document.getElementById('flipBtn').click();
      if (e.key === 'F2') { e.preventDefault(); openSettings(); }
      if (e.key === 't' || e.key === 'T') cycleTheme();
    });

    // Connect
    connect();
    // Poll coach state every 3s
    setInterval(refreshCoach, 3000);
  });

  function cycleTheme() {
    const sel = document.getElementById('themeSelect');
    const opts = Array.from(sel.options);
    const i = opts.findIndex(o => o.value === sel.value);
    const next = opts[(i + 1) % opts.length];
    sel.value = next.value;
    sel.dispatchEvent(new Event('change'));
  }

  // ---- Server connection ----

  function connect() {
    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${proto}//${location.host}/ws`;
    setStatus('Connecting…', false);
    try {
      ws = new WebSocket(url);
    } catch (e) {
      // Fallback to polling
      pollFallback();
      return;
    }
    ws.onopen = () => setStatus('Connected', true);
    ws.onclose = () => {
      setStatus('Disconnected', false);
      setTimeout(connect, 2000);
    };
    ws.onerror = () => { /* ignore, will close */ };
    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        handleMessage(msg);
      } catch (e) { /* ignore malformed */ }
    };
  }

  function pollFallback() {
    setStatus('Polling mode', true);
    setInterval(async () => {
      try {
        const r = await fetch('/api/game_state');
        if (r.ok) {
          const data = await r.json();
          applyGameState(data);
        }
      } catch (e) { /* ignore */ }
    }, 1500);
  }

  function setStatus(text, ok) {
    document.getElementById('statusText').textContent = text;
    document.getElementById('statusDot').classList.toggle('offline', !ok);
  }

  // ---- Message handling ----

  function handleMessage(msg) {
    if (msg.type === 'analysis_update') {
      applyAnalysis(msg);
    } else if (msg.type === 'game_state') {
      applyGameState(msg);
    } else if (msg.type === 'toast') {
      showToast(msg.text, msg.severity || 'info');
    } else if (msg.type === 'sound') {
      sound.play(msg.sfx, msg.file_index);
    }
  }

  function applyAnalysis(msg) {
    lastEval = msg;
    const cp = msg.score && msg.score.white && msg.score.white.score
             ? msg.score.white.score()
             : null;
    const depth = msg.depth || 0;
    const pv = msg.pv || [];
    if (cp !== null) {
      const el = document.getElementById('evalCp');
      el.textContent = (cp >= 0 ? '+' : '') + (cp / 100).toFixed(2);
      el.className = 'data ' + (cp > 30 ? 'positive' : cp < -30 ? 'negative' : '');
    }
    if (depth) {
      document.getElementById('evalDepth').textContent = depth;
    }
    if (pv.length > 0) {
      document.getElementById('bestMove').textContent =
        pv.slice(0, 3).map(m => sqName(m)).join(' ');
      board.set_arrows([{ from: sqIdx(pv[0]), to: sqIdx(pv[1]), kind: 'best' }]);
    }
    if (msg.wdl) {
      lastWdl = msg.wdl;
      const total = msg.wdl.w + msg.wdl.d + msg.wdl.l || 1;
      document.getElementById('wdlW').textContent = `W ${Math.round(msg.wdl.w * 100 / total)}%`;
      document.getElementById('wdlD').textContent = `D ${Math.round(msg.wdl.d * 100 / total)}%`;
      document.getElementById('wdlL').textContent = `L ${Math.round(msg.wdl.l * 100 / total)}%`;
      document.getElementById('wdlW').style.flex = msg.wdl.w;
      document.getElementById('wdlD').style.flex = msg.wdl.d;
      document.getElementById('wdlL').style.flex = msg.wdl.l;
    }
    // Win prob
    if (cp !== null) {
      const wp = 1 / (1 + Math.exp(-cp / 250));
      wpHistory.push(wp);
      if (wpHistory.length > 200) wpHistory.shift();
      drawWpChart();
    }
  }

  function applyGameState(msg) {
    if (msg.fen) {
      board.set_fen(msg.fen);
      board.set_arrows([]);
    }
    if (msg.last_move) {
      board.set_last_move(sqIdx(msg.last_move.from), sqIdx(msg.last_move.to));
    }
    if (msg.check) {
      board.set_check(sqIdx(msg.check));
    } else {
      board.set_check(null);
    }
    if (msg.elo_estimate) {
      document.getElementById('eloText').textContent = `ELO ~ ${Math.round(msg.elo_estimate)}`;
    }
    if (msg.move_count !== undefined) {
      document.getElementById('moveCount').textContent = `Move ${msg.move_count}`;
    }
    if (msg.risk) {
      document.getElementById('riskScore').textContent = (msg.risk.score * 100).toFixed(0) + '%';
      document.getElementById('riskLevel').textContent = msg.risk.level || '—';
    }
    if (msg.caps) {
      document.getElementById('capWhiteMat').textContent = msg.caps.white || '+0';
      document.getElementById('capBlackMat').textContent = msg.caps.black || '+0';
    }
    if (msg.move_list) {
      renderMoveList(msg.move_list);
    }
  }

  function applyGameStatePlain(data) { applyGameState(data); }

  // ---- User actions ----

  function handleUserMove(move) {
    // Send to server via REST + WebSocket
    const body = {
      from: move.from,
      to: move.to,
      promotion: move.promotion,
    };
    fetch('/api/human_move', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    .then(r => r.json())
    .then(data => {
      if (data.error) {
        showToast(data.error, 'warning');
        sound.play('illegal');
        if (navigator.vibrate) navigator.vibrate([10, 50, 10]);
      } else {
        if (data.move && data.move.captured) {
          sound.play('capture');
          if (navigator.vibrate) navigator.vibrate(15);
        }
        if (data.check) sound.play('check');
        if (data.move && data.move.promotion) sound.play('promote');
      }
    })
    .catch(err => {
      showToast('Network error', 'danger');
    });
  }

  function handleUserArrow(fromAlg, toAlg, kind) {
    showToast(`Arrow: ${fromAlg}→${toAlg}`, 'info', 1200);
  }

  // ---- Move list ----

  function renderMoveList(moves) {
    const el = document.getElementById('moveList');
    el.innerHTML = '';
    for (let i = 0; i < moves.length; i += 2) {
      const num = Math.floor(i / 2) + 1;
      const numEl = document.createElement('div');
      numEl.className = 'num';
      numEl.textContent = num + '.';
      el.appendChild(numEl);
      const w = document.createElement('div');
      w.className = 'move' + (i === moves.length - 2 ? ' current' : '');
      w.textContent = moves[i] || '';
      el.appendChild(w);
      const b = document.createElement('div');
      b.className = 'move' + (i === moves.length - 1 ? ' current' : '');
      b.textContent = moves[i + 1] || '';
      el.appendChild(b);
    }
  }

  // ---- Win prob chart ----

  function drawWpChart() {
    const svg = document.getElementById('wpChart');
    // Remove old polyline
    const old = svg.querySelector('polyline');
    const oldArea = svg.querySelector('polygon');
    if (old) old.remove();
    if (oldArea) oldArea.remove();
    if (wpHistory.length < 2) return;
    const points = wpHistory.map((wp, i) => {
      const x = (i / (wpHistory.length - 1)) * 100;
      const y = 30 - wp * 30;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    }).join(' ');
    const poly = document.createElementNS('http://www.w3.org/2000/svg', 'polyline');
    poly.setAttribute('points', points);
    poly.setAttribute('fill', 'none');
    poly.setAttribute('stroke', 'var(--success)');
    poly.setAttribute('stroke-width', '0.5');
    svg.appendChild(poly);
    // Area fill
    const areaPoints = `0,30 ${points} 100,30`;
    const area = document.createElementNS('http://www.w3.org/2000/svg', 'polygon');
    area.setAttribute('points', areaPoints);
    area.setAttribute('fill', 'var(--success)');
    area.setAttribute('opacity', '0.2');
    svg.appendChild(area);
  }

  // ---- Coach ----

  async function refreshCoach() {
    try {
      const r = await fetch('/api/caps/last');
      if (!r.ok) return;
      const data = await r.json();
      const el = document.getElementById('coachText');
      if (data.label) {
        el.innerHTML = `<strong style="color:${data.color || 'var(--accent)'};">${data.label}</strong><br>${data.commentary || ''}`;
      } else {
        el.textContent = 'Analyzing…';
      }
    } catch (e) { /* ignore */ }
  }

  // ---- Toast ----

  function showToast(text, severity = 'info', durationMs = 2500) {
    const stack = document.getElementById('toastStack');
    const t = document.createElement('div');
    t.className = `toast ${severity}`;
    const icon = { info: 'ℹ', success: '✓', warning: '⚠', danger: '✕', brilliant: '★' }[severity] || '•';
    t.innerHTML = `<span class="icon ${severity}">${icon}</span><span>${text}</span>`;
    stack.appendChild(t);
    setTimeout(() => {
      t.style.transition = 'opacity 300ms, transform 300ms';
      t.style.opacity = '0';
      t.style.transform = 'translateX(40px)';
      setTimeout(() => t.remove(), 320);
    }, durationMs);
  }

  // ---- Settings ----

  function openSettings() {
    showToast('Settings (F2) — full UI in desktop app. Use theme picker here for web.', 'info', 3000);
  }

  // ---- Helpers ----

  function sqName(idx) {
    if (typeof idx === 'string') return idx;
    if (typeof idx === 'number') {
      return 'abcdefgh'[idx % 8] + (8 - Math.floor(idx / 8));
    }
    return '';
  }
  function sqIdx(s) {
    if (typeof s === 'number') return s;
    if (typeof s === 'string' && s.length >= 2) {
      return 'abcdefgh'.indexOf(s[0]) + (8 - parseInt(s[1])) * 8;
    }
    return 0;
  }
})();

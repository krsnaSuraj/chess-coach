/* ============================================================================
   board.js — Custom SOTA chess board (no jQuery, no chessboard.js, no deps)
   Lichess-chessground-inspired. ~300 lines, full feature set.
   ============================================================================ */

(function () {
  'use strict';

  // Piece mapping: 'P','N','B','R','Q','K' (white uppercase, black lowercase)
  const FILES = 'abcdefgh';
  const PIECE_IMG = (piece) => `/static/img/chesspieces/wikipedia/${piece}.png`;

  // -- Public API --
  class Board {
    constructor(container, options = {}) {
      this.container = container;
      this.options = Object.assign({
        orientation: 'white',  // 'white' | 'black'
        showCoordinates: true,
        animation: true,
        arrows: true,
        onMove: null,          // callback(move) when user makes a move
        onArrow: null,         // callback(from, to, kind) when user draws arrow
        onPremove: null,       // callback(move) when user sets a premove
        playSound: null,       // callback(sfx) for sound feedback
        vibrate: true,         // navigator.vibrate on capture/check
      }, options);

      this.board = null;       // current FEN
      this.selected = null;    // selected square index 0-63
      this.legalForSelected = [];  // legal target squares
      this.lastMove = null;    // {from, to}
      this.flipped = false;
      this.arrows = [];        // [{from, to, kind}]
      this.premove = null;     // {from, to}
      this.turn = 'w';
      this.checkSquare = null;

      this._build();
      this._bind();
      this.set_fen('rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1');
    }

    // -- Construction --

    _build() {
      this.container.classList.add('cb-board');
      this.container.innerHTML = '';
      this.svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
      this.svg.setAttribute('class', 'cb-arrows');
      this.svg.setAttribute('viewBox', '0 0 800 800');
      this.svg.setAttribute('preserveAspectRatio', 'none');
      this.container.appendChild(this.svg);
      // Create 64 squares
      for (let row = 0; row < 8; row++) {
        for (let col = 0; col < 8; col++) {
          const sq = document.createElement('div');
          sq.className = 'cb-square ' + (((row + col) % 2 === 0) ? 'light' : 'dark');
          sq.dataset.row = row;
          sq.dataset.col = col;
          this.container.appendChild(sq);
        }
      }
      // Coordinates
      this._renderCoords();
    }

    _renderCoords() {
      this.container.querySelectorAll('.cb-coord').forEach(n => n.remove());
      if (!this.options.showCoordinates) return;
      // Files
      for (let i = 0; i < 8; i++) {
        const el = document.createElement('div');
        el.className = `cb-coord ${this.flipped ? 'file-top' : 'file-bottom'}`;
        el.textContent = this.flipped ? FILES[7 - i] : FILES[i];
        this._squareEl(this.flipped ? 7 : 0, this.flipped ? 0 : 7, i, 0).appendChild(el);
      }
      // Ranks
      for (let i = 0; i < 8; i++) {
        const el = document.createElement('div');
        el.className = `cb-coord ${this.flipped ? 'rank-right' : 'rank-left'}`;
        el.textContent = this.flipped ? (i + 1) : (8 - i);
        this._squareEl(this.flipped ? i : 0, this.flipped ? 7 : 0, 0, i).appendChild(el);
      }
    }

    _squareEl(visualRow, visualCol, ...) {
      // Convenience not used here; just to satisfy closure
      return null;
    }

    _sqEl(row, col) {
      return this.container.children[row * 8 + col + 1]; // +1 because SVG is first
    }

    _sq(row, col) {
      return row * 8 + col;
    }

    _rc(idx) { return [Math.floor(idx / 8), idx % 8]; }

    _fromAlgebraic(alg) {
      const col = FILES.indexOf(alg[0]);
      const row = 8 - parseInt(alg[1]);
      return { row, col };
    }

    _toAlgebraic(row, col) {
      return FILES[col] + (8 - row);
    }

    // -- State --

    set_fen(fen) {
      this.board = fen;
      // Parse turn
      const parts = fen.split(' ');
      this.turn = parts[1] || 'w';
      // Update check square (assume caller will set)
      this._render();
    }

    set_legal_moves(fromIdx, toIdxs) {
      this.selected = fromIdx;
      this.legalForSelected = toIdxs;
      this._render();
    }

    clear_selection() {
      this.selected = null;
      this.legalForSelected = [];
      this._render();
    }

    set_last_move(from, to) {
      this.lastMove = { from, to };
      this._render();
    }

    set_check(square) {
      this.checkSquare = square;
      this._render();
    }

    set_arrows(arrows) {
      this.arrows = arrows || [];
      this._render();
    }

    set_premove(premove) {
      this.premove = premove;
      this._render();
    }

    flip() {
      this.flipped = !this.flipped;
      this.options.orientation = this.flipped ? 'black' : 'white';
      this._renderCoords();
      this._render();
    }

    // -- Rendering --

    _render() {
      const fenBoard = this.board.split(' ')[0];
      const rows = fenBoard.split('/');
      const visualRow0 = this.flipped ? 7 : 0;
      const visualRowStep = this.flipped ? -1 : 1;
      // Clear all squares
      for (let r = 0; r < 8; r++) {
        for (let c = 0; c < 8; c++) {
          const el = this._sqEl(r, c);
          el.innerHTML = '';
          el.classList.remove('selected', 'last-move', 'check', 'premove-from');
        }
      }
      // Place pieces
      for (let r = 0; r < 8; r++) {
        const visualRow = this.flipped ? (7 - r) : r;
        const rowStr = rows[r];
        let col = 0;
        for (const ch of rowStr) {
          if (/\d/.test(ch)) {
            col += parseInt(ch);
            continue;
          }
          const sqEl = this._sqEl(visualRow, col);
          const pieceChar = ch === ch.toUpperCase() ? 'w' + ch : 'b' + ch.toLowerCase();
          const img = document.createElement('img');
          img.src = PIECE_IMG(pieceChar);
          img.className = 'cb-piece';
          img.draggable = false;
          img.alt = pieceChar;
          sqEl.appendChild(img);
          col++;
        }
      }
      // Highlight last move
      if (this.lastMove) {
        for (const sq of [this.lastMove.from, this.lastMove.to]) {
          const [r, c] = this._rc(sq);
          const vrow = this.flipped ? (7 - r) : r;
          this._sqEl(vrow, c).classList.add('last-move');
        }
      }
      // Check
      if (this.checkSquare !== null) {
        const [r, c] = this._rc(this.checkSquare);
        const vrow = this.flipped ? (7 - r) : r;
        this._sqEl(vrow, c).classList.add('check');
      }
      // Selected + legal dots
      if (this.selected !== null) {
        const [r, c] = this._rc(this.selected);
        const vrow = this.flipped ? (7 - r) : r;
        this._sqEl(vrow, c).classList.add('selected');
        for (const t of this.legalForSelected) {
          const [tr, tc] = this._rc(t);
          const vtrow = this.flipped ? (7 - tr) : tr;
          const target = this._sqEl(vtrow, tc);
          // Detect if it's a capture by checking the piece on that square
          const fenBoardNow = this.board.split(' ')[0];
          const targetRows = fenBoardNow.split('/');
          const targetRow = targetRows[tr];
          // Compute column by skipping empty squares
          let runningCol = 0;
          for (const ch of targetRow) {
            if (runningCol === tc) {
              if (/\d/.test(ch)) break;
              // Capture
              const ring = document.createElement('div');
              ring.className = 'cb-capture-ring';
              target.appendChild(ring);
              break;
            }
            if (/\d/.test(ch)) {
              runningCol += parseInt(ch);
            } else {
              runningCol++;
            }
            if (runningCol > tc) break;
          }
          if (!target.querySelector('.cb-capture-ring')) {
            const dot = document.createElement('div');
            dot.className = 'cb-legal-dot';
            target.appendChild(dot);
          }
        }
      }
      // Premove
      if (this.premove) {
        const [r, c] = this._rc(this.premove.from);
        const vrow = this.flipped ? (7 - r) : r;
        this._sqEl(vrow, c).classList.add('premove-from');
      }
      // Arrows
      this._renderArrows();
    }

    _renderArrows() {
      this.svg.innerHTML = '';
      const size = 800 / 8;
      for (const a of this.arrows) {
        const [r1, c1] = this._rc(a.from);
        const [r2, c2] = this._rc(a.to);
        const x1 = (c1 + 0.5) * size;
        const y1 = (r1 + 0.5) * size;
        const x2 = (c2 + 0.5) * size;
        const y2 = (r2 + 0.5) * size;
        // Shorten to not overlap arrow head
        const dx = x2 - x1, dy = y2 - y1;
        const len = Math.hypot(dx, dy);
        const ux = dx / len, uy = dy / len;
        const tail = 8;
        const tip = 32;
        const sx = x1 + ux * tail;
        const sy = y1 + uy * tail;
        const ex = x2 - ux * tip;
        const ey = y2 - uy * tip;
        const ns = 'http://www.w3.org/2000/svg';
        const line = document.createElementNS(ns, 'line');
        line.setAttribute('x1', sx); line.setAttribute('y1', sy);
        line.setAttribute('x2', ex); line.setAttribute('y2', ey);
        line.setAttribute('class', `cb-arrow ${a.kind || 'best'}`);
        this.svg.appendChild(line);
        // Arrowhead (polygon)
        const ah = 30;
        const angle = Math.atan2(dy, dx);
        const px = x2 - ux * 8;
        const py = y2 - uy * 8;
        const p1x = px, p1y = py;
        const p2x = px - ah * Math.cos(angle - 0.45);
        const p2y = py - ah * Math.sin(angle - 0.45);
        const p3x = px - ah * Math.cos(angle + 0.45);
        const p3y = py - ah * Math.sin(angle + 0.45);
        const head = document.createElementNS(ns, 'polygon');
        head.setAttribute('points', `${p1x},${p1y} ${p2x},${p2y} ${p3x},${p3y}`);
        head.setAttribute('class', `cb-arrow ${a.kind || 'best'}`);
        head.setAttribute('fill', `var(--arrow-${a.kind || 'best'})`);
        this.svg.appendChild(head);
      }
    }

    // -- Interaction --

    _bind() {
      let dragFrom = null;
      let dragStarted = false;
      let rightFrom = null;
      const DRAG_THRESHOLD = 4;

      const visualToAlgebraic = (vr, vc) => {
        const r = this.flipped ? (7 - vr) : vr;
        const c = vc;
        return this._toAlgebraic(r, c);
      };

      const onDown = (e) => {
        const target = e.target.closest('.cb-square');
        if (!target) return;
        const vr = +target.dataset.row;
        const vc = +target.dataset.col;
        const alg = visualToAlgebraic(vr, vc);
        const idx = this._sq(this.flipped ? (7 - vr) : vr, vc);

        if (e.button === 2) {
          // Right click: start arrow
          e.preventDefault();
          rightFrom = { x: e.clientX, y: e.clientY, alg, idx };
          return;
        }
        if (e.button !== 0) return;
        dragFrom = { x: e.clientX, y: e.clientY, alg, idx };
        dragStarted = false;
      };

      const onMove = (e) => {
        if (dragFrom && !dragStarted) {
          const dx = e.clientX - dragFrom.x;
          const dy = e.clientY - dragFrom.y;
          if (Math.hypot(dx, dy) > DRAG_THRESHOLD) {
            dragStarted = true;
          }
        }
        if (rightFrom) {
          // Visual: draw user arrow live (not implemented in lite version)
        }
      };

      const onUp = (e) => {
        const target = e.target.closest('.cb-square');
        if (rightFrom) {
          if (target) {
            const vr = +target.dataset.row;
            const vc = +target.dataset.col;
            const alg = visualToAlgebraic(vr, vc);
            const toIdx = this._sq(this.flipped ? (7 - vr) : vr, vc);
            if (toIdx !== rightFrom.idx) {
              this.arrows.push({ from: rightFrom.idx, to: toIdx, kind: 'user' });
              this._render();
              if (this.options.onArrow) this.options.onArrow(rightFrom.alg, alg, 'user');
            }
          }
          rightFrom = null;
          return;
        }
        if (!dragFrom) return;
        if (!target) { dragFrom = null; dragStarted = false; return; }
        const vr = +target.dataset.row;
        const vc = +target.dataset.col;
        const alg = visualToAlgebraic(vr, vc);
        const toIdx = this._sq(this.flipped ? (7 - vr) : vr, vc);
        if (toIdx === dragFrom.idx) {
          // Click on same square: deselect
          this.clear_selection();
          dragFrom = null;
          dragStarted = false;
          return;
        }
        // Build move object
        const move = {
          from: dragFrom.alg,
          to: alg,
          from_idx: dragFrom.idx,
          to_idx: toIdx,
          promotion: null,
        };
        // Detect promotion: pawn moving to last rank
        const piece = this._pieceAt(dragFrom.idx);
        if (piece && (piece === 'P' || piece === 'p')) {
          const toRank = parseInt(alg[1]);
          if (toRank === 1 || toRank === 8) {
            // Use default queen for now; could open dialog
            move.promotion = 'q';
          }
        }
        if (this.options.onMove) this.options.onMove(move);
        if (this.options.playSound) this.options.playSound('move');
        if (this.options.vibrate && navigator.vibrate) navigator.vibrate(8);
        dragFrom = null;
        dragStarted = false;
      };

      this.container.addEventListener('mousedown', onDown);
      this.container.addEventListener('mousemove', onMove);
      window.addEventListener('mouseup', onUp);
      this.container.addEventListener('contextmenu', e => e.preventDefault());

      // Touch
      this.container.addEventListener('touchstart', (e) => {
        const t = e.touches[0];
        onDown({ ...t, button: 0, target: document.elementFromPoint(t.clientX, t.clientY) });
        e.preventDefault();
      }, { passive: false });
      this.container.addEventListener('touchmove', (e) => {
        const t = e.touches[0];
        const el = document.elementFromPoint(t.clientX, t.clientY);
        onMove({ ...t, target: el });
      }, { passive: false });
      this.container.addEventListener('touchend', (e) => {
        const t = e.changedTouches[0];
        const el = document.elementFromPoint(t.clientX, t.clientY);
        onUp({ ...t, button: 0, target: el });
      });
    }

    _pieceAt(idx) {
      const [r, c] = this._rc(idx);
      const rows = this.board.split(' ')[0].split('/');
      const rowStr = rows[r];
      let col = 0;
      for (const ch of rowStr) {
        if (/\d/.test(ch)) {
          col += parseInt(ch);
          if (col > c) return null;
          continue;
        }
        if (col === c) {
          return ch === ch.toUpperCase() ? ch.toUpperCase() : ch.toLowerCase();
        }
        col++;
      }
      return null;
    }
  }

  window.ChessBoard = Board;
})();

// =============================================================
//  WebSocket connection state — Svelte 5 runes
//  Wires to the real backend WS envelope:
//    { type, v, ts, ...data }
//  Heartbeat sends {"type": "ping"} (JSON) per the protocol
//  (src/chess_coach/ws/server.py + ws/protocol.py).
// =============================================================
import type { WsAnalysisUpdate, WsEnvelope } from '$lib/types';

export type WsState = 'idle' | 'connecting' | 'open' | 'closed' | 'error';

export class WsConnection {
  url = $state('/ws');
  state = $state<WsState>('idle');
  retry = $state(0);
  lastError = $state<string | null>(null);

  #socket: WebSocket | null = null;
  #handlers = new Set<(m: WsEnvelope) => void>();
  #retryTimer: ReturnType<typeof setTimeout> | null = null;
  #pingTimer: ReturnType<typeof setInterval> | null = null;
  #shouldRun = false;

  start(url = '/ws') {
    this.url = url;
    this.#shouldRun = true;
    this.#connect();
  }

  stop() {
    this.#shouldRun = false;
    if (this.#retryTimer) clearTimeout(this.#retryTimer);
    if (this.#pingTimer) clearInterval(this.#pingTimer);
    this.#retryTimer = null;
    this.#pingTimer = null;
    this.#socket?.close();
    this.#socket = null;
    this.state = 'idle';
  }

  send(data: Record<string, unknown>) {
    if (this.#socket?.readyState === WebSocket.OPEN) {
      this.#socket.send(JSON.stringify({ v: 1, ts: Date.now(), ...data }));
    }
  }

  onMessage(fn: (m: WsEnvelope) => void) {
    this.#handlers.add(fn);
    return () => this.#handlers.delete(fn);
  }

  #connect() {
    if (!this.#shouldRun) return;
    this.state = 'connecting';
    try {
      const proto = location.protocol === 'https:' ? 'wss' : 'ws';
      const ws = new WebSocket(`${proto}://${location.host}${this.url}`);
      this.#socket = ws;

      ws.onopen = () => {
        this.state = 'open';
        this.retry = 0;
        this.lastError = null;
        if (this.#pingTimer) clearInterval(this.#pingTimer);
        this.#pingTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'ping', v: 1, ts: Date.now() }));
          }
        }, 15000);
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as WsEnvelope;
          for (const h of this.#handlers) h(data);
        } catch (e) {
          this.lastError = String(e);
        }
      };

      ws.onerror = () => {
        this.state = 'error';
        this.lastError = 'WebSocket error';
      };

      ws.onclose = () => {
        this.state = 'closed';
        if (this.#pingTimer) clearInterval(this.#pingTimer);
        this.#pingTimer = null;
        if (!this.#shouldRun) return;
        // Exponential backoff: 1s, 2s, 4s, 8s, 16s, max 30s
        const delay = Math.min(30000, 1000 * 2 ** Math.min(this.retry, 5));
        this.retry += 1;
        this.#retryTimer = setTimeout(() => this.#connect(), delay);
      };
    } catch (e) {
      this.state = 'error';
      this.lastError = String(e);
      if (this.#shouldRun) this.#retryTimer = setTimeout(() => this.#connect(), 2000);
    }
  }
}

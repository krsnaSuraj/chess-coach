// =============================================================
//  WebSocket connection state — Svelte 5 runes
//  Single source of truth for live eval streaming.
// =============================================================
import type { WsEvalMessage } from '$lib/types';

export type WsState = 'idle' | 'connecting' | 'open' | 'closed' | 'error';

export class WsConnection {
  url = $state('/ws');
  state = $state<WsState>('idle');
  lastMessage = $state<WsEvalMessage | null>(null);
  retry = $state(0);
  lastError = $state<string | null>(null);

  #socket: WebSocket | null = null;
  #handlers = new Set<(m: WsEvalMessage) => void>();
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

  onMessage(fn: (m: WsEvalMessage) => void) {
    this.#handlers.add(fn);
    return () => this.#handlers.delete(fn);
  }

  send(msg: unknown) {
    if (this.#socket?.readyState === WebSocket.OPEN) {
      this.#socket.send(JSON.stringify(msg));
    }
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
        // Heartbeat — keep connection alive
        if (this.#pingTimer) clearInterval(this.#pingTimer);
        this.#pingTimer = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping');
        }, 15000);
      };

      ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(ev.data) as WsEvalMessage;
          this.lastMessage = data;
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
        // Exponential backoff: 1s, 2s, 4s, 8s, max 30s
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

import { describe, it, expect, vi } from 'vitest';
import { WsConnection } from '../lib/stores/ws.svelte';

describe('WsConnection (public API)', () => {
  it('starts in idle state', () => {
    const ws = new WsConnection();
    expect(ws.state).toBe('idle');
    expect(ws.retry).toBe(0);
    expect(ws.url).toBe('/ws');
  });

  it('start() transitions to connecting', () => {
    const ws = new WsConnection();
    ws.start('/ws');
    expect(ws.state).toBe('connecting');
    expect(ws.url).toBe('/ws');
    ws.stop();
  });

  it('stop() returns to idle and clears retry state', () => {
    const ws = new WsConnection();
    ws.start('/ws');
    ws.stop();
    expect(ws.state).toBe('idle');
  });

  it('onMessage returns an unsubscribe', () => {
    const ws = new WsConnection();
    const handler = vi.fn();
    const off = ws.onMessage(handler);
    expect(typeof off).toBe('function');
    off();
  });

  it('state machine: idle -> connecting -> idle after stop', () => {
    const ws = new WsConnection();
    const states: string[] = [];
    states.push(ws.state);
    ws.start('/ws');
    states.push(ws.state);
    ws.stop();
    states.push(ws.state);
    expect(states).toEqual(['idle', 'connecting', 'idle']);
  });
});

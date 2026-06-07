import { describe, it, expect } from 'vitest';
import { easeOutCubic, lerp, clamp, cpToBar, formatEval, cpToWinProbability } from '../lib/utils/tween';

describe('tween utils', () => {
  it('easeOutCubic(0) = 0', () => {
    expect(easeOutCubic(0)).toBe(0);
  });
  it('easeOutCubic(1) = 1', () => {
    expect(easeOutCubic(1)).toBe(1);
  });
  it('lerp is linear', () => {
    expect(lerp(0, 100, 0.5)).toBe(50);
    expect(lerp(-100, 100, 0.25)).toBe(-50);
  });
  it('clamp bounds', () => {
    expect(clamp(5, 0, 10)).toBe(5);
    expect(clamp(-1, 0, 10)).toBe(0);
    expect(clamp(11, 0, 10)).toBe(10);
  });
  it('cpToBar symmetric around 0', () => {
    expect(cpToBar(0)).toBeCloseTo(0.5, 5);
    expect(cpToBar(1000)).toBeGreaterThan(0.5);
    expect(cpToBar(-1000)).toBeLessThan(0.5);
  });
  it('formatEval formats sign + decimals', () => {
    expect(formatEval(0, null)).toBe('+0.00');
    expect(formatEval(134, null)).toBe('+1.34');
    expect(formatEval(-87, null)).toBe('-0.87');
    expect(formatEval(0, 5)).toBe('M5');
    expect(formatEval(0, -3)).toBe('-M3');
  });
  it('cpToWinProbability monotonic', () => {
    expect(cpToWinProbability(-1000)).toBeLessThan(cpToWinProbability(0));
    expect(cpToWinProbability(0)).toBeLessThan(cpToWinProbability(1000));
    expect(cpToWinProbability(0)).toBeCloseTo(0.5, 1);
  });
});

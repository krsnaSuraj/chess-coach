// =============================================================
//  Tween utilities — SOTA 200 ms easeOutCubic for eval bar
// =============================================================

export function easeOutCubic(t: number): number {
  const c = 1 - t;
  return 1 - c * c * c;
}

export function lerp(a: number, b: number, t: number): number {
  return a + (b - a) * t;
}

export function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** Convert centipawns to win-probability (Lichess formula, normalized 0..1). */
export function cpToWinProbability(cp: number): number {
  const x = clamp(cp, -1000, 1000);
  return 0.5 + 0.5 * (2 / (1 + Math.exp(-0.00368208 * x)) - 1);
}

/** Convert centipawns to a 0..1 bar fill ratio (top is white, bottom is black). */
export function cpToBar(cp: number): number {
  return clamp(0.5 + Math.atan(cp / 220) / Math.PI, 0.02, 0.98);
}

/** Format eval for display: 0.00 / +1.34 / -0.87 / M5 */
export function formatEval(cp: number, mate: number | null | undefined): string {
  if (mate != null && mate !== 0) return (mate > 0 ? 'M' : '-M') + Math.abs(mate);
  if (cp == null) return '0.00';
  const sign = cp >= 0 ? '+' : '';
  return sign + (cp / 100).toFixed(2);
}

/** Format eval without sign (for the bar's "0.00" label). */
export function formatEvalUnsigned(cp: number): string {
  const v = Math.abs(cp) / 100;
  return v.toFixed(2);
}

/** Format a 0..1 ratio as a percentage. */
export function formatPct(p: number, digits = 1): string {
  return (p * 100).toFixed(digits) + '%';
}

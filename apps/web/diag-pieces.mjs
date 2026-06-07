import { chromium } from '@playwright/test';
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
(async () => {
  const b = await chromium.launch({ headless: true });
  const p = await (await b.newContext({ viewport: { width: 1920, height: 1080 } })).newPage();
  await p.goto('http://127.0.0.1:8000/', { waitUntil: 'networkidle' });
  await wait(3000);

  // Get the first 3 pieces
  const pieceInfo = await p.evaluate(() => {
    const pieces = Array.from(document.querySelectorAll('piece'));
    return pieces.slice(0, 3).map((el) => {
      const cs = getComputedStyle(el);
      return {
        cssClass: el.className,
        width: cs.width,
        height: cs.height,
        backgroundImage: cs.backgroundImage,
        backgroundSize: cs.backgroundSize,
        transform: cs.transform,
        position: cs.position,
        display: cs.display,
        opacity: cs.opacity,
        visibility: cs.visibility,
        zIndex: cs.zIndex,
        top: cs.top,
        left: cs.left,
        rect: el.getBoundingClientRect()
      };
    });
  });
  console.log('First 3 pieces:', JSON.stringify(pieceInfo, null, 2));

  // Check the cg-board (parent) sizing
  const boardInfo = await p.evaluate(() => {
    const board = document.querySelector('cg-board');
    if (!board) return null;
    const cs = getComputedStyle(board);
    return {
      width: cs.width,
      height: cs.height,
      backgroundImage: cs.backgroundImage,
      backgroundSize: cs.backgroundSize,
      position: cs.position
    };
  });
  console.log('cg-board:', JSON.stringify(boardInfo, null, 2));

  // Check coordinates (8, 7, ..., A, B, ...) — are they showing because squares are visible?
  // Let me check the piece's own width
  const pieceRect = await p.evaluate(() => {
    const piece = document.querySelector('piece');
    if (!piece) return null;
    const r = piece.getBoundingClientRect();
    return { x: r.x, y: r.y, width: r.width, height: r.height };
  });
  console.log('First piece rect:', pieceRect);

  await b.close();
})();

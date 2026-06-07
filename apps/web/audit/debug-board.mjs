import { chromium } from '@playwright/test';
const b = await chromium.launch({ headless: true });
const p = await b.newPage();
const consoleMsgs = [];
p.on('console', m => consoleMsgs.push(`[${m.type()}] ${m.text()}`));
p.on('pageerror', e => consoleMsgs.push(`[pageerror] ${e.message}`));
await p.goto('http://127.0.0.1:5173/', { waitUntil: 'networkidle' });
await p.waitForTimeout(1500);
const data = await p.evaluate(() => {
  const host = document.querySelector('.board-host');
  const allCgBoards = document.querySelectorAll('cg-board');
  const allContainers = document.querySelectorAll('cg-container');
  const pieces = document.querySelectorAll('cg-board piece');
  const transforms = new Set();
  pieces.forEach(p => transforms.add(p.style.transform));
  const boardSizes = Array.from(allCgBoards).map(b => {
    const r = b.getBoundingClientRect();
    return { w: r.width, h: r.height };
  });
  return {
    hostSize: host ? { w: host.clientWidth, h: host.clientHeight } : null,
    boardCount: allCgBoards.length,
    containerCount: allContainers.length,
    pieceCount: pieces.length,
    boardSizes,
    uniqueTransforms: Array.from(transforms),
    containerComputed: allContainers[0] ? {
      width: window.getComputedStyle(allContainers[0]).width,
      height: window.getComputedStyle(allContainers[0]).height,
      position: window.getComputedStyle(allContainers[0]).position,
      display: window.getComputedStyle(allContainers[0]).display,
    } : null,
    boardComputed: allCgBoards[0] ? {
      width: window.getComputedStyle(allCgBoards[0]).width,
      height: window.getComputedStyle(allCgBoards[0]).height,
      position: window.getComputedStyle(allCgBoards[0]).position,
      display: window.getComputedStyle(allCgBoards[0]).display,
      bgImage: window.getComputedStyle(allCgBoards[0]).backgroundImage.slice(0, 80),
    } : null,
  };
});
console.log('=== BOARD STATE ===');
console.log(JSON.stringify(data, null, 2));
console.log('=== CONSOLE ===');
for (const m of consoleMsgs.slice(0, 20)) console.log(m);
await b.close();

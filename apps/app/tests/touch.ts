import type { Page } from "@playwright/test";

export type Pt = { x: number; y: number };
/** One real touch drag, so the card sees pointer events the way it does on a phone. */
export async function drag(page: Page, from: Pt, to: Pt) {
  const cdp = await page.context().newCDPSession(page);
  const at = (p: Pt) => [{ x: p.x, y: p.y, id: 1 }];
  await cdp.send("Input.dispatchTouchEvent", { type: "touchStart", touchPoints: at(from) });
  for (let i = 1; i <= 10; i++) {
    await page.waitForTimeout(20);
    await cdp.send("Input.dispatchTouchEvent", { type: "touchMove", touchPoints: at({ x: from.x + ((to.x - from.x) * i) / 10, y: from.y + ((to.y - from.y) * i) / 10 }) });
  }
  await cdp.send("Input.dispatchTouchEvent", { type: "touchEnd", touchPoints: [] });
  await cdp.detach();
}


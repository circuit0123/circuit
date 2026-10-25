import { expect, test, type Page } from "@playwright/test";
import { OFF, OFF_PATHS, ON, PATHS, THEMES } from "./support";

/**
 * The measurable "premium" rules from DESIGN.md §5 and §13 item 5, for the landing home page (apps/app/tests/premium.spec.ts is the
 * same idea for tab screens): one primary button, never a border AND a background on one element, 40px (phone) / 56px (desktop)
 * between sections, body lines under 600px, at most 5 font sizes, accent never on a button or headline and on at most 2 kinds of
 * element, no text cut off with an ellipsis. Failures are soft, so one run lists every broken rule.
 */
type Hit = { rule: string; element: string; detail: string };

async function scan(page: Page, wide: boolean): Promise<Hit[]> {
  return page.evaluate((wide) => {
    /* eslint-disable @typescript-eslint/no-explicit-any */
    const hits: any[] = [];
    const cls = (el: Element) => (typeof (el as any).className === "string" ? (el as any).className : (el.getAttribute("class") ?? ""));
    const describe = (el: Element) => `${el.tagName.toLowerCase()}${cls(el) ? "." + cls(el).split(/\s+/).slice(0, 3).join(".") : ""} "${(el.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 28)}"`;
    const hit = (rule: string, el: Element | null, detail = "") => hits.push({ rule, element: el ? describe(el) : "(page)", detail });
    const shown = (el: Element) => {
      // The answer inside a closed <details> isn't on screen, though the browser still reports a box for it.
      const closed = el.closest("details:not([open])");
      if (closed && !el.closest("summary") && el !== closed) return false;
      const r = el.getBoundingClientRect();
      if (r.width < 2 || r.height < 2) return false;
      const s = getComputedStyle(el);
      return s.display !== "none" && s.visibility !== "hidden" && parseFloat(s.opacity) > 0;
    };
    const alpha = (c: string) => { const m = /rgba?\(([^)]+)\)/.exec(c); if (!m) return c === "transparent" ? 0 : 1; const p = m[1].split(/[ ,/]+/).filter(Boolean); return p.length > 3 ? parseFloat(p[3]) : 1; };
    const hasBg = (s: CSSStyleDeclaration) => alpha(s.backgroundColor) > 0.02 || s.backgroundImage !== "none";
    const hasBorder = (s: CSSStyleDeclaration) => (["Top", "Right", "Bottom", "Left"] as const).some((side) => parseFloat((s as any)[`border${side}Width`]) > 0 && (s as any)[`border${side}Style`] !== "none" && alpha((s as any)[`border${side}Color`]) > 0.02);
    const token = (name: string) => { const p = document.createElement("i"); p.style.color = `var(${name})`; document.body.append(p); const c = getComputedStyle(p).color; p.remove(); return c; };
    const PRIMARY = token("--primary");
    const ACCENT = token("--current");
    const everything = Array.from(document.body.querySelectorAll("*")).filter((el) => !el.closest("svg, script, style, noscript") && shown(el));

    // 1. one primary button
    const primaries = everything.filter((el) => el.matches("button, a, [role=button]") && getComputedStyle(el).backgroundColor === PRIMARY);
    primaries.slice(1).forEach((el) => hit("one-primary", el, `${primaries.length} primary buttons`));

    // 2. never a border AND a background on one element (the footer rule and FAQ hairlines have no fill)
    for (const el of everything) { const s = getComputedStyle(el); if (hasBorder(s) && hasBg(s)) hit("border+bg", el, "border and background together"); }

    // 3. text: line length (15-17px body), font sizes, ellipsis
    const sizes = new Set<number>();
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const t = n as Text; const p = t.parentElement;
      if (!p || !t.data.trim() || p.closest("svg, script, style, noscript") || !shown(p)) continue;
      const px = parseFloat(getComputedStyle(p).fontSize);
      sizes.add(Math.round(px * 10) / 10);
      if (px >= 15 && px <= 17) {
        const r = document.createRange(); r.selectNodeContents(t);
        const widest = Math.max(0, ...Array.from(r.getClientRects()).map((q) => q.width));
        if (widest > 600) hit("line-length", p, `a line is ${Math.round(widest)}px wide`);
      }
      if (/(…|\.\.\.)\s*$/.test(t.data.trim())) hit("truncated", p, "text ends in an ellipsis");
    }
    for (const el of everything) {
      const s = getComputedStyle(el);
      if (s.textOverflow === "ellipsis" && el.scrollWidth > el.clientWidth + 1) hit("truncated", el, "cut off with an ellipsis");
      const clamp = (s as any).webkitLineClamp;
      if (clamp && clamp !== "none" && el.scrollHeight > el.clientHeight + 1) hit("truncated", el, `clamped to ${clamp} lines`);
    }
    if (sizes.size > 5) hit("font-sizes", null, `${sizes.size} sizes: ${[...sizes].sort((a, b) => a - b).join(", ")}px (max 5)`);

    // 4. accent: at most 2 kinds of element, never on a button or a headline (in the light theme accent and primary are the same green, so a primary fill is not counted as accent)
    const kinds = new Set<string>();
    for (const el of everything) {
      const s = getComputedStyle(el);
      const ownText = Array.from(el.childNodes).some((c) => c.nodeType === 3 && (c as Text).data.trim());
      const usesAccent = (ownText && s.color === ACCENT) || (s.backgroundColor === ACCENT && ACCENT !== PRIMARY) || (hasBorder(s) && s.borderTopColor === ACCENT);
      if (!usesAccent) continue;
      kinds.add(`${el.tagName.toLowerCase()}.${cls(el)}`);
      if (el.closest("button, [role=button], a[href]")) hit("accent-on-button", el, "accent inside a button or link");
      if (el.closest("h1, h2, h3") || parseFloat(s.fontSize) >= 20) hit("accent-on-headline", el, "accent in a headline");
    }
    if (kinds.size > 2) hit("accent-kinds", null, `${kinds.size} kinds of element use the accent`);

    // 5. space between sections: from the last ink of one section to the first ink of the next
    const ink = (root: Element) => {
      let top = Infinity, bottom = -Infinity;
      const add = (r: DOMRect) => { if (r.width >= 1 && r.height >= 1) { top = Math.min(top, r.top + scrollY); bottom = Math.max(bottom, r.bottom + scrollY); } };
      const w = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (let n = w.nextNode(); n; n = w.nextNode()) { const t = n as Text; if (!t.data.trim() || !t.parentElement || !shown(t.parentElement)) continue; const r = document.createRange(); r.selectNodeContents(t); add(r.getBoundingClientRect()); }
      for (const el of Array.from(root.querySelectorAll("img, video, picture, [role=img]"))) if (shown(el)) add(el.getBoundingClientRect());
      for (const el of Array.from(root.querySelectorAll("*"))) { if (el.closest("svg") || !shown(el)) continue; const s = getComputedStyle(el); if (hasBg(s) && el.getBoundingClientRect().height > 40) add(el.getBoundingClientRect()); }
      return { top, bottom };
    };
    const blocks = Array.from(document.querySelectorAll("main > section")).filter(shown).map((s) => ({ s, ...ink(s) }));
    const need = wide ? 56 : 40;
    for (let i = 1; i < blocks.length; i++) {
      const gap = Math.round(blocks[i].top - blocks[i - 1].bottom);
      if (gap < need) hit("section-gap", blocks[i].s, `${gap}px above this section (need ${need}px)`);
    }
    return hits;
  }, wide);
}

const CASES = [...PATHS.map((path) => ({ base: ON, path, name: path })), ...OFF_PATHS.map((path) => ({ base: OFF, path, name: `${path} (flag off)` }))];

for (const c of CASES) {
  for (const theme of THEMES) {
    test(`premium rules, ${c.name}, ${theme}`, async ({ page }, info) => {
      await page.emulateMedia({ colorScheme: theme, reducedMotion: "reduce" });
      await page.goto(c.base + c.path);
      await page.waitForLoadState("networkidle");
      const wide = info.project.name === "desktop";
      const hits = await scan(page, wide);
      for (const h of hits) expect.soft(false, `${c.name} | ${theme} | ${wide ? 1280 : 375} | ${h.rule} | ${h.element} | ${h.detail}`).toBe(true);
      expect(hits.length).toBe(0);
    });
  }
}

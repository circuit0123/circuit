import { expect, test, type Page } from "@playwright/test";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { inBothThemes, isPhone, signInAs } from "../e2e/helpers";

/**
 * The "premium" checks from DESIGN.md §13 item 5 (rules in §5 "Breathing room"). Every tab screen, at 375px and 1280px, in both themes:
 *   one primary button · no border AND background on a feed item · section gaps (40px phone / 56px desktop) · body lines under 600px ·
 *   at most 4 font sizes · accent on at most 2 kinds of element and never on a button · no mid-sentence truncation.
 * Three more rules from §5/§3 that can be measured are checked too: a Large title that sits 8px above the first block, at most 3 blocks
 * before the first scroll on a phone, and the desktop rail (one rail, max 340px, 48px from the column).
 *
 * Needs `make dev` (API + app). Failures are soft, so one run lists every broken rule. The list is also written to
 * screenshots/premium/report/<project>-<screen>.json. PREMIUM_SHOTS=before|after also saves screenshots to screenshots/premium/<screen>/.
 */
const OUT = join(__dirname, "../../../screenshots/premium");
const SCREENS = [
  { id: "home", path: "/" },
  { id: "discover", path: "/discover" },
  { id: "inbox", path: "/inbox" },
  { id: "profile", path: "/profile" },
] as const;

type Hit = { rule: string; element: string; detail: string };
type Scan = { hits: Hit[]; fontSizes: string[] };

test.beforeEach(async ({ context }) => { await signInAs(context, "ravi"); });

/** Runs inside the page: measures the active tab pane (and the desktop rail) and returns what breaks a rule. */
async function scan(page: Page, wide: boolean): Promise<Scan> {
  return page.evaluate(({ wide }) => {
    /* eslint-disable @typescript-eslint/no-explicit-any */
    const hits: any[] = [];
    const sizes = new Set<string>();
    const hit = (rule: string, el: Element | null, detail = "") => hits.push({ rule, element: el ? describe(el) : "(page)", detail });

    const cls = (el: Element) => (typeof (el as any).className === "string" ? (el as any).className : (el.getAttribute("class") ?? ""));
    function describe(el: Element): string {
      const label = el.getAttribute("aria-label") ?? el.getAttribute("role") ?? "";
      const text = (el.textContent ?? "").replace(/\s+/g, " ").trim().slice(0, 28);
      const c = cls(el).split(/\s+/).filter(Boolean).slice(0, 3).join(".");
      return `${el.tagName.toLowerCase()}${c ? "." + c : ""}${label ? `[${label}]` : ""}${text ? ` "${text}"` : ""}`;
    }
    const sy = window.scrollY;
    const rect = (el: Element) => el.getBoundingClientRect();
    const shown = (el: Element) => {
      const r = rect(el);
      if (r.width < 2 || r.height < 2) return false;
      const s = getComputedStyle(el);
      return s.display !== "none" && s.visibility !== "hidden" && parseFloat(s.opacity) > 0;
    };
    const alpha = (c: string) => {
      const m = /rgba?\(([^)]+)\)/.exec(c) ?? /color\(.*\/\s*([\d.]+)\)/.exec(c);
      if (!m) return c === "transparent" ? 0 : 1;
      const p = m[1].split(/[ ,\/]+/).filter(Boolean);
      return p.length > 3 ? parseFloat(p[3]) : 1;
    };
    const hasBg = (s: CSSStyleDeclaration) => alpha(s.backgroundColor) > 0.02 || s.backgroundImage !== "none";
    const hasBorder = (s: CSSStyleDeclaration) =>
      (["Top", "Right", "Bottom", "Left"] as const).some((side) => parseFloat((s as any)[`border${side}Width`]) > 0 && (s as any)[`border${side}Style`] !== "none" && alpha((s as any)[`border${side}Color`]) > 0.02);
    const token = (name: string) => {
      const p = document.createElement("i");
      p.style.color = `var(${name})`;
      document.body.append(p);
      const c = getComputedStyle(p).color;
      p.remove();
      return c;
    };
    const PRIMARY = token("--primary");
    const ACCENT = token("--current");

    // Where the screen lives: the visible tab pane, plus the desktop rail. Chrome (tab bar, left nav, dev banner) is not the screen.
    const pane = document.querySelector<HTMLElement>("[data-pane]:not([hidden])");
    const rail = document.querySelector<HTMLElement>('aside[aria-label="For you"]');
    const roots = [pane, rail].filter((x): x is HTMLElement => !!x && shown(x));
    if (!pane) { hit("setup", null, "no visible tab pane"); return { hits, fontSizes: [] }; }
    const inScope = (el: Element) => roots.some((r) => r.contains(el));
    const all = roots.flatMap((r) => [r, ...Array.from(r.querySelectorAll("*"))]).filter((el) => !el.closest("svg") || el.tagName.toLowerCase() === "svg");
    const everything = roots.flatMap((r) => [r, ...Array.from(r.querySelectorAll("*"))]);

    // ---- 1. one primary button ----
    const primaries = all.filter((el) => el.matches("button, a, [role=button]") && shown(el) && getComputedStyle(el).backgroundColor === PRIMARY);
    primaries.slice(1).forEach((el) => hit("one-primary", el, `${primaries.length} primary buttons on this screen`));

    // ---- 2. feed items: never a border AND a background on the same element ----
    const feedItems = Array.from(document.querySelectorAll('[data-feed-item], section[aria-label="Pulse"] [data-index], section[aria-label="Worth meeting"] li, section[aria-label="People you may know"] li')).filter(inScope);
    for (const item of feedItems) {
      for (const el of [item, ...Array.from(item.querySelectorAll("*"))]) {
        if (el.closest("svg") && el.tagName.toLowerCase() !== "svg") continue;
        const s = getComputedStyle(el);
        if (hasBorder(s) && hasBg(s) && shown(el)) hit("feed-border+bg", el, "border and background together");
      }
    }

    // ---- 3. text: line length, font sizes, truncation ----
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const texts: Text[] = [];
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const t = n as Text;
      const p = t.parentElement;
      if (p && (t.data ?? "").trim() && inScope(p) && !p.closest("svg, script, style, [data-dev]") && shown(p)) texts.push(t);
    }
    for (const t of texts) {
      const p = t.parentElement!;
      const s = getComputedStyle(p);
      sizes.add(`${Math.round(parseFloat(s.fontSize) * 10) / 10}`);
      const px = parseFloat(s.fontSize);
      if (px >= 15 && px <= 17) {
        const r = document.createRange();
        r.selectNodeContents(t);
        const widest = Math.max(0, ...Array.from(r.getClientRects()).map((q) => q.width));
        if (widest > 600) hit("line-length", p, `a line is ${Math.round(widest)}px wide`);
      }
      if (/(…|\.\.\.)\s*$/.test(t.data.trim())) hit("truncated", p, "text ends in an ellipsis");
    }
    for (const el of everything) {
      if (!shown(el) || el.closest("svg")) continue;
      const s = getComputedStyle(el);
      const words = (el.textContent ?? "").trim().split(/\s+/).filter(Boolean).length;
      if (words < 3) continue;
      const clamp = (s as any).webkitLineClamp;
      if (s.textOverflow === "ellipsis" && el.scrollWidth > el.clientWidth + 1) hit("truncated", el, `cut off with an ellipsis (${words} words)`);
      else if (clamp && clamp !== "none" && el.scrollHeight > el.clientHeight + 1) hit("truncated", el, `clamped to ${clamp} lines and cut (${words} words)`);
    }

    // ---- 4. accent: at most 2 kinds of element, never on a button or a headline ----
    type Use = { el: Element; how: string };
    const uses: Use[] = [];
    const liveClass = /(^|\s)([a-z-]+:)*(text|bg|border|ring|stroke|fill)-live(\/\d+)?(\s|$)/;
    for (const el of everything) {
      if (!shown(el)) continue;
      const s = getComputedStyle(el);
      const svgShape = !!el.closest("svg") && el.tagName.toLowerCase() !== "svg";
      const owner = svgShape ? ((el.closest("svg")!.parentElement as Element) ?? el) : el;
      const ownText = Array.from(el.childNodes).some((c) => c.nodeType === 3 && (c as Text).data.trim());
      if (ownText && !svgShape && s.color === ACCENT) uses.push({ el, how: "text" });
      else if (alpha(s.backgroundColor) > 0.02 && s.backgroundColor === ACCENT) uses.push({ el, how: "background" });
      else if (hasBorder(s) && s.borderTopColor === ACCENT) uses.push({ el, how: "border" });
      else if (svgShape && (s.stroke === ACCENT || s.fill === ACCENT) && !el.closest("defs")) uses.push({ el: owner, how: "icon" });
      else if (!svgShape && liveClass.test(cls(el))) uses.push({ el, how: "class" });
    }
    const seenEl = new Set<Element>();
    const kinds = new Map<string, Element>();
    for (const u of uses) {
      if (seenEl.has(u.el)) continue;
      seenEl.add(u.el);
      const kind = `${u.el.tagName.toLowerCase()}.${cls(u.el).split(/\s+/).filter(Boolean).sort().join(".")}`;
      if (!kinds.has(kind)) kinds.set(kind, u.el);
      const decoration = !!u.el.closest('[aria-hidden="true"]');
      const control = u.el.closest("button, [role=button], a[href]");
      if (control && !decoration) hit("accent-on-button", u.el, `accent ${u.how} inside ${describe(control)}`);
      const head = u.el.closest("h1, h2, h3");
      if (head || parseFloat(getComputedStyle(u.el).fontSize) >= 20) {
        if (!decoration || head) hit("accent-on-headline", u.el, `accent ${u.how} in a headline`);
      }
    }
    if (kinds.size > 2) hit("accent-kinds", null, `${kinds.size} kinds: ${Array.from(kinds.values()).map(describe).join(" | ")}`);

    // ---- 5. blocks: Large title, gaps between sections, blocks before the first scroll ----
    const ownPositioned = (el: Element) => ["sticky", "fixed"].includes(getComputedStyle(el).position);
    const flowChildren = (el: Element) => Array.from(el.children).filter((c) => shown(c) && !ownPositioned(c) && c.tagName !== "SCRIPT" && c.tagName !== "STYLE");
    const blocksOf = (root: Element) => {
      let node: Element = root;
      for (let i = 0; i < 6; i++) {
        const kids = flowChildren(node);
        if (kids.length !== 1) break;
        node = kids[0];
      }
      return flowChildren(node);
    };
    // The "ink" of a block: text, media and filled or bordered boxes, in page coordinates. Padding and margin both count as space.
    const ink = (block: Element) => {
      let top = Infinity, bottom = -Infinity;
      const add = (r: DOMRect) => { if (r.width >= 1 && r.height >= 1) { top = Math.min(top, r.top + sy); bottom = Math.max(bottom, r.bottom + sy); } };
      const w = document.createTreeWalker(block, NodeFilter.SHOW_TEXT);
      for (let n = w.nextNode(); n; n = w.nextNode()) {
        const t = n as Text;
        if (!t.data.trim() || !t.parentElement || !shown(t.parentElement)) continue;
        const r = document.createRange();
        r.selectNodeContents(t);
        r.getClientRects().length && add(r.getBoundingClientRect());
      }
      for (const el of [block, ...Array.from(block.querySelectorAll("*"))]) {
        if (!shown(el)) continue;
        const tag = el.tagName.toLowerCase();
        if (["img", "video", "canvas"].includes(tag) || tag === "svg") add(rect(el));
        else if (!el.closest("svg")) { const s = getComputedStyle(el); if ((hasBg(s) || hasBorder(s)) && !el.matches(".skeleton")) add(rect(el)); }
      }
      return { top, bottom };
    };

    for (const root of roots) {
      const blocks = blocksOf(root).filter((b) => !b.matches("[data-pane]"));
      const isMain = root === pane;
      const titleIdx = blocks.findIndex((b) => [b, ...Array.from(b.querySelectorAll("h1"))].some((x) => x.matches("h1") && shown(x)));
      if (isMain) {
        const h1 = Array.from(pane.querySelectorAll("h1")).find(shown);
        if (!h1) hit("large-title", pane, "no visible Large title (h1)");
        else if (parseFloat(getComputedStyle(h1).fontSize) < 34) hit("large-title", h1, `title is ${getComputedStyle(h1).fontSize}, not Large title (34px)`);
      }
      const inks = blocks.map((b) => ({ b, ...ink(b) })).filter((x) => isFinite(x.top));
      for (let i = 1; i < inks.length; i++) {
        const gap = Math.round(inks[i].top - inks[i - 1].bottom);
        const afterTitle = isMain && titleIdx >= 0 && blocks.indexOf(inks[i - 1].b) === titleIdx;
        if (afterTitle) { if (gap > 16) hit("title-gap", inks[i].b, `${gap}px under the title (8px expected, 16px allowed)`); continue; }
        const need = wide ? 56 : 40;
        if (gap < need) hit("section-gap", inks[i].b, `${gap}px above this block (need ${need}px)`);
      }
      if (isMain && !wide) {
        const above = inks.filter((x) => x.top - sy < window.innerHeight).length;
        if (above > 3) hit("above-the-fold", null, `${above} blocks before the first scroll (max 3)`);
      }
    }

    // ---- 6. desktop: one rail, max 340px, 48px from the column ----
    if (wide) {
      const main = document.querySelector("main");
      const asides = Array.from(document.querySelectorAll("aside")).filter((a) => shown(a) && !a.querySelector('nav[aria-label="Main"]'));
      if (asides.length > 1) hit("desktop-columns", null, `${asides.length} rails; one allowed`);
      if (main && rail && shown(rail)) {
        const w = Math.round(rect(rail).width);
        const gap = Math.round(rect(rail).left - rect(main).right);
        if (w > 341) hit("desktop-columns", rail, `rail is ${w}px wide (max 340)`);
        if (gap < 48) hit("desktop-columns", rail, `${gap}px between column and rail (48 needed)`);
        if (rect(main).width > 601) hit("desktop-columns", main, `centre column is ${Math.round(rect(main).width)}px (max 600)`);
      }
    }
    return { hits, fontSizes: Array.from(sizes) };
  }, { wide });
}

/** Scrolls the page in steps (the Pulse list is virtualised), scanning at each stop, then comes back to the top. */
async function scanWholePage(page: Page, wide: boolean) {
  const hits = new Map<string, Hit>();
  const sizes = new Set<string>();
  const take = (s: Scan) => {
    s.hits.forEach((h) => hits.set(`${h.rule}|${h.element}|${h.detail}`, h));
    s.fontSizes.forEach((f) => sizes.add(f));
  };
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(250);
  take(await scan(page, wide));
  const height = await page.evaluate(() => document.documentElement.scrollHeight);
  const step = 600;
  for (let y = step; y < Math.min(height, 7000); y += step) {
    await page.evaluate((to) => window.scrollTo(0, to), y);
    await page.waitForTimeout(160);
    take(await scan(page, wide));
  }
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.waitForTimeout(250);
  const out = Array.from(hits.values());
  // Rules that only make sense for the screen as a whole: they were measured at the top, where the page starts.
  if (sizes.size > 4) out.push({ rule: "font-sizes", element: "(screen)", detail: `${sizes.size} sizes: ${Array.from(sizes).sort((a, b) => +a - +b).join(", ")}px (max 4)` });
  return out;
}

for (const screen of SCREENS) {
  test(`premium: ${screen.id}`, async ({ page }, info) => {
    const width = isPhone(info) ? 375 : 1280;
    await page.goto(screen.path);
    await expect(page.locator("[data-pane]:not([hidden])")).toBeVisible();
    if (screen.id === "home") {
      await expect(page.getByRole("list", { name: "Live wire" })).toBeVisible();
      // Opening Home marks Pulse as seen, so a second run starts at "You're caught up": ask for the earlier items.
      const earlier = page.getByRole("button", { name: "See earlier this week" });
      await expect(earlier.or(page.locator('section[aria-label="Pulse"] article').first())).toBeVisible();
      if (await earlier.count()) await earlier.click();
      await expect(page.locator('section[aria-label="Pulse"] article').first()).toBeVisible();
    }
    await page.waitForLoadState("networkidle");
    await page.waitForTimeout(700);

    const rows: Array<Hit & { screen: string; width: number; theme: string }> = [];
    await inBothThemes(page, async (theme) => {
      await page.waitForTimeout(250);
      for (const h of await scanWholePage(page, width >= 1024)) rows.push({ screen: screen.id, width, theme, ...h });
      const tag = process.env.PREMIUM_SHOTS;
      if (tag) {
        const dir = join(OUT, screen.id);
        mkdirSync(dir, { recursive: true });
        await page.screenshot({ path: join(dir, `${tag}-${width}-${theme}.png`) });
      }
    });

    mkdirSync(join(OUT, "report"), { recursive: true });
    writeFileSync(join(OUT, "report", `${info.project.name}-${screen.id}.json`), JSON.stringify(rows, null, 2));
    for (const r of rows) expect.soft(false, `${r.screen} | ${r.width} | ${r.theme} | ${r.rule} | ${r.element} | ${r.detail}`).toBe(true);
  });
}

// Renders a docs/design-reference/*.dc.html file in Chromium with a minimal stand-in for its missing support.js
// (sc-for, sc-if, {{path}} in text and attributes), so it can be screenshotted next to the real screen.
// Usage: node screenshots/f3/ref-render.mjs <Name> <width> <height> <out.png> [state-json]
import { chromium } from "/home/klk/circuit/apps/app/node_modules/@playwright/test/index.mjs";
import { readFileSync } from "node:fs";

const [name, w, h, out, stateJson] = process.argv.slice(2);
const file = `/home/klk/circuit/docs/design-reference/${name}.dc.html`;
let html = readFileSync(file, "utf8").replace('<script src="./support.js"></script>', "");
const state = stateJson ? JSON.parse(stateJson) : null;

const engine = `
(function () {
  const get = (scope, path) => path.trim().split(".").reduce((o, k) => (o == null ? o : o[k]), scope);
  const fill = (s, scope) => s.replace(/\\{\\{([^}]+)\\}\\}/g, (_, p) => { const v = get(scope, p); return typeof v === "function" ? "" : v == null ? "" : v; });
  function walk(node, scope) {
    if (node.nodeType === 3) { node.nodeValue = fill(node.nodeValue, scope); return; }
    if (node.nodeType !== 1) return;
    const tag = node.tagName.toLowerCase();
    if (tag === "sc-if") {
      const v = get(scope, node.getAttribute("value").replace(/[{}]/g, ""));
      const kids = [...node.childNodes];
      if (v) { kids.forEach((k) => { node.parentNode.insertBefore(k, node); walk(k, scope); }); }
      node.remove();
      return;
    }
    if (tag === "sc-for") {
      const list = get(scope, node.getAttribute("list").replace(/[{}]/g, "")) || [];
      const as = node.getAttribute("as");
      const tpl = [...node.childNodes];
      list.forEach((item) => {
        tpl.forEach((t) => { const c = t.cloneNode(true); node.parentNode.insertBefore(c, node); walk(c, { ...scope, [as]: item }); });
      });
      node.remove();
      return;
    }
    for (const a of [...node.attributes]) { if (a.name.startsWith("on")) node.removeAttribute(a.name); else a.value = fill(a.value, scope); }
    [...node.childNodes].forEach((c) => walk(c, scope));
  }
  window.__render = (vals) => walk(document.querySelector("x-dc"), vals);
  window.DCLogic = class { constructor(props) { this.props = props || {}; this.state = {}; } setState(s) { Object.assign(this.state, s); } };
})();
`;
html = html.replace("<script type=\"text/x-dc\"", `<script>${engine}</script><script type="text/x-dc"`);

const b = await chromium.launch();
const ctx = await b.newContext({ viewport: { width: +w, height: +h }, reducedMotion: "reduce" });
const p = await ctx.newPage();
await p.route("**/fonts.googleapis.com/**", (r) => r.abort());
await p.setContent(html, { waitUntil: "load" });
await p.evaluate((st) => {
  const src = document.querySelector("script[data-dc-script]").textContent;
  const C = new Function(`${src}; return Component;`)();
  const c = new C({});
  if (st) Object.assign(c.state, st);
  window.__render(c.renderVals());
}, state);
await p.screenshot({ path: out, fullPage: false });
await b.close();

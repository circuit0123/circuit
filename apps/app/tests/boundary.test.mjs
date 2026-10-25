// The architecture rule (CLAUDE.md "Frontend architecture"): only src/data talks to the backend. Screens, components and packages/ui never
// import the API client, Supabase or call fetch. This lints sample code as if it lived in each place and checks the rule bites, and only there.
// Run with: node --test tests/boundary.test.mjs   (make test-web runs it)
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { ESLint } from "eslint";

const app = fileURLToPath(new URL("..", import.meta.url));
const ui = fileURLToPath(new URL("../../../packages/ui", import.meta.url));

const bad = {
  "the API client": `import { createApi } from "@circuit/api-client";\nexport const x = createApi;\n`,
  "the API client's types too (a screen has no business with them)": `import type { paths } from "@circuit/api-client";\nexport type X = paths;\n`,
  "Supabase": `import { createClient } from "@supabase/supabase-js";\nexport const x = createClient;\n`,
  "openapi-fetch": `import createClient from "openapi-fetch";\nexport const x = createClient;\n`,
  "fetch": `export const load = () => fetch("/api/me");\n`,
  "window.fetch": `export const load = () => window.fetch("/api/me");\n`,
};

async function messages(cwd, filePath, code) {
  const eslint = new ESLint({ cwd });
  const [r] = await eslint.lintText(code, { filePath });
  return r.messages.filter((m) => m.severity === 2).map((m) => `${m.ruleId}: ${m.message}`);
}

for (const [what, code] of Object.entries(bad)) {
  test(`a screen importing ${what} is an error`, async () => {
    const found = await messages(app, `${app}/src/components/Bad.tsx`, code);
    assert.ok(found.length > 0, `expected an error for ${what}, got none`);
  });

  test(`packages/ui importing ${what} is an error`, async () => {
    const found = await messages(ui, `${ui}/src/Bad.tsx`, code);
    assert.ok(found.length > 0, `expected an error for ${what}, got none`);
  });

  test(`src/data may use ${what}`, async () => {
    const found = await messages(app, `${app}/src/data/ok.ts`, code);
    assert.deepEqual(found.filter((f) => f.startsWith("no-restricted")), []);
  });
}

test("a screen may use the data layer", async () => {
  const found = await messages(app, `${app}/src/components/Good.tsx`, `import { useMe } from "@/data";\nexport const x = useMe;\n`);
  assert.deepEqual(found.filter((f) => f.startsWith("no-restricted")), []);
});

test("a screen cannot reach into the data layer's internals", async () => {
  const found = await messages(app, `${app}/src/components/Bad.tsx`, `import { api } from "@/data/client";\nexport const x = api;\n`);
  assert.ok(found.length > 0);
});

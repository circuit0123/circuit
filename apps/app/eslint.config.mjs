import next from "eslint-config-next";

const message = "Screens and components never talk to the backend. Use a hook from @/data (CLAUDE.md: Frontend architecture).";

export default [
  ...next,
  { ignores: [".next/**", "e2e/**", "playwright-report/**", "test-results/**"] },
  // Straight apostrophes in plain-language copy ("You're caught up.") are intended.
  { rules: { "react/no-unescaped-entities": "off" } },
  // Only src/data may import the API client or Supabase, or call fetch.
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: ["src/data/**"],
    rules: {
      "no-restricted-imports": ["error", { patterns: [
        { group: ["@circuit/api-client", "@circuit/api-client/*", "@supabase/*", "openapi-fetch"], message },
        { group: ["**/data/client", "**/data/supabase", "**/data/session"], message: "Import from @/data, not from its internals." },
      ] }],
      "no-restricted-globals": ["error", { name: "fetch", message }],
      "no-restricted-properties": ["error", { object: "window", property: "fetch", message }],
    },
  },
];

import type { NextConfig } from "next";

const config: NextConfig = {
  // The Playwright sign-in tests run a second dev server with stubbed Supabase keys; it needs its own build folder.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  devIndicators: false,
  transpilePackages: ["@circuit/ui", "@circuit/api-client"],
  turbopack: {
    // Mock mode (`make mock`) imports "msw/browser", which has no Node entry. The server pass gets an empty stand-in.
    resolveAlias: { "msw/browser": { browser: "./node_modules/msw/lib/browser/index.js", default: "./src/data/mocks/empty.ts" } },
  },
};
export default config;

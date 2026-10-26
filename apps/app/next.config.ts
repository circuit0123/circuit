import type { NextConfig } from "next";

// One Vercel project serves landing at / and this app under a prefix (vercel.json): set NEXT_PUBLIC_BASE_PATH=/app there. Empty everywhere else.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH ?? "";

const config: NextConfig = {
  ...(basePath ? { basePath } : {}),
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

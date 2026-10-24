import type { NextConfig } from "next";

const config: NextConfig = {
  // The Playwright sign-in tests run a second dev server with stubbed Supabase keys; it needs its own build folder.
  distDir: process.env.NEXT_DIST_DIR || ".next",
  devIndicators: false,
  transpilePackages: ["@circuit/ui", "@circuit/api-client"],
};
export default config;

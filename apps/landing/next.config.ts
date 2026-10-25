import type { NextConfig } from "next";
import { PHASE_DEVELOPMENT_SERVER } from "next/constants";

// No hard-coded domains (PRODUCTION.md §2a): every URL comes from the environment. Local defaults apply to `next dev` only;
// a production build without them fails here instead of shipping links to nowhere.
const URLS = {
  NEXT_PUBLIC_APP_URL: "http://localhost:3000",
  NEXT_PUBLIC_LANDING_URL: "http://localhost:3001",
  NEXT_PUBLIC_API_URL: "http://localhost:8000",
} as const;

export default function config(phase: string): NextConfig {
  const dev = phase === PHASE_DEVELOPMENT_SERVER;
  const missing = Object.keys(URLS).filter((k) => !process.env[k]);
  if (!dev && missing.length) throw new Error(`Missing build-time variables: ${missing.join(", ")} (see .env.example)`);
  return {
    output: "export",
    trailingSlash: true, // /privacy/index.html, so any static host (and `pnpm start`) serves it
    images: { unoptimized: true },
    transpilePackages: ["@circuit/ui"],
    // The tests build twice (feature flags on and off) into separate folders; normal builds use the default `out/`.
    ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
    env: dev ? Object.fromEntries(missing.map((k) => [k, URLS[k as keyof typeof URLS]])) : {},
  };
}

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
  const mode = process.env.NEXT_PUBLIC_LAUNCH_MODE || "live";
  if (mode !== "live" && mode !== "waitlist") throw new Error(`NEXT_PUBLIC_LAUNCH_MODE must be "waitlist" or "live", got "${mode}" (see .env.example)`);
  if (mode === "waitlist") {
    // Pre-launch: calls to action open the external form, so it must be a real absolute URL; the app is never linked.
    let ok = false;
    try { ok = /^https?:$/.test(new URL(process.env.NEXT_PUBLIC_WAITLIST_URL ?? "").protocol); } catch {}
    if (!ok) throw new Error("NEXT_PUBLIC_LAUNCH_MODE=waitlist needs NEXT_PUBLIC_WAITLIST_URL to be an absolute http(s) URL (see .env.example)");
  }
  const required = mode === "waitlist" ? Object.keys(URLS).filter((k) => k !== "NEXT_PUBLIC_APP_URL") : Object.keys(URLS);
  const missing = Object.keys(URLS).filter((k) => !process.env[k]);
  const missingRequired = missing.filter((k) => required.includes(k));
  if (!dev && missingRequired.length) throw new Error(`Missing build-time variables: ${missingRequired.join(", ")} (see .env.example)`);
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

/** All URLs and flags come from config (PRODUCTION.md §2a). Nothing is hard-coded. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
/** Path prefix the app is served under ("" or e.g. "/app"); the same value next.config.ts passes to Next as basePath. */
export const BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH ?? "";
export const APP_ENV = process.env.NEXT_PUBLIC_ENV ?? "dev";
export const SHOW_DEV_TOOLS = APP_ENV === "dev" || APP_ENV === "demo";
/** Public marketing site: where the Terms and Privacy Policy live. */
export const LANDING_URL = process.env.NEXT_PUBLIC_LANDING_URL ?? "";
/** Map tiles for MapLibre (CLAUDE.md: OpenStreetMap tiles). Raster XYZ template; set NEXT_PUBLIC_MAP_TILES_URL to use another tile server. */
export const MAP_TILES_URL = process.env.NEXT_PUBLIC_MAP_TILES_URL || "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
export const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION || "dev";

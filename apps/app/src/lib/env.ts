/** All URLs and flags come from config (PRODUCTION.md §2a). Nothing is hard-coded. */
export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "";
export const APP_ENV = process.env.NEXT_PUBLIC_ENV ?? "dev";
export const SHOW_DEV_TOOLS = APP_ENV === "dev" || APP_ENV === "demo";
/** Public marketing site: where the Terms and Privacy Policy live. */
export const LANDING_URL = process.env.NEXT_PUBLIC_LANDING_URL ?? "";

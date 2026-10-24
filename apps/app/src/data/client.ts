/**
 * The only place that creates the API client. Everything else in the app reaches the
 * backend through the hooks in this folder (CLAUDE.md "Frontend architecture"); an ESLint
 * rule stops screens and components importing the client, Supabase or fetch.
 */
import { ApiError, createApi, unwrap } from "@circuit/api-client";
import { API_URL } from "@/lib/env";

export { ApiError, unwrap };

const DEMO_KEY = "circuit.token";

/** The token the next request will carry. Set by the session provider; read synchronously by the client. */
let current: string | null = null;
export const setCurrentToken = (t: string | null) => { current = t; };

export function getStoredDemoToken(): string | null {
  try { return localStorage.getItem(DEMO_KEY); } catch { return null; }
}
export function setStoredDemoToken(t: string | null) {
  try { if (t) localStorage.setItem(DEMO_KEY, t); else localStorage.removeItem(DEMO_KEY); } catch { /* private mode: stay signed out */ }
}

export const api = createApi({ baseUrl: API_URL, getToken: () => current });

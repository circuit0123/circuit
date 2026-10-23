import { createApi, unwrap } from "@circuit/api-client";

const KEY = "circuit.token";

export function getStoredToken(): string | null {
  try { return localStorage.getItem(KEY); } catch { return null; }
}
export function setStoredToken(t: string | null) {
  try { if (t) localStorage.setItem(KEY, t); else localStorage.removeItem(KEY); } catch { /* private mode: stay signed out */ }
}

export const api = createApi({
  baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "",
  getToken: getStoredToken,
});
export { unwrap };

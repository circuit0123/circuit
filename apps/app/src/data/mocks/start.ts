import { setStoredDemoToken, getStoredDemoToken } from "../client";
import { handlers } from "./handlers";

let started: Promise<void> | null = null;

/**
 * Starts the mock worker and signs in as the mock member, so the app opens straight on Home. Called once before the first request;
 * calling it again (React runs effects twice in development) returns the same promise instead of patching WebSocket a second time.
 */
export function startMocks(): Promise<void> {
  started ??= (async () => {
    const { setupWorker } = await import("msw/browser");
    await setupWorker(...handlers).start({ onUnhandledFrame: "bypass", quiet: true });
    if (!getStoredDemoToken()) setStoredDemoToken("mock-token");
  })();
  return started;
}

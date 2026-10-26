/**
 * Mock Realtime (mock mode only): an in-memory stand-in for Supabase private Broadcast channels. Mock handlers `emit` on the same
 * topics and events the backend uses (`circuit:<id>` / `status`, `conversation:<id>` / `message`); `useChannel` listens here instead of
 * Supabase. Mock Service Worker runs handlers in the page, so both sides share this module.
 */
type Listener = (payload: Record<string, unknown>) => void;
const listeners = new Map<string, Set<Listener>>();
const keyOf = (topic: string, event: string) => `${topic}|${event}`;

export function on(topic: string, event: string, fn: Listener): () => void {
  const k = keyOf(topic, event);
  if (!listeners.has(k)) listeners.set(k, new Set());
  listeners.get(k)!.add(fn);
  return () => { listeners.get(k)?.delete(fn); };
}

export function emit(topic: string, event: string, payload: Record<string, unknown>) {
  listeners.get(keyOf(topic, event))?.forEach((fn) => fn(payload));
}

"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { SHOW_DEV_TOOLS } from "@/lib/env";
import { getStoredDemoToken, setCurrentToken, setStoredDemoToken } from "./client";
import { getSupabase } from "./supabase";
import type { Session as Session_ } from "@supabase/supabase-js";

function identityOf(s: Session_): Identity {
  const meta = (s.user.user_metadata ?? {}) as Record<string, unknown>;
  const name = typeof meta.full_name === "string" ? meta.full_name : typeof meta.name === "string" ? meta.name : "";
  return { email: s.user.email ?? "", name: name.trim() };
}

export type SessionSource = "demo" | "supabase";
/** What the sign-in provider told us about the person. Only used to prefill the name step and the waitlist; the API never trusts it. */
export type Identity = { email: string; name: string };
type Session = {
  ready: boolean;
  token: string | null;
  source: SessionSource | null;
  identity: Identity | null;
  /** Dev and demo only: sign in as a persona. */
  signInDemo: (token: string) => void;
  signOut: () => Promise<void>;
};

const Ctx = createContext<Session>({ ready: false, token: null, source: null, identity: null, signInDemo: () => {}, signOut: async () => {} });
export const useSession = () => useContext(Ctx);

/** Holds who is signed in. A persona token (dev/demo) or a Supabase session; the API client reads it through setCurrentToken. */
export function SessionProvider({ children, onChange }: { children: React.ReactNode; onChange: () => void }) {
  const [state, setState] = useState<{ ready: boolean; token: string | null; source: SessionSource | null; identity: Identity | null }>({ ready: false, token: null, source: null, identity: null });

  const had = useRef(false);
  const apply = useCallback((token: string | null, source: SessionSource | null, identity: Identity | null = null) => {
    // Someone signed in or out (not just a token refresh): forget everything cached for the last person.
    if (had.current !== !!token) { had.current = !!token; onChange(); }
    setCurrentToken(token);
    setState((s) => (s.token === token && s.ready ? s : { ready: true, token, source, identity }));
  }, [onChange]);

  // The saved token lives in browser storage, which the server render cannot see, so it is read after hydration.
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const demo = SHOW_DEV_TOOLS ? getStoredDemoToken() : null;
    if (demo) { apply(demo, "demo"); return; }
    const sb = getSupabase();
    if (!sb) { apply(null, null); return; }
    const from = (session: Session_ | null) => apply(session?.access_token ?? null, session ? "supabase" : null, session ? identityOf(session) : null);
    sb.auth.getSession().then(({ data }) => from(data.session));
    const { data: sub } = sb.auth.onAuthStateChange((_event, session) => from(session));
    return () => sub.subscription.unsubscribe();
  }, [apply]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const signInDemo = useCallback((t: string) => { onChange(); setStoredDemoToken(t); apply(t, "demo"); }, [apply, onChange]);
  const signOut = useCallback(async () => {
    setStoredDemoToken(null);
    try { await getSupabase()?.auth.signOut(); } catch { /* already signed out */ }
    apply(null, null);
  }, [apply]);

  const value = useMemo(() => ({ ...state, signInDemo, signOut }), [state, signInDemo, signOut]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

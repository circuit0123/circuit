"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ToastProvider } from "@circuit/ui";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { getStoredToken, setStoredToken } from "@/lib/api";

type Session = { ready: boolean; token: string | null; signIn: (t: string) => void; signOut: () => void };
const SessionCtx = createContext<Session>({ ready: false, token: null, signIn: () => {}, signOut: () => {} });
export const useSession = () => useContext(SessionCtx);

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: { queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false } } }));
  const [token, setToken] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  useEffect(() => {
    // localStorage only exists in the browser, so the token is read after hydration.
    /* eslint-disable react-hooks/set-state-in-effect */
    setToken(getStoredToken());
    setReady(true);
    /* eslint-enable react-hooks/set-state-in-effect */
    try {
      const t = localStorage.getItem("circuit.theme");
      if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
    } catch { /* system theme */ }
  }, []);
  const signIn = useCallback((t: string) => { client.clear(); setStoredToken(t); setToken(t); }, [client]);
  const signOut = useCallback(() => { client.clear(); setStoredToken(null); setToken(null); }, [client]);
  const session = useMemo(() => ({ ready, token, signIn, signOut }), [ready, token, signIn, signOut]);
  return (
    <SessionCtx.Provider value={session}>
      <QueryClientProvider client={client}>
        <ToastProvider>{children}</ToastProvider>
      </QueryClientProvider>
    </SessionCtx.Provider>
  );
}

"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { problemOf } from "./errors";
import { MOCK } from "./mocks/config";
import { SessionProvider, useSession } from "./session";

/** Set by SignedOutWatcher; called when the API says the session is over. */
let onSignedOut: () => void = () => {};

function SignedOutWatcher({ children }: { children: React.ReactNode }) {
  const { signOut } = useSession();
  useEffect(() => {
    onSignedOut = () => { void signOut(); };
    return () => { onSignedOut = () => {}; };
  }, [signOut]);
  return <>{children}</>;
}

/** In mock mode nothing may call the API until the mock worker is up. The mock code is only loaded then. */
function MockGate({ children }: { children: React.ReactNode }) {
  const [ready, setReady] = useState(!MOCK);
  useEffect(() => {
    if (!MOCK) return;
    void import("./mocks/start").then((m) => m.startMocks()).then(() => setReady(true));
  }, []);
  return ready ? <>{children}</> : null;
}

/**
 * The one query client. Error mapping lives here, once: the session ending signs the person out; "consent needed" and "beta access
 * needed" refetch who they are, so the Gate moves them to the right screen; a network failure is not retried (the screen shows
 * its error state); anything unexpected is retried once.
 */
function makeClient() {
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({ onError: (e) => react(e) }),
    mutationCache: new MutationCache({ onError: (e) => react(e) }),
    defaultOptions: { queries: { staleTime: 30_000, retry: (n, e) => problemOf(e).kind === "unknown" && n < 1, refetchOnWindowFocus: false } },
  });
  function react(e: unknown) {
    const kind = problemOf(e).kind;
    if (kind === "signed_out") onSignedOut();
    else if (kind === "consent" || kind === "beta") void client.invalidateQueries({ predicate: (q) => q.queryKey[0] === "me" || q.queryKey[1] === "config" });
  }
  return client;
}

export function DataProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(makeClient);
  const clear = useCallback(() => client.clear(), [client]);
  return (
    <MockGate>
      <SessionProvider onChange={clear}>
        <QueryClientProvider client={client}>
          <SignedOutWatcher>{children}</SignedOutWatcher>
        </QueryClientProvider>
      </SessionProvider>
    </MockGate>
  );
}

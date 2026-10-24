"use client";

import { MutationCache, QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { problemOf } from "./errors";
import { SessionProvider, useSession } from "./session";

/** Set by SignedOutWatcher; called when the API says the session is over. */
let onSignedOut: () => void = () => {};
const check = (e: unknown) => { if (problemOf(e).kind === "signed_out") onSignedOut(); };

function SignedOutWatcher({ children }: { children: React.ReactNode }) {
  const { signOut } = useSession();
  useEffect(() => {
    onSignedOut = () => { void signOut(); };
    return () => { onSignedOut = () => {}; };
  }, [signOut]);
  return <>{children}</>;
}

export function DataProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        queryCache: new QueryCache({ onError: check }),
        mutationCache: new MutationCache({ onError: check }),
        defaultOptions: { queries: { staleTime: 30_000, retry: (n, e) => problemOf(e).kind === "unknown" && n < 1, refetchOnWindowFocus: false } },
      }),
  );
  const clear = useCallback(() => client.clear(), [client]);
  return (
    <SessionProvider onChange={clear}>
      <QueryClientProvider client={client}>
        <SignedOutWatcher>{children}</SignedOutWatcher>
      </QueryClientProvider>
    </SessionProvider>
  );
}

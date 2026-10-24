"use client";

import { Button, Skeleton } from "@circuit/ui";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useSession } from "@/data";

const GIVE_UP_MS = 10_000;

/** Where Google sends people back to. The sign-in library finishes the exchange; this waits for the session, then goes Home. */
export function AuthCallback() {
  const { token } = useSession();
  const router = useRouter();
  const params = useSearchParams();
  const [late, setLate] = useState(false);
  const failed = params.has("error") || params.has("error_description") || late;

  useEffect(() => { if (token) router.replace("/"); }, [token, router]);
  useEffect(() => {
    const t = setTimeout(() => setLate(true), GIVE_UP_MS);
    return () => clearTimeout(t);
  }, []);

  return (
    <main className="mx-auto flex min-h-dvh w-full max-w-[440px] flex-col justify-center gap-4 px-4 py-12">
      {failed && !token ? (
        <>
          <h1 className="t-title2">Couldn't sign you in</h1>
          <p className="t-body text-text-muted">That didn't work. Go back and try again, or use email instead.</p>
          <Button variant="primary" className="w-full" onClick={() => router.replace("/")}>Back to sign-in</Button>
        </>
      ) : (
        <>
          <h1 className="t-title2">Signing you in</h1>
          <Skeleton className="h-4 w-2/3" />
        </>
      )}
    </main>
  );
}

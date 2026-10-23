"use client";

import { Button } from "@circuit/ui";
import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/lib/api";
import { SHOW_DEV_TOOLS } from "@/lib/env";
import { useSession } from "./Providers";
import { roleLabel } from "@/lib/format";

/** Supabase sign-in (Google + email OTP) is the next round. Until then, dev and demo use personas (F9). */
export function SignIn() {
  const { signIn } = useSession();
  const personas = useQuery({ queryKey: ["personas"], enabled: SHOW_DEV_TOOLS, queryFn: () => unwrap(api.GET("/api/demo/personas")) });
  const pick = async (key: string) => {
    const t = await unwrap(api.POST("/api/demo/token", { body: { persona: key } }));
    signIn(t.access_token);
  };
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-6 px-4 py-12">
      <h1 className="t-display">Circuit</h1>
      {!SHOW_DEV_TOOLS ? (
        <p className="t-body text-text-muted">Sign-in opens soon.</p>
      ) : (
        <>
          <p className="t-body text-text-muted">Choose a demo person to see Circuit as they do.</p>
          {personas.isError && <p className="t-body text-danger" role="alert">Couldn't reach the demo server. Check that the backend is running and try again.</p>}
          <ul className="flex flex-col gap-2">
            {personas.data?.filter((p) => p.key !== "admin").map((p) => (
              <li key={p.key}>
                <Button className="w-full justify-between" onClick={() => pick(p.key)}>
                  <span>{p.display_name}</span>
                  <span className="t-caption font-normal text-text-muted">{roleLabel(p.role)}</span>
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}

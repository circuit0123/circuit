"use client";

import { Button } from "@circuit/ui";
import { usePersonaSignIn, usePersonas } from "@/data";
import { SHOW_DEV_TOOLS } from "@/lib/env";

/** Placeholder until the Welcome screen: dev and demo sign in as a persona (F9). */
export function SignIn() {
  const personas = usePersonas();
  const pick = usePersonaSignIn();
  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col justify-center gap-6 px-4 py-12">
      <h1 className="t-large">Circuit</h1>
      {!SHOW_DEV_TOOLS ? (
        <p className="t-body text-text-muted">Sign-in opens soon.</p>
      ) : (
        <>
          <p className="t-body text-text-muted">Choose a demo person to see Circuit as they do.</p>
          {personas.isError && <p className="t-body text-danger" role="alert">Couldn't reach the demo server. Check that the backend is running and try again.</p>}
          <ul className="flex flex-col gap-2">
            {personas.data?.map((p) => (
              <li key={p.key}>
                <Button className="w-full justify-between" disabled={pick.isPending} onClick={() => pick.mutate(p.key)}>
                  <span>{p.name}</span>
                  <span className="t-footnote font-normal text-text-muted">{p.role}</span>
                </Button>
              </li>
            ))}
          </ul>
        </>
      )}
    </main>
  );
}

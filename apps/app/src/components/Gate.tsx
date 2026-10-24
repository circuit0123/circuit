"use client";

import { Button, Skeleton } from "@circuit/ui";
import { useGate } from "@/data";
import { SignIn } from "./SignIn";

function Centered({ children }: { children: React.ReactNode }) {
  return <main className="mx-auto flex min-h-dvh w-full max-w-[440px] flex-col justify-center gap-4 px-4 py-12">{children}</main>;
}

/** Shows the screen the person belongs on: sign-in, consent, invite, onboarding, or the app itself. */
export function Gate({ children }: { children: React.ReactNode }) {
  const { gate, retry } = useGate();
  switch (gate) {
    case "loading":
      return <Centered><Skeleton className="h-10 w-2/3" /><Skeleton className="h-24" /></Centered>;
    case "signed_out":
      return <SignIn />;
    case "error":
      return (
        <Centered>
          <h1 className="t-title2">Couldn't open Circuit</h1>
          <p className="t-body text-text-muted">Check your connection and try again.</p>
          <Button variant="primary" onClick={retry}>Try again</Button>
        </Centered>
      );
    case "ready":
      return <>{children}</>;
    default:
      // consent, invite and onboarding screens arrive in the next steps.
      return <Centered><h1 className="t-title2">Almost there</h1></Centered>;
  }
}

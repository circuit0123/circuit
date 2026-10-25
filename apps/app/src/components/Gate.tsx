"use client";

import { Button, Skeleton } from "@circuit/ui";
import { useEffect } from "react";
import { useGate, useJoinContext } from "@/data";
import { Centered } from "./Centered";
import { Consent } from "./onboarding/Consent";
import { Invite } from "./onboarding/Invite";
import { SignIn } from "./SignIn";

/** Shows the screen the person belongs on: sign-in, consent, invite, onboarding, or the app itself. */
export function Gate({ children }: { children: React.ReactNode }) {
  const { gate, retry } = useGate();
  const { clear: forgetLink } = useJoinContext();
  // Whatever a link told us has done its job once the person is inside.
  useEffect(() => { if (gate === "ready") forgetLink(); }, [gate, forgetLink]);
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
    case "consent":
      return <Consent />;
    case "invite":
      return <Invite />;
    default:
      // onboarding arrives in the next step.
      return <Centered><h1 className="t-title2">Almost there</h1></Centered>;
  }
}

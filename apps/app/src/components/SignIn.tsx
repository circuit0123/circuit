"use client";

import { Button, CodeField, Logo, Step, StepTransition, TextField, Skeleton } from "@circuit/ui";
import { useEffect, useRef, useState } from "react";
import { problemOf, usePersonaSignIn, usePersonas, useSupabaseSignIn } from "@/data";
import { SHOW_DEV_TOOLS } from "@/lib/env";
import { Legal } from "./Legal";

type Screen = "welcome" | "email" | "code";
const ORDER: Screen[] = ["welcome", "email", "code"];
const RESEND_SECONDS = 30;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** The circuit-trace drawing above the title (Welcome.dc.html): decoration only, in the surface tones, with one live node. */
function Trace() {
  return (
    <svg viewBox="0 0 390 360" fill="none" aria-hidden className="h-full w-full max-w-[440px]" preserveAspectRatio="xMidYMax slice">
      <path d="M-10 250 H110 L160 170 H260 L300 210 H400" className="stroke-surface-2" strokeWidth="2" />
      <path d="M40 120 H150 L190 160 H330" className="stroke-surface-2" strokeWidth="2" />
      <path d="M-10 310 H70 L100 280 H220" className="stroke-surface" strokeWidth="2" />
      <circle cx="160" cy="170" r="5" className="fill-surface-3" />
      <circle cx="300" cy="210" r="5" className="fill-surface-3" />
      <circle cx="190" cy="160" r="5" className="fill-surface-3" />
      <circle cx="260" cy="170" r="6" className="fill-live" />
    </svg>
  );
}

/** Dev and demo only (F9): sign in as a seeded person instead of Google. Never rendered in staging or production. */
function Personas() {
  const personas = usePersonas();
  const pick = usePersonaSignIn();
  if (!SHOW_DEV_TOOLS) return null;
  return (
    <section aria-label="Demo people" className="mt-8">
      <h2 className="t-footnote mb-2 text-text-muted">Demo people (dev and demo only)</h2>
      {personas.isPending && <Skeleton className="h-24" />}
      {personas.isError && <p role="alert" className="t-footnote text-danger">Couldn't reach the demo server. Check that the backend is running and try again.</p>}
      {pick.isError && <p role="alert" className="t-footnote text-danger">Couldn't sign in as that person. Try again.</p>}
      <ul className="grid grid-cols-2 gap-2">
        {personas.data?.map((p) => (
          <li key={p.key}>
            <button type="button" disabled={pick.isPending} onClick={() => pick.mutate(p.key)} className="flex min-h-11 w-full flex-col items-start rounded-control bg-surface-2 px-3 py-2 text-left active:opacity-80 disabled:opacity-50">
              <span className="t-subhead w-full truncate font-medium">{p.name}</span>
              <span className="t-caption text-text">{p.role}</span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Welcome, then (only if they pick email) the address and the 6-digit code. DESIGN.md §4 steps 1 and 2. */
export function SignIn() {
  const sb = useSupabaseSignIn();
  const [screen, setScreen] = useState<Screen>("welcome");
  const [direction, setDirection] = useState<1 | -1>(1);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [emailError, setEmailError] = useState<string | null>(null);
  const [codeError, setCodeError] = useState<string | null>(null);
  const [googleError, setGoogleError] = useState<string | null>(null);
  const [wait, setWait] = useState(0);
  const verifying = useRef(false);

  const go = (to: Screen) => {
    setDirection(ORDER.indexOf(to) > ORDER.indexOf(screen) ? 1 : -1);
    setScreen(to);
  };

  useEffect(() => {
    if (wait <= 0) return;
    const t = setTimeout(() => setWait((w) => w - 1), 1000);
    return () => clearTimeout(t);
  }, [wait]);

  const notReady = "Sign-in isn't set up here yet.";
  const reason = (e: unknown, fallback: string) => {
    const p = problemOf(e);
    if (p.kind === "rate_limited") return p.message;
    return e instanceof Error && e.message === notReady ? notReady : fallback;
  };

  const google = () => {
    setGoogleError(null);
    sb.google.mutate(undefined, { onError: (e) => setGoogleError(reason(e, "Couldn't open Google. Try again, or use email instead.")) });
  };

  const sendCode = (after?: () => void) => {
    const addr = email.trim();
    if (!EMAIL.test(addr)) { setEmailError("Enter your email address, like name@example.com."); return; }
    setEmailError(null);
    sb.sendCode.mutate(addr, {
      onSuccess: () => { setCode(""); setCodeError(null); setWait(RESEND_SECONDS); after?.(); },
      onError: (e) => setEmailError(reason(e, "Couldn't send a code to that address. Check it and try again.")),
    });
  };

  const verify = (digits: string) => {
    if (verifying.current) return;
    verifying.current = true;
    setCodeError(null);
    sb.verifyCode.mutate({ email: email.trim(), code: digits }, {
      onError: (e) => setCodeError(reason(e, "That code didn't work. Check it, or ask for a new one.")),
      onSettled: () => { verifying.current = false; },
    });
  };

  return (
    <StepTransition stepKey={screen} direction={direction}>
      {screen === "welcome" && (
        <main className="mx-auto flex min-h-dvh w-full max-w-[440px] flex-col px-4">
          <div className="pointer-events-none -mx-4 mt-[env(safe-area-inset-top)] min-h-0 flex-1 basis-[28vh]"><Trace /></div>
          <div className="pt-6">
            <Logo height={36} />
            <h1 className="t-large mt-3">Build with people near you.</h1>
            <p className="t-body mt-3 text-text-muted">Find work, collaborators and mentors who need what you're good at.</p>
            <Personas />
          </div>
          <footer className="sticky bottom-0 -mx-4 mt-8 flex flex-col gap-1 bg-bg px-4 pb-[max(16px,env(safe-area-inset-bottom))] pt-3">
            <Button variant="primary" className="w-full" disabled={sb.google.isPending} onClick={google}>Continue with Google</Button>
            {googleError && <p role="alert" className="t-footnote text-danger">{googleError}</p>}
            <Button variant="text" className="w-full" onClick={() => go("email")}>Use email instead</Button>
            <Legal />
          </footer>
        </main>
      )}
      {screen === "email" && (
        <Step
          title="What's your email?"
          subhead="We'll send you a 6-digit code. No password."
          onBack={() => go("welcome")}
          footer={<Button variant="primary" className="w-full" disabled={sb.sendCode.isPending} onClick={() => sendCode(() => go("code"))}>Send code</Button>}
        >
          <form onSubmit={(e) => { e.preventDefault(); sendCode(() => go("code")); }}>
            <TextField label="Email" type="email" inputMode="email" autoComplete="email" autoFocus value={email} onChange={(e) => { setEmail(e.target.value); setEmailError(null); }} error={emailError} placeholder="name@example.com" />
          </form>
        </Step>
      )}
      {screen === "code" && (
        <Step
          title="Check your inbox."
          subhead={`We sent a 6-digit code to ${email.trim()}.`}
          onBack={() => go("email")}
          footer={
            <Button variant="text" className="w-full" disabled={wait > 0 || sb.sendCode.isPending} onClick={() => sendCode()}>
              {wait > 0 ? `Resend in ${wait}s` : "Resend code"}
            </Button>
          }
        >
          <CodeField label="6-digit code" value={code} onChange={(v) => { setCode(v); setCodeError(null); }} onComplete={verify} error={codeError} disabled={sb.verifyCode.isPending} />
          {emailError && <p role="alert" className="t-footnote mt-3 text-danger">{emailError}</p>}
        </Step>
      )}
    </StepTransition>
  );
}

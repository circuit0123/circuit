"use client";

import { Button, Skeleton, Step, TextField } from "@circuit/ui";
import { useState } from "react";
import { inviteMessage, problemOf, useInviteLink, useJoinWaitlist, useRedeem, useRoleChoices, useSession } from "@/data";
import { Centered } from "../Centered";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const MIN_CODE = 6;

type Mode = "code" | "role" | "confirm" | "done";

/** Step 3. Shown when the beta is on and this person has no access yet; an invite link skips it. */
export function Invite() {
  const link = useInviteLink();
  const { signOut } = useSession();
  const [mode, setMode] = useState<Mode>("code");
  const [role, setRole] = useState<string | undefined>();

  if (link.checking) {
    return (
      <Centered>
        <p className="t-callout text-text-muted" role="status">Checking your invite…</p>
        <Skeleton className="h-10 w-2/3" />
      </Centered>
    );
  }
  if (mode === "code") return <Code prefill={link.failed} onWaitlist={() => setMode("role")} onBack={() => void signOut()} />;
  return <Waitlist mode={mode} setMode={setMode} role={role} setRole={setRole} onCode={() => setMode("code")} />;
}

function Code({ prefill, onWaitlist, onBack }: { prefill: { code: string; error: string } | null; onWaitlist: () => void; onBack: () => void }) {
  const redeem = useRedeem();
  const [code, setCode] = useState(prefill?.code ?? "");
  const [error, setError] = useState<string | null>(prefill?.error ?? null);
  const ready = code.replace(/\s/g, "").length >= MIN_CODE;
  const submit = () => {
    if (!ready || redeem.isPending) return;
    setError(null);
    redeem.mutate(code, { onError: (e) => setError(inviteMessage(e)) }); // what was typed stays put
  };
  return (
    <Step
      title="Got an invite code?"
      subhead="Circuit is invite-only while we're in beta."
      progress={0.06}
      onBack={onBack}
      footer={
        <>
          <Button variant="primary" className="w-full" disabled={!ready || redeem.isPending} onClick={submit}>Continue</Button>
          <Button variant="text" className="w-full" onClick={onWaitlist}>Join the waitlist</Button>
        </>
      }
    >
      <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="mt-4">
        <label className="block">
          <span className="sr-only">Invite code</span>
          <input
            value={code}
            onChange={(e) => { setCode(e.target.value.toUpperCase()); setError(null); }}
            placeholder="CIRCUIT-0000"
            autoCapitalize="characters"
            autoComplete="off"
            autoCorrect="off"
            spellCheck={false}
            autoFocus
            aria-invalid={!!error}
            aria-describedby={error ? "invite-error" : undefined}
            className={`h-16 w-full rounded-control bg-surface-2 px-5 font-mono t-title2 tracking-[0.08em] text-text outline-none placeholder:text-text-subtle ${error ? "ring-1 ring-danger" : ""}`}
          />
        </label>
        {error && <p id="invite-error" role="alert" className="t-footnote mt-3 text-danger">{error}</p>}
      </form>
    </Step>
  );
}

function Waitlist({ mode, setMode, role, setRole, onCode }: { mode: Mode; setMode: (m: Mode) => void; role?: string; setRole: (r: string) => void; onCode: () => void }) {
  const wait = useJoinWaitlist();
  const rows = useRoleChoices();
  const { signOut, identity } = useSession();
  const chosen = role ?? wait.role; // a link's role answers the question
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);
  const email = wait.email || typed.trim();

  const go = () => {
    if (!EMAIL.test(email)) { setError("Enter your email address, like name@example.com."); return; }
    setError(null);
    wait.mutate(
      { email, role: chosen ?? "student" },
      {
        onSuccess: () => setMode("done"),
        onError: (e) => { const p = problemOf(e); setError(p.kind === "rate_limited" || p.kind === "network" ? p.message : "Couldn't join the waitlist. Try again in a moment."); },
      },
    );
  };

  if (mode === "role" && !chosen) {
    return (
      <Step title="What brings you here?" subhead="So we know who to save a spot for." progress={0.06} onBack={onCode}>
        <div className="flex flex-col gap-3">
          {rows.map((r) => (
            <button key={r.choice} type="button" onClick={() => { setRole(r.choice === "invest" ? "investor" : r.choice); setMode("confirm"); }} className="flex min-h-16 items-center justify-between rounded-card bg-surface px-5 text-left t-body font-medium active:opacity-80">
              {r.label}
            </button>
          ))}
        </div>
      </Step>
    );
  }
  if (mode === "done") {
    return (
      <Step
        title="You're on the list."
        subhead={email ? `We'll email ${email} when your invite is ready.` : "We'll email you when your invite is ready."}
        footer={
          <>
            <Button variant="primary" className="w-full" onClick={() => void signOut()}>Done</Button>
            <Button variant="text" className="w-full" onClick={onCode}>I have an invite code</Button>
          </>
        }
      />
    );
  }
  return (
    <Step
      title="Join the waitlist."
      subhead="We're letting people in a few at a time."
      progress={0.06}
      onBack={() => setMode(chosen && !wait.role ? "role" : "code")}
      footer={
        <>
          {error && <p role="alert" className="t-footnote text-danger">{error}</p>}
          <Button variant="primary" className="w-full" disabled={wait.isPending} onClick={go}>Join the waitlist</Button>
        </>
      }
    >
      {identity?.email ? (
        <p className="t-body text-text-muted">We'll email <span className="text-text">{identity.email}</span> as soon as there's a spot.</p>
      ) : (
        <form onSubmit={(e) => { e.preventDefault(); go(); }}>
          <TextField label="Email" type="email" inputMode="email" autoComplete="email" autoFocus value={typed} onChange={(e) => { setTyped(e.target.value); setError(null); }} placeholder="name@example.com" />
        </form>
      )}
    </Step>
  );
}

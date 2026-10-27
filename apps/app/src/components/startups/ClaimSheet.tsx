"use client";

import { Button, CodeField, Sheet, TextField, useToast } from "@circuit/ui";
import { useEffect, useState } from "react";
import { ClaimError, useStartClaim, useVerifyClaim } from "@/data";

/**
 * Claim this startup (CLAUDE.md F3): a code goes to a work email on the startup's own domain; entering it makes the page yours.
 * Two steps in one sheet, nothing else on it.
 */
export function ClaimSheet({ open, onClose, startup }: { open: boolean; onClose: () => void; startup: { id: number; name: string; website: string } }) {
  const toast = useToast();
  const start = useStartClaim(startup.id);
  const verify = useVerifyClaim(startup.id);
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const sent = start.isSuccess;

  useEffect(() => {
    if (open) return;
    setEmail(""); setCode(""); start.reset(); verify.reset(); // eslint-disable-line react-hooks/set-state-in-effect
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const err = (e: unknown) => (e instanceof ClaimError ? e.detail : e ? "Couldn't send that. Check your connection and try again." : null);
  const confirm = (c: string) => verify.mutate(c, {
    onSuccess: () => { onClose(); toast({ text: `${startup.name} is yours now. What you change here is never overwritten.` }); },
  });

  return (
    <Sheet open={open} onClose={onClose} title={`Claim ${startup.name}`} detents={["large"]} detent="large">
      {!sent ? (
        <form className="flex flex-col gap-6 pt-2" onSubmit={(e) => { e.preventDefault(); if (email.trim()) start.mutate(email.trim()); }}>
          <p className="t-body text-text-muted">We'll send a code to your work email at {startup.website}. That's how we know you're on the team.</p>
          <TextField label={`Work email at ${startup.website}`} type="email" autoComplete="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder={`you@${startup.website}`} error={err(start.error)} />
          <Button type="submit" variant="primary" className="w-full" disabled={!email.trim() || start.isPending}>{start.isPending ? "Sending…" : "Send code"}</Button>
        </form>
      ) : (
        <form className="flex flex-col gap-6 pt-2" onSubmit={(e) => { e.preventDefault(); if (code.length === 8) confirm(code); }}>
          <p className="t-body text-text-muted">Enter the 8-character code we sent to {email}.</p>
          {start.data?.dev_code && <p className="t-subhead text-text-muted">Test builds only: the code is <span className="num">{start.data.dev_code}</span>.</p>}
          <CodeField kind="code" length={8} label="Code" value={code} onChange={setCode} onComplete={confirm} error={err(verify.error)} disabled={verify.isPending} />
          <Button type="submit" variant="primary" className="w-full" disabled={code.length !== 8 || verify.isPending}>{verify.isPending ? "Checking…" : "Claim startup"}</Button>
          <Button variant="text" className="w-full" onClick={() => { start.reset(); setCode(""); }}>Use a different email</Button>
        </form>
      )}
    </Sheet>
  );
}

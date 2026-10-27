"use client";

import { Button, CodeField, Sheet, TextField, useToast } from "@circuit/ui";
import { useEffect, useState } from "react";
import { useWorkEmail, workEmailProblem as problem } from "@/data";

/** Verify your work email (verification level 2): a code goes to the address, entering it raises the level. Two steps, nothing else on the sheet. */
export function WorkEmailSheet({ open, onClose }: { open: boolean; onClose: () => void }) {
  const toast = useToast();
  const { start, confirm } = useWorkEmail();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const sent = start.isSuccess;

  useEffect(() => {
    if (open) return;
    setEmail(""); setCode(""); start.reset(); confirm.reset(); // eslint-disable-line react-hooks/set-state-in-effect
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps

  const check = (c: string) => confirm.mutate(c, { onSuccess: () => { onClose(); toast({ text: "Your work email is verified." }); } });

  return (
    <Sheet open={open} onClose={onClose} title="Verify your work email" detents={["large"]} detent="large">
      {!sent ? (
        <form className="flex flex-col gap-6 pt-2" onSubmit={(e) => { e.preventDefault(); if (email.trim()) start.mutate(email.trim()); }}>
          <p className="t-body text-text-muted">We&apos;ll send a code to your work email. A verified badge helps people say yes to you.</p>
          <TextField label="Work email" type="email" autoComplete="email" inputMode="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@yourcompany.com" error={problem(start.error)} />
          <Button type="submit" variant="primary" className="w-full" disabled={!email.trim() || start.isPending}>{start.isPending ? "Sending…" : "Send code"}</Button>
        </form>
      ) : (
        <form className="flex flex-col gap-6 pt-2" onSubmit={(e) => { e.preventDefault(); if (code.length === 8) check(code); }}>
          <p className="t-body text-text-muted">Enter the 8-character code we sent to {email}.</p>
          {start.data?.dev_code && <p className="t-subhead text-text-muted">Test builds only: the code is <span className="num">{start.data.dev_code}</span>.</p>}
          <CodeField kind="code" length={8} label="Code" value={code} onChange={setCode} onComplete={check} error={problem(confirm.error)} disabled={confirm.isPending} />
          <Button type="submit" variant="primary" className="w-full" disabled={code.length !== 8 || confirm.isPending}>{confirm.isPending ? "Checking…" : "Verify"}</Button>
          <Button variant="text" className="w-full" onClick={() => { start.reset(); setCode(""); }}>Use a different email</Button>
        </form>
      )}
    </Sheet>
  );
}

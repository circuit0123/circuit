"use client";

import { Button, TextField } from "@circuit/ui";
import Link from "next/link";
import { useState } from "react";
import { DELETE_WORD, settingsHref, useDeleteAccount } from "@/data";
import { ConfirmSheet } from "../sheets";
import { SettingsScreen } from "./SettingsHome";

/**
 * Delete account: what happens, then type DELETE, then confirm in a sheet. After that the session ends; the API answers 403
 * `account_deleted` to anything else, which signs out too.
 */
export function DeleteAccount() {
  const del = useDeleteAccount();
  const [typed, setTyped] = useState("");
  const [confirm, setConfirm] = useState(false);
  const ready = typed.trim() === DELETE_WORD;
  return (
    <SettingsScreen title="Delete account">
      <div className="flex flex-col gap-5 px-4 lg:px-0">
        <ul className="t-body flex max-w-[540px] list-disc flex-col gap-2 pl-5">
          <li>Your profile, matches and intro requests are removed, and nobody can find you.</li>
          <li>Build logs, replies and messages you sent stay where they are, shown as &ldquo;Deleted member&rdquo;.</li>
          <li>You&apos;re signed out on every device. This can&apos;t be undone.</li>
        </ul>
        <p className="t-subhead text-text-muted">Want a copy first? <Link href={settingsHref("export")} className="underline">Export your data</Link>.</p>
        <TextField label={`Type ${DELETE_WORD} to confirm`} value={typed} onChange={(e) => setTyped(e.target.value)} autoCapitalize="characters" autoComplete="off" spellCheck={false} />
        <Button variant="destructive" className="w-full" disabled={!ready} onClick={() => setConfirm(true)}>Delete my account</Button>
        {del.isError && <p role="alert" className="t-footnote text-danger">Couldn&apos;t delete your account. Check your connection and try again.</p>}
      </div>
      <ConfirmSheet
        open={confirm}
        onClose={() => setConfirm(false)}
        title="Delete your account?"
        text="Your profile goes now and you'll be signed out. This can't be undone."
        confirmLabel="Delete account"
        busy={del.isPending}
        onConfirm={() => del.mutate(typed, { onSettled: () => setConfirm(false) })}
      />
    </SettingsScreen>
  );
}

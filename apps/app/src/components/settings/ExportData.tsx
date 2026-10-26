"use client";

import { Button, ErrorState, Skeleton } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { loadFailed, useExport, useExportDownload } from "@/data";
import { SettingsScreen } from "./SettingsHome";

const DAY = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "long", timeZone: "Asia/Kolkata" });
const size = (b: number) => (b >= 1_000_000 ? `${(b / 1_000_000).toFixed(1)} MB` : `${Math.max(1, Math.round(b / 1000))} KB`);

/**
 * Export my data: ask, then "preparing", then a link by email. With `token` (the email link opens /settings/export?token=…) it offers the
 * download instead; an old link says it has expired, and a link for another account says so.
 */
export function ExportData({ token }: { token: string | null }) {
  return <SettingsScreen title="Export my data">{token ? <Download token={token} /> : <Ask />}</SettingsScreen>;
}

function Ask() {
  const e = useExport();
  const st = e.state;
  const ask = <Button variant="primary" className="w-full" disabled={e.request.isPending} onClick={() => e.request.mutate()}>{e.request.isPending ? "Asking…" : "Ask for my data"}</Button>;
  return (
    <div className="flex flex-col gap-5 px-4 lg:px-0">
      <p className="t-body max-w-[540px]">A copy of what you&apos;ve put on Circuit: your profile, build logs, replies, messages, intros, circuits and applications, as one file.</p>
      {e.isPending && <Skeleton className="h-12" />}
      {e.isError && <ErrorState text={loadFailed("your data export")} onRetry={() => void e.refetch()} />}
      {!e.isPending && !e.isError && (
        st.kind === "preparing" ? (
          <p className="t-body rounded-card bg-surface p-4" role="status">We&apos;re preparing your file. We&apos;ll email you a link when it&apos;s ready, usually within a day.</p>
        ) : st.kind === "ready" ? (
          <p className="t-body rounded-card bg-surface p-4" role="status">Your file is ready. Open the link we emailed you to download it{st.expiresAt ? `. It works until ${DAY.format(new Date(st.expiresAt))}` : ""}.</p>
        ) : st.kind === "expired" ? (
          <>
            <p className="t-body text-text-muted">Your last file has expired. Ask again for a new one.</p>
            {ask}
          </>
        ) : ask
      )}
      {e.problem && <p role="alert" className="t-footnote text-danger">{e.problem}</p>}
    </div>
  );
}

function Download({ token }: { token: string }) {
  const router = useRouter();
  const d = useExportDownload(token);
  return (
    <div className="flex flex-col gap-5 px-4 lg:px-0">
      {d.isPending && <Skeleton className="h-12" />}
      {d.link && (
        <>
          <p className="t-body">Your data is ready to download. The link works for a few minutes.</p>
          <a href={d.link.url} download="circuit-export.json" className="inline-flex min-h-[50px] w-full items-center justify-center rounded-control bg-primary px-5 t-body font-semibold text-on-primary active:scale-[0.97] lg:min-h-11">
            Download ({size(d.link.sizeBytes)})
          </a>
        </>
      )}
      {d.failure === "expired" && (
        <>
          <p className="t-body">This link has expired. Ask for your data again to get a new one.</p>
          <Button variant="primary" className="w-full" onClick={() => router.replace("/settings/export")}>Ask again</Button>
        </>
      )}
      {d.failure === "not_yours" && <p className="t-body">This link belongs to a different account. Sign in with the account that asked for the data.</p>}
      {d.failure === "failed" && <ErrorState text="Couldn't open your download. Check your connection and try again." onRetry={() => void d.refetch()} />}
    </div>
  );
}

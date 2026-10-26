"use client";

import { Avatar, EmptyState, ErrorState, PushScreen, Button } from "@circuit/ui";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { loadFailed, roleHref, useMyApplications } from "@/data";
import { RowsSkeleton } from "../discover/parts";
import { goBack } from "./JobScreen";

/** "Your applications": every role you applied to, newest first, with where it stands in plain words. */
export function Applications() {
  const router = useRouter();
  const apps = useMyApplications();
  return (
    <PushScreen title="Your applications" largeTitle backLabel="Discover" onBack={() => goBack(router)} bleed>
      <div className="mt-4">
        {apps.isPending && <RowsSkeleton rows={3} />}
        {apps.isError && <ErrorState className="px-4 lg:px-0" text={loadFailed("your applications")} onRetry={() => apps.refetch()} />}
        {apps.data?.length === 0 && (
          <EmptyState
            className="px-4 lg:px-0"
            text="You haven't applied to a role yet. Roles that fit your skills are in Discover."
            action={<Button onClick={() => router.push("/discover?s=jobs")}>See roles</Button>}
          />
        )}
        {!!apps.data?.length && (
          <ul aria-label="Applications">
            {apps.data.map((a) => (
              <li key={a.id}>
                <Link href={roleHref(a.jobId)} className="flex items-center gap-4 border-b border-separator px-4 lg:px-0 py-3 active:opacity-80">
                  <Avatar id={`s${a.startupId}`} name={a.startup} size={44} shape="square" />
                  <span className="min-w-0 flex-1">
                    <span className="t-headline block">{a.title}</span>
                    <span className="t-subhead block text-text-muted">{a.startup} · applied {a.when === "now" ? "just now" : `${a.when} ago`}</span>
                  </span>
                  <span className={a.statusKey === "shortlisted" || a.statusKey === "hired" ? "t-subhead font-semibold" : "t-subhead text-text-muted"}>{a.status}</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </PushScreen>
  );
}

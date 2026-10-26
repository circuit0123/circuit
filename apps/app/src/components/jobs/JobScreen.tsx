"use client";

import { Avatar, Button, Chip, ErrorState, PushScreen, Skeleton, cx } from "@circuit/ui";
import Link from "next/link";
import { notFound, useRouter } from "next/navigation";
import { applicantsHref, kmOrNull, loadFailed, metaLine, problemOf, startupHref, useApply, useJob, useMe, useStartup } from "@/data";

export const goBack = (router: ReturnType<typeof useRouter>, fallback = "/discover") => (window.history.length > 1 ? router.back() : router.push(fallback));

/** A label on the left, its value on the right: one row of the facts list in Job.dc.html. */
export function Fact({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex min-h-[52px] items-center justify-between gap-4 px-4">
      <span className="t-body text-text-muted">{label}</span>
      <span className={cx("t-body text-right", mono && "num")}>{value}</span>
    </div>
  );
}

/**
 * Job page (Job.dc.html): who is hiring, the role as a Large title, the facts, how your skills match, what the work is, and a sticky
 * `Apply with your profile` (one click: the profile is the application). The startup's team sees `See applicants` instead.
 */
export function JobScreen({ id }: { id: number }) {
  const router = useRouter();
  const me = useMe().data;
  const job = useJob(id);
  const apply = useApply();
  const j = job.data;
  const team = useStartup(me?.role === "founder" && j ? j.startupId : NaN).data?.isTeam ?? false;
  if (job.notFound || !Number.isFinite(id)) notFound();

  const footer = !j ? undefined : team ? (
    <Button variant="primary" className="w-full" onClick={() => router.push(applicantsHref(j.id))}>See applicants</Button>
  ) : !j.isOpen ? (
    <p className="t-body flex min-h-[50px] items-center text-text-muted">This role is closed.</p>
  ) : me?.role !== "student" ? undefined : j.applied ? (
    <div className="flex min-h-[50px] flex-col justify-center" role="status">
      <p className="t-headline">Applied</p>
      <p className="t-subhead text-text-muted">We'll tell you when {j.startup} replies.</p>
    </div>
  ) : (
    <div>
      {apply.isError && <p role="alert" className="t-subhead mb-2 text-danger">{applyFailed(apply.error)}</p>}
      <Button variant="primary" className="w-full" disabled={apply.isPending} onClick={() => apply.mutate(j.id)}>
        {apply.isPending ? "Applying…" : "Apply with your profile"}
      </Button>
    </div>
  );

  return (
    <PushScreen title={j?.title ?? "Role"} backLabel="Discover" onBack={() => goBack(router)} footer={footer} bleed>
      {job.isPending && <div className="px-4 lg:px-0"><Skeleton className="h-10 w-2/3" /><Skeleton className="mt-6 h-40" /></div>}
      {job.isError && !job.notFound && <ErrorState className="px-4 lg:px-0 pt-6" text={loadFailed("this role")} onRetry={() => job.refetch()} />}
      {j && (
        <>
          <Link href={startupHref(j.startupId)} className="mx-4 lg:mx-0 flex items-center gap-3 active:opacity-80">
            <Avatar id={`s${j.startupId}`} name={j.startup} size={40} shape="square" />
            <span className="t-subhead text-text-muted">{metaLine(j.startup, j.sector, kmOrNull(j.km))}</span>
          </Link>
          <h1 className="t-large mx-4 lg:mx-0 mt-3">{j.title}</h1>

          <div className="mx-4 lg:mx-0 mt-6 divide-y divide-separator overflow-hidden rounded-group bg-surface">
            <Fact label="Stipend" value={j.stipend ?? "Not listed"} mono={!!j.stipend} />
            <Fact label="Type" value={j.kind} />
            <Fact label="Where" value={j.location} />
          </div>

          {j.skills.length > 0 && (
            <section aria-label="Skill match" className="mx-4 lg:mx-0 mt-section">
              <h2 className="t-title3 mb-3">{me?.role === "student" ? `You match ${j.matched} of ${j.skills.length} skills` : "Skills this role asks for"}</h2>
              <ul className="flex flex-wrap gap-2">
                {j.skills.map((s) => (
                  <li key={s.name}>
                    {s.have || me?.role !== "student" ? <Chip label={s.name} /> : (
                      <span className="inline-flex min-h-8 items-center rounded-full border border-dashed border-text-subtle/60 px-3 t-subhead text-text-muted">
                        {s.name}<span className="sr-only">, not one of your skills yet</span>
                      </span>
                    )}
                  </li>
                ))}
              </ul>
            </section>
          )}

          {j.description && (
            <section aria-label="About the role" className="mx-4 lg:mx-0 mt-section">
              <h2 className="t-title3 mb-3">About the role</h2>
              <p className="t-body max-w-[540px]">{j.description}</p>
            </section>
          )}
        </>
      )}
    </PushScreen>
  );
}

function applyFailed(e: unknown): string {
  const p = problemOf(e);
  if (p.kind === "network") return "Couldn't send your application. Check your connection and try again.";
  if (p.kind === "rate_limited") return p.message;
  if (p.kind === "forbidden" || p.kind === "invalid") return p.message;
  return "Couldn't send your application. Try again.";
}

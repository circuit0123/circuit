"use client";

import { ExternalLink } from "lucide-react";
import { Avatar, Button, EmptyState, ErrorState, PushScreen } from "@circuit/ui";
import { notFound, useRouter } from "next/navigation";
import { loadFailed, useApplicants, useCapabilities, useJob, useMe, useSetApplicantStatus, type ApplicantRow } from "@/data";
import { RowsSkeleton } from "../discover/parts";
import { goBack } from "./JobScreen";

const LEVEL = ["", "learning", "can do", "strong"] as const;

/**
 * The founder's applicant view (CLAUDE.md F11): everyone who applied to one role, ranked by skill match and proof of work, never by
 * college. Founders of the startup only; anyone else gets the 404 screen. Shortlist, Not now and Hired change the status at once.
 */
export function Applicants({ jobId }: { jobId: number }) {
  const router = useRouter();
  const me = useMe().data;
  const isFounder = me?.role === "founder";
  const job = useJob(jobId);
  const list = useApplicants(isFounder ? jobId : NaN);
  const caps = useCapabilities();
  const name = (slug: string) => caps.data?.find((c) => c.slug === slug)?.name ?? slug;
  if (me && (!isFounder || list.denied || job.notFound)) notFound();

  return (
    <PushScreen title="Applicants" largeTitle backLabel={job.data?.title ?? "Role"} onBack={() => goBack(router, `/discover/jobs/${jobId}`)} bleed>
      {job.data && <p className="t-subhead -mt-1 px-4 lg:px-0 text-text-muted">{job.data.title} · ranked by skill match</p>}
      <div className="mt-6">
        {(list.isPending || !me) && <RowsSkeleton rows={4} />}
        {list.isError && !list.denied && <ErrorState className="px-4 lg:px-0" text={loadFailed("applicants")} onRetry={() => list.refetch()} />}
        {list.data?.length === 0 && <EmptyState className="px-4 lg:px-0" text="No one has applied yet. We'll tell you when the first application comes in." />}
        {!!list.data?.length && (
          <ol aria-label="Applicants, best skill match first">
            {list.data.map((a, i) => <li key={a.applicationId}><Applicant a={a} rank={i + 1} jobId={jobId} name={name} /></li>)}
          </ol>
        )}
      </div>
    </PushScreen>
  );
}

function Applicant({ a, rank, jobId, name }: { a: ApplicantRow; rank: number; jobId: number; name: (slug: string) => string }) {
  const set = useSetApplicantStatus(jobId);
  const proofs = a.skills.filter((s) => s.proof);
  const actions = [
    { status: "shortlisted", label: "Shortlist" },
    { status: "rejected", label: "Not now" },
    { status: "hired", label: "Hired" },
  ] as const;
  return (
    <article aria-label={`${rank}. ${a.name}`} className="border-b border-separator px-4 lg:px-0 py-5">
      <div className="flex items-start gap-4">
        <Avatar id={a.studentId} name={a.name} size={44} />
        <div className="min-w-0 flex-1">
          <h2 className="t-headline"><span className="num text-text-muted">{rank}.</span> {a.name}</h2>
          <p className="t-subhead text-text-muted">{a.fit} · applied {a.when === "now" ? "just now" : `${a.when} ago`}</p>
        </div>
        <span className="t-subhead font-semibold" role="status">{a.status}</span>
      </div>
      <ul className="mt-3 flex flex-wrap gap-2" aria-label="Skills">
        {a.skills.map((s) => <li key={s.name} className="inline-flex min-h-8 items-center rounded-full bg-surface-2 px-3 t-subhead">{name(s.name)} · {LEVEL[Math.min(3, Math.max(0, s.level))]}</li>)}
      </ul>
      {proofs.length > 0 && (
        <ul className="mt-3 flex flex-col gap-1" aria-label="Proof of work">
          {proofs.map((s) => (
            <li key={s.proof}>
              <a href={s.proof} target="_blank" rel="noreferrer" className="t-subhead inline-flex min-h-11 items-center gap-1 underline underline-offset-2">
                {new URL(s.proof).host}{new URL(s.proof).pathname.replace(/\/$/, "")}<ExternalLink size={14} strokeWidth={1.75} aria-hidden /><span className="sr-only">(opens in a new tab)</span>
              </a>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label={`Decide on ${a.name}`}>
        {actions.map((x) => (
          <Button key={x.status} variant={a.statusKey === x.status ? "secondary" : "text"} aria-pressed={a.statusKey === x.status} className="min-h-11 px-4 lg:min-h-11" onClick={() => set.mutate({ applicationId: a.applicationId, status: x.status })}>
            {x.label}
          </Button>
        ))}
      </div>
    </article>
  );
}

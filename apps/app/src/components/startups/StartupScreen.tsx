"use client";

import { ExternalLink, MoreHorizontal } from "lucide-react";
import { Avatar, BarButton, Button, Chip, ErrorState, PushScreen, Sheet, Skeleton, VerifiedBadge, firstName, useToast } from "@circuit/ui";
import { notFound, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  hiringState, kmOrNull, loadFailed, metaLine, useFollow, useFollows, useInterest, useIntroPath, useMe, useReport, useStartup, useStartupJobs, type StartupFounder, type StartupPage,
} from "@/data";
import { JobRowItem, RowsSkeleton } from "../discover/parts";
import { useAskIntro } from "../home/IntroSheet";
import { goBack } from "../jobs/JobScreen";
import { ClaimSheet } from "./ClaimSheet";

/**
 * Startup page (DESIGN.md §4 "Startup page"; no reference file, built in the style of Job.dc.html): header, one primary `Follow`, Hiring
 * first, then About, build logs and founders (with `Intro via a mutual` when a warm path exists). Unclaimed pages say where the data came
 * from and offer founders `Claim this startup`. No public counts; the team sees its own views and interest privately.
 */
export function StartupScreen({ id }: { id: number }) {
  const router = useRouter();
  const q = useStartup(id);
  const s = q.data;
  const [menu, setMenu] = useState(false);
  if (q.notFound || !Number.isFinite(id)) notFound();

  return (
    <PushScreen
      title={s?.name ?? "Startup"}
      onBack={() => goBack(router)}
      right={s && <BarButton label="More" onClick={() => setMenu(true)}><MoreHorizontal size={22} strokeWidth={1.75} /></BarButton>}
      bleed
    >
      {q.isPending && <div className="px-4 lg:px-0"><Skeleton className="h-16 w-16" /><Skeleton className="mt-4 h-10 w-2/3" /><Skeleton className="mt-6 h-12" /></div>}
      {q.isError && !q.notFound && <ErrorState className="px-4 lg:px-0 pt-6" text={loadFailed("this startup")} onRetry={() => q.refetch()} />}
      {s && <Page s={s} />}
      {s && <MoreSheet open={menu} onClose={() => setMenu(false)} startup={s} />}
    </PushScreen>
  );
}

function Page({ s }: { s: StartupPage }) {
  const me = useMe().data;
  const follows = useFollows();
  const follow = useFollow();
  const jobs = useStartupJobs(s.hiring && s.openRoles > 0 ? s.id : null);
  const interest = useInterest(s.id, s.interested);
  const toast = useToast();
  const [claim, setClaim] = useState(false);
  const following = follows.data?.has(s.id) ?? false;
  const roles = jobs.data ?? [];
  // `hiring` comes from the API alone (it already says false to an under-18 on an unverified startup); roles never decide it.
  const state = hiringState(s);
  const hiring = state !== "none";

  // `See open roles` and deep links land on Hiring.
  useEffect(() => {
    if (window.location.hash === "#hiring" && !jobs.isPending) document.getElementById("hiring")?.scrollIntoView({ block: "start" });
  }, [jobs.isPending]);

  const toggleInterest = async () => {
    const ok = await interest.set(!interest.interested);
    if (!ok) toast({ text: "Couldn't save that. Try again.", tone: "error" });
  };
  const toggle = () => follow.mutate({ id: s.id, on: !following });

  return (
    <>
      <header className="px-4 lg:px-0">
        <Avatar id={`s${s.id}`} name={s.name} size={64} shape="square" />
        <h1 className="t-large mt-4">{s.name}</h1>
        <p className="t-subhead mt-1 text-text-muted">{metaLine(s.sector, s.stage, s.teamSize ? `${s.teamSize} people` : null)}</p>
        <p className="t-subhead text-text-muted">{metaLine(s.place, kmOrNull(s.km))}</p>
        {s.claimed ? (
          <p className="t-subhead mt-2 flex items-center gap-1 text-text-muted"><VerifiedBadge level={2} />Claimed by its team</p>
        ) : (
          <p className="t-footnote mt-2 text-text-muted">Unclaimed · from public sources</p>
        )}
        <Button variant={following ? "secondary" : "primary"} aria-pressed={following} className="mt-6 w-full" onClick={toggle}>{following ? "Following" : "Follow"}</Button>
        {s.canShowInterest && (
          <Button aria-pressed={interest.interested} className="mt-3 w-full" disabled={interest.pending} onClick={toggleInterest}>
            {interest.interested ? "Interested · tap to withdraw" : "I'm interested"}
          </Button>
        )}
        {s.privateCounts && (
          <p className="t-subhead mt-4 text-text-muted">
            Only your team sees this: <span className="num text-text">{s.privateCounts.views}</span> views and <span className="num text-text">{s.privateCounts.interested}</span> interested this month.
          </p>
        )}
      </header>

      {s.canClaim && (
        <section aria-label="Claim this startup" className="mx-4 lg:mx-0 mt-section rounded-card bg-surface p-surface">
          <h2 className="t-title3">Is this your startup?</h2>
          <p className="t-body mt-2 text-text-muted">
            {s.claimNudge && s.claimNudge.views != null && s.claimNudge.views > 0
              ? `${s.claimNudge.views} students looked at this page${s.claimNudge.interested != null ? ` and ${s.claimNudge.interested} are interested` : ""}. Claim it to post roles and keep it right.`
              : "Claim it to post roles and keep it right."}
          </p>
          <Button variant="secondary" className="mt-4 w-full" onClick={() => setClaim(true)}>Claim this startup</Button>
          <ClaimSheet open={claim} onClose={() => setClaim(false)} startup={s} />
        </section>
      )}

      <section id="hiring" aria-label="Hiring" className="mt-section scroll-mt-16">
        <h2 className="t-title3 mb-1 px-4 lg:px-0">{hiring ? "Hiring" : "Not hiring right now"}</h2>
        {state === "roles" ? (
          jobs.isPending ? <RowsSkeleton rows={2} /> : jobs.isError ? <ErrorState className="px-4 lg:px-0" text={loadFailed("open roles")} onRetry={() => jobs.refetch()} /> : (
            <ul aria-label="Open roles">{roles.map((j) => <li key={j.id}><JobRowItem job={j} showStartup={false} /></li>)}</ul>
          )
        ) : (
          <div className="px-4 lg:px-0">
            {state === "careers" && (
              <a href={s.careersUrl!} target="_blank" rel="noreferrer" className="t-body inline-flex min-h-11 items-center gap-1 underline underline-offset-2">
                Hiring · see their careers page<ExternalLink size={14} strokeWidth={1.75} aria-hidden /><span className="sr-only">(opens in a new tab)</span>
              </a>
            )}
            <p className="t-body text-text-muted">{following ? "You're following. We'll tell you when they post a role." : "Follow to hear when they post a role."}</p>
            {!following && <Button variant="text" className="-ml-5 mt-1" onClick={toggle}>Follow for updates</Button>}
          </div>
        )}
      </section>

      {(s.about || s.techStack.length > 0) && (
        <section aria-label="About" className="mt-section px-4 lg:px-0">
          <h2 className="t-title3 mb-3">About</h2>
          {s.about && <p className="t-body max-w-[540px]">{s.about}</p>}
          {s.techStack.length > 0 && <ul className="mt-4 flex flex-wrap gap-2" aria-label="Built with">{s.techStack.map((t) => <li key={t}><Chip label={t} /></li>)}</ul>}
          {s.website && <a href={`https://${s.website}`} target="_blank" rel="noreferrer" className="t-body mt-4 inline-flex min-h-11 items-center underline underline-offset-2">{s.website}<span className="sr-only"> (opens in a new tab)</span></a>}
        </section>
      )}

      {s.logs.length > 0 && (
        <section aria-label="Build logs" className="mt-section px-4 lg:px-0">
          <h2 className="t-title3 mb-3">Build logs</h2>
          <ul className="grid grid-cols-3 gap-1">
            {/* eslint-disable-next-line @next/next/no-img-element -- Supabase Storage serves the sizes (DESIGN.md §11); next/image is not used in the app */}
            {s.logs.map((l) => <li key={l.id}><img src={l.src} alt={l.alt} className="aspect-square w-full rounded-lg object-cover" loading="lazy" /></li>)}
          </ul>
        </section>
      )}

      {s.founders.length > 0 && (
        <section aria-label="Founders" className="mt-section">
          <h2 className="t-title3 mb-1 px-4 lg:px-0">Founders</h2>
          <ul>{s.founders.map((f) => <li key={f.id}><Founder f={f} minor={!!me?.isMinor} self={f.id === me?.id} /></li>)}</ul>
        </section>
      )}
    </>
  );
}

/** A founder, with `Intro via a mutual` only when a warm path exists. Under-18 members get no intro (DESIGN.md §8). */
function Founder({ f, minor, self }: { f: StartupFounder; minor: boolean; self: boolean }) {
  const path = useIntroPath(minor || self ? null : f.id);
  const ask = useAskIntro();
  const via = path.data?.via;
  return (
    <div className="flex min-h-row-sub items-center gap-4 px-4 lg:px-0 py-2">
      <Avatar id={f.id} name={f.name} size={44} />
      <div className="min-w-0 flex-1">
        <p className="t-headline flex items-center gap-1">{f.name}<VerifiedBadge level={f.level} /></p>
        <p className="t-subhead text-text-muted">{f.role}</p>
      </div>
      {via && <Button variant="secondary" className="min-h-11 px-4 lg:min-h-11" onClick={() => ask({ id: f.id, name: f.name })}>Intro via {firstName(via.name)}</Button>}
      {path.isSuccess && !via && <span className="t-subhead text-text-muted">Connected</span>}
    </div>
  );
}

function MoreSheet({ open, onClose, startup }: { open: boolean; onClose: () => void; startup: StartupPage }) {
  const report = useReport();
  const toast = useToast();
  return (
    <Sheet open={open} onClose={onClose} title={startup.name} detents={["medium"]}>
      <p className="t-body text-text-muted">Something wrong or harmful on this page? We'll take a look within a day.</p>
      <Button
        variant="destructive"
        className="mt-6 w-full"
        disabled={report.isPending}
        onClick={() => report.mutate({ target_type: "startup", target_id: startup.id, reason: "" }, {
          onSuccess: () => { onClose(); toast({ text: "Thanks. We'll look at this page." }); },
          onError: () => toast({ text: "Couldn't send that. Try again.", tone: "error" }),
        })}
      >
        Report this startup
      </Button>
    </Sheet>
  );
}

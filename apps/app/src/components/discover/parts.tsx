"use client";

import { MoreHorizontal } from "lucide-react";
import { Avatar, Button, PatternArt, Sheet, Skeleton, VerifiedBadge, cx } from "@circuit/ui";
import Link from "next/link";
import { useState } from "react";
import { kmOrNull, metaLine, roleHref, startupHref, type JobRow, type PersonTile, type Promotion, type StartupTile } from "@/data";

/** A role as a row (Discover.dc.html): startup mark, title, "Startup · Sector · 3.2 km", then the stipend in mono and the fit in words. No box. */
export function JobRowItem({ job, showStartup = true, className }: { job: JobRow; showStartup?: boolean; className?: string }) {
  return (
    <Link href={roleHref(job.id)} data-feed-item className={cx("flex items-start gap-4 border-b border-separator px-4 py-4 active:opacity-80 lg:px-0", className)}>
      {showStartup && <Avatar id={`s${job.startupId}`} name={job.startup} size={44} shape="square" />}
      <span className="min-w-0 flex-1">
        <span className="t-headline block">{job.title}</span>
        <span className="t-subhead mt-1 block text-text-muted">{showStartup ? metaLine(job.startup, job.sector, kmOrNull(job.km)) : job.kind}</span>
        <span className="mt-1 flex flex-wrap justify-between gap-x-4">
          <span className="num t-subhead">{job.stipend ?? "Stipend not listed"}</span>
          <span className="t-subhead text-text-muted">{job.applied ? "Applied" : job.fit}</span>
        </span>
      </span>
    </Link>
  );
}

/** A person, photo first (People.dc.html): picture, name, what they do, and the match in words. */
export function PersonTileCard({ person, onOpen }: { person: PersonTile; onOpen?: () => void }) {
  const body = (
    <>
      <span className="block aspect-[4/5] overflow-hidden rounded-card"><PatternArt id={person.id} initial={person.name.replace(/^Dr\.?\s+/, "")[0]} banner /></span>
      <span className="mt-2 flex items-center gap-1 t-headline">{person.name}<VerifiedBadge level={person.level} /></span>
      <span className="t-subhead mt-0.5 block text-text-muted">{person.line}</span>
      {person.fit && <span className={cx("t-subhead mt-0.5 block", person.bridge ? "text-bridge" : "text-text-muted")}>{person.fit}</span>}
    </>
  );
  if (!onOpen) return <div className="min-w-0">{body}</div>;
  return (
    <button type="button" onClick={onOpen} className="block min-w-0 text-left active:opacity-80">
      {body}
      <span className="sr-only">. Ask for an intro</span>
    </button>
  );
}

/** A startup, picture first: its mark (circuit pattern until logos exist), name, sector and distance, and whether it is hiring. */
export function StartupTileCard({ startup }: { startup: StartupTile }) {
  const status = startup.hiring ? `Hiring · ${startup.openRoles} ${startup.openRoles === 1 ? "role" : "roles"}` : startup.fit ?? "Not hiring right now";
  return (
    <Link href={startupHref(startup.id)} className="block min-w-0 active:opacity-80">
      <span className="block aspect-square overflow-hidden rounded-card"><PatternArt id={`s${startup.id}`} initial={startup.name[0]} banner /></span>
      <span className="t-headline mt-2 block">{startup.name}</span>
      <span className="t-subhead mt-0.5 block text-text-muted">{metaLine(startup.sector, kmOrNull(startup.km))}</span>
      <span className="t-subhead mt-0.5 block text-text-muted">{status}</span>
    </Link>
  );
}

export function TileGrid({ children, label }: { children: React.ReactNode; label: string }) {
  return <ul aria-label={label} className="grid grid-cols-2 gap-x-3 gap-y-6 px-4 lg:grid-cols-3 lg:px-0">{children}</ul>;
}

export function GridSkeleton() {
  return (
    <div className="grid grid-cols-2 gap-x-3 gap-y-6 px-4 lg:grid-cols-3 lg:px-0" aria-busy="true" aria-label="Loading">
      {[0, 1, 2, 3].map((i) => <div key={i}><Skeleton className="aspect-[4/5] w-full" /><Skeleton className="mt-2 h-5 w-3/4" /></div>)}
    </div>
  );
}

export function RowsSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="flex flex-col gap-6 px-4 lg:px-0" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="flex gap-4"><Skeleton className="h-11 w-11" /><div className="flex-1"><Skeleton className="h-5 w-2/3" /><Skeleton className="mt-2 h-4 w-1/2" /></div></div>
      ))}
    </div>
  );
}

/**
 * The one promoted slot (DESIGN.md §4 "Promoted items"): the normal card of its kind under a "Promoted · {startup}" label, with a "…" for
 * "Why am I seeing this?" and "Hide this". Never styled as a match.
 */
export function PromotedSlot({ promotion, onHide }: { promotion: Promotion; onHide: () => void }) {
  const [menu, setMenu] = useState(false);
  return (
    <div aria-label="Promoted" role="group">
      <div className="flex items-center justify-between gap-4 px-4 lg:px-0">
        <p className="t-subhead text-text-muted">Promoted · {promotion.label}</p>
        <button type="button" onClick={() => setMenu(true)} aria-label="About this promotion" className="-mr-2 flex h-11 w-11 items-center justify-center rounded-full text-text-muted lg:mr-0">
          <MoreHorizontal size={20} strokeWidth={1.75} />
        </button>
      </div>
      {promotion.kind === "role" ? (
        <JobRowItem job={promotion.job} className="pt-1" />
      ) : (
        <Link href={startupHref(promotion.startup.id)} className="flex items-center gap-4 border-b border-separator px-4 pb-4 pt-1 active:opacity-80 lg:px-0">
          <Avatar id={`s${promotion.startup.id}`} name={promotion.startup.name} size={44} shape="square" />
          <span className="min-w-0 flex-1">
            <span className="t-headline block">{promotion.startup.name}</span>
            <span className="t-subhead block text-text-muted">{metaLine(promotion.startup.sector, kmOrNull(promotion.startup.km), promotion.startup.hiring ? "Hiring" : null)}</span>
          </span>
        </Link>
      )}
      <Sheet open={menu} onClose={() => setMenu(false)} title="Why am I seeing this?" detents={["medium"]}>
        <p className="t-body text-text-muted">{promotion.why} Promotions never change your matches or which roles fit you.</p>
        <Button variant="secondary" className="mt-6 w-full" onClick={() => { setMenu(false); onHide(); }}>Hide this</Button>
      </Sheet>
    </div>
  );
}

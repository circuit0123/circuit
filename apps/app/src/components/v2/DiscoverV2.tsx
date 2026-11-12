"use client";

import { Avatar, BannerArt, cx } from "@circuit/ui";
import Link from "next/link";
import { hiringState, kmOrNull, metaLine, roleHref, startupHref, type JobRow, type StartupTile } from "@/data";

type Item<T extends string> = { id: T; label: string };

/** Pill tabs (PMDiscover.dc.html) in place of the segmented control. Same items, same callback. */
export function SegmentTabsV2<T extends string>({ items, value, onChange, label, className }: { items: Item<T>[]; value: T; onChange: (v: T) => void; label: string; className?: string }) {
  return (
    <div role="tablist" aria-label={label} className={cx("flex gap-1.5", className)}>
      {items.map((s) => (
        <button
          key={s.id}
          type="button"
          role="tab"
          aria-selected={value === s.id}
          onClick={() => onChange(s.id)}
          className={cx("h-9 rounded-full border px-3.5 text-[14px] font-semibold", value === s.id ? "border-c-brand bg-c-bright-bg text-c-bright" : "border-c-border bg-c-card text-c-muted")}
        >
          {s.label}
        </button>
      ))}
    </div>
  );
}

/** A startup as a card: its mark, name, sector and distance, and whether it is hiring (read from the real data). */
export function StartupCardV2({ startup }: { startup: StartupTile }) {
  const state = hiringState(startup);
  const hiring = state !== "none";
  const status = state === "roles" ? `Hiring · ${startup.openRoles} ${startup.openRoles === 1 ? "role" : "roles"}` : hiring ? "Hiring" : "Not hiring right now";
  return (
    <Link href={startupHref(startup.id)} className="block min-w-0 overflow-hidden rounded-[20px] border border-c-border bg-c-card">
      <span className="block aspect-[4/3] overflow-hidden"><BannerArt id={`s${startup.id}`} initial={startup.name[0]} src={startup.logo} /></span>
      <span className="block p-3">
        <span className="block truncate text-[17px] font-semibold tracking-[-0.02em]">{startup.name}</span>
        <span className="mt-0.5 block truncate text-[13px] text-c-muted">{metaLine(startup.sector, kmOrNull(startup.km))}</span>
        <span className={cx("mt-2 inline-flex h-6 items-center rounded-md px-2 text-[12px] font-semibold", hiring ? "bg-c-bright-bg text-c-bright" : "bg-c-bg text-c-muted")}>{status}</span>
      </span>
    </Link>
  );
}

/** A role as a card: title, startup · sector · distance, and the stipend. The fit words are left out in v2 (plan §5). */
export function JobRowV2({ job, showStartup = true }: { job: JobRow; showStartup?: boolean }) {
  return (
    <Link href={roleHref(job.id)} data-feed-item className="mx-4 mb-2.5 flex items-end justify-between gap-3 rounded-2xl border border-c-border bg-c-card px-4 py-3.5 lg:mx-0">
      {showStartup && <Avatar id={`s${job.startupId}`} name={job.startup} src={job.logo} size={44} shape="square" className="self-start" />}
      <span className="min-w-0 flex-1">
        <span className="block text-[17px] font-semibold tracking-[-0.02em]">{job.title}</span>
        <span className="mt-0.5 block text-[13px] text-c-muted">{showStartup ? metaLine(job.startup, job.sector, kmOrNull(job.km)) : job.kind}</span>
        {job.applied && <span className="mt-1.5 block font-mono text-[12px] uppercase text-c-muted">Applied</span>}
      </span>
      <span className={cx("shrink-0 text-right font-mono text-[15px] font-medium", job.stipend ? "text-c-bright" : "text-c-muted")}>{job.stipend ?? "Stipend not listed"}</span>
    </Link>
  );
}

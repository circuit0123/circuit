"use client";

import { ExternalLink } from "lucide-react";
import { Chip, EmptyState, ErrorState, GroupedList, ListRow, SegmentedControl, Skeleton, type PostView } from "@circuit/ui";
import Link from "next/link";
import { useState } from "react";
import { postHref, skillLevel, type ChipItem, type Highlight, type ProfileView, type Strength } from "@/data";
import { ROW_INSET } from "../sheets";

/** Offers and Needs as two rows of chips (Person.dc.html). Says nothing when both are empty and `empty` isn't given. */
export function OffersNeeds({ offers, needs, empty, level = 3 }: { offers: ChipItem[]; needs: ChipItem[]; empty?: React.ReactNode; /** Heading level for "Offers" and "Needs": 2 where no section title sits above them. */ level?: 2 | 3 }) {
  if (offers.length === 0 && needs.length === 0) return <>{empty ?? null}</>;
  const H = level === 2 ? "h2" : "h3";
  const row = (label: string, items: ChipItem[]) => items.length > 0 && (
    <div>
      <H className="t-subhead mb-2 text-text-muted">{label}</H>
      <ul className="flex flex-wrap gap-2" aria-label={label}>{items.map((c) => <li key={c.slug}><Chip label={c.name} /></li>)}</ul>
    </div>
  );
  return <div className="flex flex-col gap-4">{row("Offers", offers)}{row("Needs", needs)}</div>;
}

/** Up to 6 pinned projects as rounded tiles (DESIGN.md §4 Profile). */
export function Highlights({ items, level = 3 }: { items: Highlight[]; level?: 2 | 3 }) {
  if (items.length === 0) return null;
  const H = level === 2 ? "h2" : "h3";
  return (
    <div>
      <H className="t-subhead mb-2 text-text-muted">Highlights</H>
      <ul className="no-scrollbar -mx-4 flex gap-3 overflow-x-auto px-4 lg:mx-0 lg:px-0" data-no-swipe aria-label="Highlights">
        {items.slice(0, 6).map((h) => (
          <li key={h.id} className="w-36 shrink-0">
            {/* eslint-disable-next-line @next/next/no-img-element -- Supabase Storage serves the sizes (DESIGN.md §11); next/image is not used in the app */}
            <img src={h.src} alt={h.alt} className="aspect-square w-full rounded-card bg-surface-2 object-cover" />
            <p className="t-subhead mt-2 truncate">{h.title}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The owner-only strength meter (DESIGN.md §4 Profile): how complete the profile is, and one next step. Neutral colours: it is not a
 * score to chase (no streaks, no guilt, §8), so it disappears once everything is in.
 */
export function StrengthMeter({ strength }: { strength: Strength }) {
  if (!strength.next) return null;
  return (
    <div className="rounded-card bg-surface p-4">
      <div className="flex items-baseline justify-between gap-4">
        <p className="t-subhead font-semibold" id="strength-label">Profile strength</p>
        <p className="num t-subhead text-text-muted">{strength.percent}%</p>
      </div>
      <div role="progressbar" aria-labelledby="strength-label" aria-valuemin={0} aria-valuemax={100} aria-valuenow={strength.percent} className="mt-2 h-1.5 overflow-hidden rounded-full bg-surface-3">
        <div className="h-full rounded-full bg-text" style={{ width: `${strength.percent}%` }} />
      </div>
      <Link href={strength.next.href} className="t-subhead mt-3 flex min-h-11 items-center justify-between gap-2 font-semibold">
        <span>Next: {strength.next.label}</span><span aria-hidden className="text-text-muted">›</span>
      </Link>
      <p className="t-footnote text-text-muted">Only you see this.</p>
    </div>
  );
}

/** Build logs as a 3-column grid of first pictures; a text-only log shows its first words. */
export function BuildLogGrid({ posts, isPending, isError, onRetry, empty }: { posts: PostView[]; isPending: boolean; isError: boolean; onRetry: () => void; empty: React.ReactNode }) {
  if (isPending) return <div className="grid grid-cols-3 gap-1" aria-hidden>{[0, 1, 2].map((i) => <Skeleton key={i} className="aspect-square !rounded-md" />)}</div>;
  if (isError) return <ErrorState text="Couldn't load build logs. Check your connection and try again." onRetry={onRetry} />;
  if (posts.length === 0) return <>{empty}</>;
  return (
    <ul className="grid grid-cols-3 gap-1" aria-label="Build logs">
      {posts.map((p) => (
        <li key={p.id}>
          <Link href={postHref(p.id)} aria-label={p.media[0] ? `Build log: ${p.media[0].alt}` : undefined} className="block aspect-square overflow-hidden rounded-md bg-surface-2">
            {p.media[0] ? (
              // eslint-disable-next-line @next/next/no-img-element -- Supabase Storage serves the sizes (DESIGN.md §11); next/image is not used in the app
              <img src={p.media[0].srcSmall} alt="" className="h-full w-full object-cover" />
            ) : (
              <span className="t-footnote line-clamp-5 block p-2 text-text">{p.body}</span>
            )}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** About: what they wrote, where they study or work, and skills with proof-of-work links. */
export function About({ p }: { p: ProfileView }) {
  return (
    <div className="flex flex-col gap-6">
      {p.bio && <p className="t-body max-w-[540px] whitespace-pre-line">{p.bio}</p>}
      {(p.org || p.college) && <p className="t-subhead text-text-muted">{p.org ?? p.college}</p>}
      {p.skills.length > 0 ? (
        <GroupedList header="Skills" className="!px-0">
          {p.skills.map((s) => (
            <ListRow className={ROW_INSET}
              key={s.slug}
              title={s.name}
              subtitle={skillLevel(s.level)}
              trailing={s.proof ? (
                <a href={s.proof} target="_blank" rel="noopener noreferrer nofollow" className="flex min-h-11 items-center gap-1 t-subhead text-text-muted underline">
                  Proof<span className="sr-only"> of work for {s.name}</span><ExternalLink size={14} strokeWidth={1.75} aria-hidden />
                </a>
              ) : undefined}
            />
          ))}
        </GroupedList>
      ) : (
        <p className="t-subhead text-text-muted">No skills added yet.</p>
      )}
    </div>
  );
}

/** Circuits closed (or in progress), one row each. No counts or ratings shown. */
export function CircuitsList({ items, empty }: { items: string[]; empty: string }) {
  if (items.length === 0) return <EmptyState text={empty} />;
  return <GroupedList className="!px-0">{items.map((c, i) => <ListRow className={ROW_INSET} key={i} title={c} />)}</GroupedList>;
}

export type ProfileTab = "logs" | "circuits" | "about";

/** Build logs · Circuits · About (DESIGN.md §4). A tab whose feature is off isn't there; About always is. */
export function ProfileTabs({ logs, circuits, render }: { logs: boolean; circuits: boolean; render: (t: ProfileTab) => React.ReactNode }) {
  const items = [
    ...(logs ? [{ id: "logs" as const, label: "Build logs" }] : []),
    ...(circuits ? [{ id: "circuits" as const, label: "Circuits" }] : []),
    { id: "about" as const, label: "About" },
  ];
  const [tab, setTab] = useState<ProfileTab>(items[0].id);
  const current = items.some((i) => i.id === tab) ? tab : items[0].id;
  return (
    <div>
      {items.length > 1 && <SegmentedControl stretch label="Profile sections" items={items} value={current} onChange={setTab} />}
      <div className="mt-4">{render(current)}</div>
    </div>
  );
}

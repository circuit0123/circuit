"use client";

import { Button, EmptyState, ErrorState, Screen, SearchField, SegmentedControl, useTabSwipeLock } from "@circuit/ui";
import dynamic from "next/dynamic";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import {
  NO_FILTERS, SEGMENTS, activeFilters, applicationsHref, loadFailed, memberHref, useDiscoverJobs, useDiscoverPeople, useDiscoverSearch,
  useDiscoverStartups, useMe, useMyApplications, usePromotion, useSkillsInDemand, type DiscoverFilters, type Segment,
} from "@/data";
import { useAskIntro } from "../home/IntroSheet";
import { FilterSheet } from "./FilterSheet";
import { GridSkeleton, JobRowItem, PersonTileCard, PromotedSlot, RowsSkeleton, StartupTileCard, TileGrid } from "./parts";

/** MapLibre is big: it loads only when the Map segment is first opened (DESIGN.md §11). */
const MapView = dynamic(() => import("./MapView").then((m) => m.MapView), { ssr: false });

const KEY = "circuit.discover.segment";
const isSegment = (s: string | null): s is Segment => SEGMENTS.some((x) => x.id === s);

/**
 * Discover (DESIGN.md §4; Discover.dc.html, People.dc.html, Map.dc.html): one search field over all four segments, then People · Startups ·
 * Jobs · Map. Filters live in a bottom sheet. Students start on Jobs (a role nearby is what they came for), everyone else on People;
 * `?s=` picks one, and the last choice is kept for the session.
 */
export function Discover() {
  const me = useMe().data;
  const path = usePathname();
  const [picked, setPicked] = useState<Segment | null>(null);
  const [filters, setFilters] = useState<DiscoverFilters>(NO_FILTERS);
  const [query, setQuery] = useState("");
  const [sheet, setSheet] = useState(false);

  // On first load and whenever Discover comes back into view (`/discover?s=jobs` from another screen picks Jobs).
  useEffect(() => {
    if (path !== "/discover") return;
    const fromUrl = new URLSearchParams(window.location.search).get("s");
    let saved: string | null = null;
    try { saved = sessionStorage.getItem(KEY); } catch { /* no storage: start fresh */ }
    const s = isSegment(fromUrl) ? fromUrl : isSegment(saved) ? saved : null;
    if (s) setPicked(s); // eslint-disable-line react-hooks/set-state-in-effect
  }, [path]);
  const seg: Segment = picked ?? (me?.role === "student" ? "jobs" : "people");
  const pick = (s: Segment) => {
    setPicked(s);
    try { sessionStorage.setItem(KEY, s); } catch { /* not remembered */ }
  };

  const here = path === "/discover";
  const map = seg === "map";
  useTabSwipeLock(here && map); // the map owns every gesture (DESIGN.md §3)
  const n = activeFilters(filters, seg);
  const filterButton = (
    <button type="button" onClick={() => setSheet(true)} className="-mr-2 min-h-11 shrink-0 rounded-full px-2 t-subhead active:opacity-80 lg:mr-0">
      {n > 0 ? `Filters · ${n}` : "Filters"}
    </button>
  );

  return (
    <>
      {map ? (
        <h1 className="sr-only">Discover</h1>
      ) : (
        <Screen title="Discover">
          <div className="flex flex-col gap-4 px-4 lg:px-0">
            <SearchField placeholder="People, startups, roles" aria-label="Search people, startups and roles" value={query} onChange={(e) => setQuery(e.target.value)} />
            <SegmentedControl stretch label="Discover sections" items={SEGMENTS} value={seg} onChange={pick} />
          </div>
          <div className="mt-section">
            {query.trim() ? (
              <SearchResults query={query} />
            ) : seg === "people" ? (
              <People filters={filters} filterButton={filterButton} />
            ) : seg === "startups" ? (
              <Startups filters={filters} filterButton={filterButton} onClear={() => setFilters(NO_FILTERS)} />
            ) : (
              <Jobs filters={filters} filterButton={filterButton} onClear={() => setFilters(NO_FILTERS)} />
            )}
          </div>
        </Screen>
      )}
      {map && <MapView visible={here} filters={filters} onFilters={setFilters} onOpenFilters={() => setSheet(true)} segment={<SegmentedControl stretch label="Discover sections" items={SEGMENTS} value={seg} onChange={pick} className="material" />} />}
      <FilterSheet open={sheet} onClose={() => setSheet(false)} segment={seg} value={filters} onApply={setFilters} />
    </>
  );
}

function Header({ title, action }: { title: string; action?: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-center justify-between gap-4 px-4 lg:px-0">
      <h2 className="t-headline">{title}</h2>
      {action}
    </div>
  );
}

function People({ filters, filterButton }: { filters: DiscoverFilters; filterButton: React.ReactNode }) {
  const me = useMe().data;
  const people = useDiscoverPeople(filters);
  const ask = useAskIntro();
  return (
    <section aria-label="People">
      <Header title="Near you, matched on skills" action={filterButton} />
      {people.isPending ? <GridSkeleton /> : people.isError ? (
        <ErrorState className="px-4 lg:px-0" text={loadFailed("people")} onRetry={() => people.refetch()} />
      ) : people.items.length === 0 ? (
        <EmptyState className="px-4 lg:px-0" text="No matches here yet. Add what you need and what you can offer, and new people show up each morning." />
      ) : (
        <TileGrid label="People">
          {people.items.map((p) => {
            const href = memberHref(p.id);
            // Under-18 members can't start contact with people they don't know (DESIGN.md §8), so their tiles carry no intro.
            const open = href ? undefined : me?.isMinor ? undefined : () => ask({ id: p.id, name: p.name });
            return <li key={p.id}>{href ? <Link href={href}><PersonTileCard person={p} /></Link> : <PersonTileCard person={p} onOpen={open} />}</li>;
          })}
        </TileGrid>
      )}
    </section>
  );
}

function Startups({ filters, filterButton, onClear }: { filters: DiscoverFilters; filterButton: React.ReactNode; onClear: () => void }) {
  const startups = useDiscoverStartups(filters);
  const promo = usePromotion("startups");
  const [hidden, setHidden] = useState(false);
  return (
    <section aria-label="Startups">
      {promo && !hidden && <div className="mb-8"><PromotedSlot promotion={promo} onHide={() => setHidden(true)} /></div>}
      <Header title="Startups near you" action={filterButton} />
      {startups.isPending ? <GridSkeleton /> : startups.isError ? (
        <ErrorState className="px-4 lg:px-0" text={loadFailed("startups")} onRetry={() => startups.refetch()} />
      ) : startups.items.length === 0 ? (
        <EmptyState className="px-4 lg:px-0" text="No startups match these filters nearby. Try a wider distance." action={activeFilters(filters, "startups") > 0 ? <Button onClick={onClear}>Clear filters</Button> : undefined} />
      ) : (
        <TileGrid label="Startups">{startups.items.map((s) => <li key={s.id}><StartupTileCard startup={s} /></li>)}</TileGrid>
      )}
    </section>
  );
}

function Jobs({ filters, filterButton, onClear }: { filters: DiscoverFilters; filterButton: React.ReactNode; onClear: () => void }) {
  const me = useMe().data;
  const jobs = useDiscoverJobs(filters);
  const skills = useSkillsInDemand();
  const apps = useMyApplications();
  const promo = usePromotion("jobs");
  const [hidden, setHidden] = useState(false);
  const count = apps.data?.length ?? 0;
  return (
    <div className="flex flex-col gap-section">
      {skills.text && (
        <section aria-label="Skills in demand" className="px-4 lg:px-0">
          <h2 className="t-headline mb-3">Skills in demand near you</h2>
          <p className="t-subhead max-w-[540px] text-text-muted">{skills.text}</p>
        </section>
      )}
      <section aria-label="Roles near you">
        {promo && !hidden && <div className="mb-6"><PromotedSlot promotion={promo} onHide={() => setHidden(true)} /></div>}
        <Header title="Roles that fit your skills" action={filterButton} />
        {count > 0 && (
          <Link href={applicationsHref} className="mx-4 mb-2 flex min-h-11 items-center justify-between rounded-control bg-surface px-4 t-body active:opacity-80 lg:mx-0">
            Your applications<span className="num t-subhead text-text-muted">{count}</span>
          </Link>
        )}
        {jobs.isPending ? <RowsSkeleton /> : jobs.isError ? (
          <ErrorState className="px-4 lg:px-0" text={loadFailed("jobs")} onRetry={() => jobs.refetch()} />
        ) : jobs.items.length === 0 ? (
          <EmptyState
            className="px-4 lg:px-0"
            text={me?.isMinor ? "Roles from verified startups near you will show up here." : activeFilters(filters, "jobs") > 0 ? "No roles match these filters yet." : "No open roles near you right now. Follow startups to hear when they hire."}
            action={activeFilters(filters, "jobs") > 0 ? <Button onClick={onClear}>Clear filters</Button> : undefined}
          />
        ) : (
          <ul aria-label="Roles">{jobs.items.map((j) => <li key={j.id}><JobRowItem job={j} /></li>)}</ul>
        )}
      </section>
    </div>
  );
}

/** One search over People, Startups and Roles (the map's pins are the startups). */
function SearchResults({ query }: { query: string }) {
  const r = useDiscoverSearch(query);
  if (r.isPending) return <RowsSkeleton />;
  if (r.isError) return <ErrorState className="px-4 lg:px-0" text={loadFailed("search results")} />;
  const none = r.people.length + r.startups.length + r.jobs.length === 0;
  if (none) return <EmptyState className="px-4 lg:px-0" text={`Nothing matches “${query.trim()}”. Try a skill, a startup or a role.`} />;
  return (
    <div className="flex flex-col gap-section" aria-live="polite">
      {r.jobs.length > 0 && (
        <section aria-label="Roles found">
          <Header title="Roles" />
          <ul>{r.jobs.slice(0, 5).map((j) => <li key={j.id}><JobRowItem job={j} /></li>)}</ul>
        </section>
      )}
      {r.startups.length > 0 && (
        <section aria-label="Startups found">
          <Header title="Startups" />
          <TileGrid label="Startups found">{r.startups.slice(0, 6).map((s) => <li key={s.id}><StartupTileCard startup={s} /></li>)}</TileGrid>
        </section>
      )}
      {r.people.length > 0 && (
        <section aria-label="People found">
          <Header title="People" />
          <TileGrid label="People found">{r.people.slice(0, 6).map((p) => <li key={p.id}><PersonTileCard person={p} /></li>)}</TileGrid>
        </section>
      )}
    </div>
  );
}

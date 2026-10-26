"use client";

import { ChevronRight, MoreHorizontal } from "lucide-react";
import { Avatar, BarButton, Button, EmptyState, ErrorState, PushScreen, Section, Sheet, Skeleton, VerifiedBadge, firstName, useToast } from "@circuit/ui";
import { notFound, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { loadFailed, memberHref, newMessageHref, useIntroPath, useMe, useMemberPosts, useProfile, useFeatures, type PersonView } from "@/data";
import { useAskIntro } from "../home/IntroSheet";
import { goBack } from "../jobs/JobScreen";
import { ConfirmSheet, ReportSheet } from "../sheets";
import { About, BuildLogGrid, CircuitsList, Highlights, OffersNeeds, ProfileTabs } from "./parts";

/**
 * Someone else's profile (Person.dc.html, DESIGN.md §4 Profile): Connect is the one primary action, then Message and "Intro via a mutual"
 * when a warm path exists; offers and needs, highlights, then Build logs · Circuits · About. Only the mutual-connection count is shown,
 * never followers. An under-18 member's profile is private to people they aren't connected to, and strangers can't message them.
 */
export function Person({ id }: { id: number }) {
  const router = useRouter();
  const me = useMe().data;
  const q = useProfile(id);
  const p = q.data;
  const [sheet, setSheet] = useState<null | "menu" | "report" | "block">(null);
  // Your own id goes to your own profile.
  useEffect(() => { if (me && me.id === id) router.replace("/profile"); }, [me, id, router]);
  if (q.notFound) notFound();

  return (
    <PushScreen
      title={p?.name ?? "Profile"}
      onBack={() => goBack(router, "/discover?s=people")}
      right={p && <BarButton label="More: share, report, block" onClick={() => setSheet("menu")}><MoreHorizontal size={22} strokeWidth={1.75} /></BarButton>}
      bleed
    >
      {q.isPending && (
        <div className="px-4 lg:px-0" aria-label="Loading profile">
          <Skeleton round className="h-24 w-24" /><Skeleton className="mt-4 h-10 w-2/3" /><Skeleton className="mt-6 h-12" />
        </div>
      )}
      {q.isError && !q.notFound && <ErrorState className="px-4 pt-6 lg:px-0" text={loadFailed("this profile")} onRetry={() => void q.refetch()} />}
      {p && (p.hidden ? <Private p={p} /> : <Page p={p} connect={(note) => q.connect.mutate(note)} />)}
      {p && <Sheets p={p} sheet={sheet} setSheet={setSheet} report={q.report} block={() => q.block.mutateAsync()} onBlocked={() => router.replace("/")} />}
    </PushScreen>
  );
}

function Head({ p }: { p: PersonView }) {
  const mutuals = p.mutuals ? `${p.mutuals} mutual connection${p.mutuals === 1 ? "" : "s"}` : null;
  return (
    <header>
      <Avatar id={p.id} name={p.name} size={96} />
      <h1 className="t-large mt-4 flex flex-wrap items-center gap-2">{p.name}<VerifiedBadge level={p.level} className="[&>svg]:h-5 [&>svg]:w-5" /></h1>
      <p className="t-subhead mt-1 text-text-muted">{[p.line, mutuals].filter(Boolean).join(" · ")}</p>
      {p.org && <p className="t-subhead text-text-muted">{p.org}</p>}
    </header>
  );
}

function Private({ p }: { p: PersonView }) {
  return (
    <>
      <div className="px-4 lg:px-0"><Head p={{ ...p, line: p.role, org: null }} /></div>
      <Section><EmptyState text="This profile is private." /></Section>
    </>
  );
}

function Page({ p, connect }: { p: PersonView; connect: (note: string) => void }) {
  const router = useRouter();
  const toast = useToast();
  const ask = useAskIntro();
  const features = useFeatures();
  const posts = useMemberPosts(p.id);
  const path = useIntroPath(p.connection === "connected" ? null : p.id);
  const via = path.data?.via ?? null;
  const first = firstName(p.name);

  const connectButton =
    p.connection === "connected" ? <Button disabled aria-disabled>Connected</Button>
      : p.connection === "pending" ? <Button disabled aria-disabled className="text-text-muted">Request sent</Button>
      : <Button variant="primary" onClick={() => { connect(""); toast({ text: `Request sent to ${first}.` }); }}>Connect</Button>;

  return (
    <>
      <div className="px-4 lg:px-0">
        <Head p={p} />
        <div className="mt-5 grid grid-cols-2 gap-3">
          {connectButton}
          <Button disabled={!p.canMessage} onClick={() => router.push(newMessageHref(p.id))}>Message</Button>
        </div>
        {!p.canMessage && <p className="t-footnote mt-2 text-text-muted">{first} only takes messages from connections.</p>}
        {via && (
          <button type="button" onClick={() => ask({ id: p.id, name: p.name })} className="mt-3 flex min-h-11 w-full items-center justify-between t-subhead text-text-muted active:opacity-80">
            Intro via {via.name}, {via.role.toLowerCase()}
            <ChevronRight size={16} strokeWidth={2} aria-hidden />
          </button>
        )}
      </div>

      {(p.offers.length > 0 || p.needs.length > 0 || p.highlights.length > 0) && (
        <Section label="Offers and needs">
          <div className="flex flex-col gap-6"><OffersNeeds level={2} offers={p.offers} needs={p.needs} /><Highlights level={2} items={p.highlights} /></div>
        </Section>
      )}

      <Section label={`${first}'s work`}>
        <ProfileTabs
          logs={posts.on}
          circuits={features.on("circuits") && p.circuits !== null}
          render={(t) =>
            t === "logs" ? (
              <BuildLogGrid posts={posts.posts} isPending={posts.isPending} isError={posts.isError} onRetry={() => void posts.refetch()} empty={<EmptyState text={`${first} hasn't posted a build log yet.`} />} />
            ) : t === "circuits" ? (
              <CircuitsList items={p.circuits ?? []} empty={`No circuits with ${first} yet.`} />
            ) : (
              <About p={p} />
            )
          }
        />
      </Section>
    </>
  );
}

function Sheets({ p, sheet, setSheet, report, block, onBlocked }: {
  p: PersonView; sheet: null | "menu" | "report" | "block"; setSheet: (s: null | "menu" | "report" | "block") => void;
  report: (reason: string) => Promise<unknown>; block: () => Promise<unknown>; onBlocked: () => void;
}) {
  const toast = useToast();
  const first = firstName(p.name);
  const [busy, setBusy] = useState(false);
  const share = async () => {
    const url = `${window.location.origin}${memberHref(p.id)}`;
    setSheet(null);
    try {
      if (navigator.share) { await navigator.share({ title: p.name, url }); return; }
      await navigator.clipboard.writeText(url);
      toast({ text: "Link copied." });
    } catch { /* closed */ }
  };
  return (
    <>
      <Sheet open={sheet === "menu"} onClose={() => setSheet(null)} title={p.name} detents={["medium"]}>
        {!p.hidden && <Button className="w-full" onClick={() => void share()}>Share profile</Button>}
        <Button className="mt-3 w-full" onClick={() => setSheet("report")}>Report {first}</Button>
        <Button variant="destructive" className="mt-3 w-full" onClick={() => setSheet("block")}>Block {first}</Button>
      </Sheet>
      <ReportSheet open={sheet === "report"} onClose={() => setSheet(null)} title={`Report ${first}?`} intro="We'll look at this profile within a day. They won't know who reported them." onSend={report} />
      <ConfirmSheet
        open={sheet === "block"}
        onClose={() => setSheet(null)}
        title={`Block ${first}?`}
        text="You won't see each other's profiles, posts, messages or intro requests any more. You can unblock them in Settings."
        confirmLabel={`Block ${first}`}
        busy={busy}
        onConfirm={async () => {
          setBusy(true);
          try { await block(); setSheet(null); toast({ text: `Blocked ${first}.` }); onBlocked(); }
          catch { toast({ text: "Couldn't block. Try again.", tone: "error" }); }
          finally { setBusy(false); }
        }}
      />
    </>
  );
}

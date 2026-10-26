"use client";

import { useWindowVirtualizer } from "@tanstack/react-virtual";
import { motion, useReducedMotion } from "motion/react";
import { ActivityCard, Sheet, Button, CaughtUp, FeedItem, PartnerItem, PostCard, PromotedItem, RoleCard, Section, Skeleton, spring, useToast, type PostView, type ReactionKind } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useAskIntro } from "./IntroSheet";
import { loadFailed, memberHref, roleHref, useHome, useMarkPulseSeen, usePulse, useReact, useReport, type PulseEntry } from "@/data";

const REASONS = ["Spam or scam", "Harassment or hate", "Misleading or fake", "Something else"];

export function Pulse() {
  const [earlier, setEarlier] = useState(false);
  const q = usePulse(earlier);
  const router = useRouter();
  const toast = useToast();
  const react = useReact();
  const report = useReport();
  const markSeen = useMarkPulseSeen();
  const reduce = useReducedMotion();
  const [menu, setMenu] = useState<number | null>(null);
  const [promo, setPromo] = useState<{ key: string; why: string } | null>(null);
  const { minor } = useHome();
  const ask = useAskIntro();

  // "Skills in demand" belongs at the top of Discover → Jobs (DESIGN.md §4), so it is left out of Pulse.
  const items = q.items.filter((it): it is Exclude<PulseEntry, { kind: "skills" }> => it.kind !== "skills");
  const caughtUp = q.caughtUp;

  const marked = useRef(false);
  useEffect(() => {
    if (caughtUp && !earlier && !marked.current) { marked.current = true; markSeen.mutate(); }
  }, [caughtUp, earlier]); // eslint-disable-line react-hooks/exhaustive-deps

  const [listTop, setListTop] = useState(0);
  const listRef = useCallback((el: HTMLDivElement | null) => { if (el) setListTop(el.offsetTop); }, []);
  const v = useWindowVirtualizer({
    count: items.length,
    estimateSize: () => 640,
    overscan: 4,
    scrollMargin: listTop,
    getItemKey: (i) => items[i].key,
  });
  // Load the next page as the reader nears the end of what we have.
  const last = v.getVirtualItems().at(-1)?.index ?? -1;
  useEffect(() => {
    if (last >= items.length - 3 && q.hasNextPage && !q.isFetchingNextPage) q.fetchNextPage();
  }, [last, items.length, q]);

  if (q.isPending) return <Section bleed label="Pulse"><PulseSkeleton /></Section>;
  if (q.isError) return <Section label="Pulse"><p role="alert" className="t-body text-danger">{loadFailed("Pulse")}</p></Section>;

  // "Intro me" under a post opens the intro sheet; the reaction is recorded once the request is sent.
  const reactTo = (post: PostView) => (kind: ReactionKind, on: boolean) => {
    const save = () => react.mutate({ post: post.id, kind, on }, { onError: () => toast({ text: "Couldn't save that. Try again." }) });
    if (on && kind === "intro_me") ask({ id: post.author.id, name: post.author.name }, save);
    else save();
  };

  const renderItem = (it: (typeof items)[number]) => {
    if (it.kind === "post") {
      return <FeedItem><PostCard post={it.post} onReact={reactTo(it.post)} onMore={() => setMenu(it.post.id)} onOpenAuthor={memberHref(it.post.author.id) ? () => router.push(memberHref(it.post.author.id)!) : undefined} priority={false} hideReactions={minor ? ["intro_me"] : undefined} /></FeedItem>;
    }
    if (it.kind === "role") return <FeedItem><RoleCard role={it.role} onOpen={() => router.push(roleHref(it.role.id))} /></FeedItem>;
    if (it.kind === "promoted") return <FeedItem><PromotedItem startup={it.startup} role={it.role} onOpen={() => router.push(roleHref(it.role.id))} onMenu={() => setPromo({ key: it.key, why: it.why })} /></FeedItem>;
    if (it.kind === "partner") return <FeedItem><PartnerItem org={it.org} text={it.text} /></FeedItem>;
    return <FeedItem><ActivityCard type={it.type} text={it.text} /></FeedItem>;
  };

  return (
    <Section bleed label="Pulse">
      <h2 className="t-headline mb-3 px-4 lg:px-0">Pulse</h2>
      <div ref={listRef} style={{ height: v.getTotalSize(), position: "relative" }}>
        {v.getVirtualItems().map((row) => (
          <div
            key={row.key}
            data-index={row.index}
            ref={v.measureElement}
            style={{ position: "absolute", top: 0, left: 0, width: "100%", transform: `translateY(${row.start - v.options.scrollMargin}px)` }}
          >
            <motion.div
              initial={row.index < 8 ? { opacity: 0, y: reduce ? 0 : 12 } : false}
              animate={{ opacity: 1, y: 0 }}
              transition={reduce ? { duration: 0.15 } : { ...spring, delay: row.index * 0.04 }}
            >
              {renderItem(items[row.index])}
            </motion.div>
          </div>
        ))}
      </div>
      {q.isFetchingNextPage && <PulseSkeleton />}
      {caughtUp && <CaughtUp onDiscover={() => router.push("/discover")} onEarlier={earlier ? undefined : () => setEarlier(true)} />}
      <Sheet open={promo !== null} onClose={() => setPromo(null)} title="Why am I seeing this?">
        <p className="t-body text-text-muted">{promo?.why}</p>
        <Button className="mt-6 w-full" onClick={() => { if (promo) q.hidePromotion(promo.key); setPromo(null); toast({ text: "Hidden. You won't see it again." }); }}>Hide this</Button>
      </Sheet>
      <Sheet open={menu !== null} onClose={() => setMenu(null)} title="Report this post">
        <ul className="flex flex-col gap-2">
          {REASONS.map((r) => (
            <li key={r}>
              <Button
                className="w-full justify-start"
                onClick={() => {
                  report.mutate({ target_type: "post", target_id: menu!, reason: r }, {
                    onSuccess: () => toast({ text: "Reported. Our team will review it." }),
                    onError: () => toast({ text: "Couldn't send the report. Try again." }),
                  });
                  setMenu(null);
                }}
              >
                {r}
              </Button>
            </li>
          ))}
        </ul>
      </Sheet>
    </Section>
  );
}

function PulseSkeleton() {
  return (
    <div className="flex flex-col gap-4 px-4 py-3 lg:px-0" aria-hidden>
      <div className="flex items-center gap-3"><Skeleton round className="h-10 w-10" /><Skeleton className="h-4 w-40" /></div>
      <Skeleton className="aspect-[4/5] w-full rounded-none lg:rounded-card" />
      <Skeleton className="h-4 w-3/4" />
    </div>
  );
}

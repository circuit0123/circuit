"use client";

import { useWindowVirtualizer } from "@tanstack/react-virtual";
import { motion, useReducedMotion } from "motion/react";
import { ActivityCard, BottomSheet, Button, CaughtUp, PostCard, RoleCard, Skeleton, SkillsInDemandCard, spring, useToast, type ReactionKind } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { loadFailed, useMarkPulseSeen, usePulse, useReact, useReport, type PulseEntry } from "@/data";

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

  const items = q.items;
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

  if (q.isPending) return <PulseSkeleton />;
  if (q.isError) return <p role="alert" className="px-4 py-6 t-body text-danger lg:px-0">{loadFailed("Pulse")}</p>;

  const reactTo = (post: number) => (kind: ReactionKind, on: boolean) =>
    react.mutate({ post, kind, on }, {
      onSuccess: () => { if (on && kind === "intro_me") toast({ text: "Marked. They'll see you'd like an intro." }); },
      onError: () => toast({ text: "Couldn't save that. Try again." }),
    });

  const renderItem = (it: PulseEntry) => {
    if (it.kind === "post") {
      return <PostCard post={it.post} onReact={reactTo(it.post.id)} onMore={() => setMenu(it.post.id)} onOpenAuthor={() => router.push(`/members/${it.post.author.id}`)} priority={false} />;
    }
    if (it.kind === "role") return <div className="py-3"><RoleCard role={it.role} onOpen={() => router.push(`/discover/jobs/${it.role.id}`)} /></div>;
    if (it.kind === "activity") return <div className="py-3"><ActivityCard type={it.type} text={it.text} /></div>;
    return <div className="py-3"><SkillsInDemandCard skills={it.skills} /></div>;
  };

  return (
    <section aria-label="Pulse">
      <h2 className="sr-only">Pulse</h2>
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
      <BottomSheet open={menu !== null} onClose={() => setMenu(null)} title="Report this post">
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
      </BottomSheet>
    </section>
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

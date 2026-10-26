"use client";

import { DropSkeleton, DropStack, EmptyState, useToast, type DropStackHandle } from "@circuit/ui";
import { useRef } from "react";
import { loadFailed, useDailyDrop, useSkip } from "@/data";
import { useAskIntro } from "./IntroSheet";

export function DropSection({ className }: { className?: string }) {
  const drop = useDailyDrop();
  const skip = useSkip();
  const ask = useAskIntro();
  const toast = useToast();
  const stack = useRef<DropStackHandle>(null);

  if (drop.isPending) return <DropSkeleton />;
  if (drop.isError) return <p role="alert" className="t-body text-danger">{loadFailed("today's drop")}</p>;
  if (drop.data.cards.length === 0) {
    return <EmptyState className="px-0" text="No new people for you today. Add what you need and what you can offer to get a drop." />;
  }
  return (
    <DropStack
      ref={stack}
      className={className}
      cards={drop.data.cards}
      onSkip={(id) => skip.mutate(id, { onError: () => toast({ text: "Couldn't save that. Try again." }) })}
      onAskIntro={(id) => ask({ id, name: drop.data.cards.find((c) => c.id === id)?.person.name ?? "them", fromDrop: true }, () => stack.current?.introSent(id))}
    />
  );
}

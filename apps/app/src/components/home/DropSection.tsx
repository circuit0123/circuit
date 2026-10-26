"use client";

import { DropSkeleton, DropStack, EmptyState, useToast, type DropStackHandle } from "@circuit/ui";
import { useRef } from "react";
import { loadFailed, useDailyDrop, useRequestIntro, useSkip } from "@/data";

export function DropSection({ className }: { className?: string }) {
  const drop = useDailyDrop();
  const skip = useSkip();
  const intro = useRequestIntro();
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
      onAskIntro={(id) =>
        intro.mutate({ id, fromDrop: true }, {
          onSuccess: () => { stack.current?.introSent(id); toast({ text: "Intro requested. We'll tell you when they reply." }); },
          onError: () => toast({ text: "Couldn't send that. Try again." }),
        })
      }
    />
  );
}

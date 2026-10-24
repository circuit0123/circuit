"use client";

import { DropSkeleton, DropStack, EmptyState, useToast } from "@circuit/ui";
import { loadFailed, useDailyDrop, useSwipe } from "@/data";

export function DropSection({ className }: { className?: string }) {
  const drop = useDailyDrop();
  const swipe = useSwipe();
  const toast = useToast();

  if (drop.isPending) return <DropSkeleton />;
  if (drop.isError) return <p role="alert" className="t-body text-danger">{loadFailed("today's drop")}</p>;
  if (drop.data.cards.length === 0) {
    return <EmptyState className="px-0" text="No new people for you today. Add what you need and what you can offer to get a drop." />;
  }
  return (
    <DropStack
      className={className}
      doneText="That's today's drop. New one tomorrow at 8."
      cards={drop.data.cards}
      onAnswer={(id, direction) =>
        swipe.mutate(
          { id, direction },
          {
            onSuccess: () => { if (direction === "intro") toast({ text: "Intro requested. We'll tell you when they reply." }); },
            onError: () => toast({ text: "Couldn't send that. Try again." }),
          },
        )
      }
    />
  );
}

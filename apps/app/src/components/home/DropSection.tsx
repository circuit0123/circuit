"use client";

import { DropSkeleton, DropStack, EmptyState, useToast } from "@circuit/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useDrop, useSwipe } from "@/hooks/home";
import { roleLabel } from "@/lib/format";
import { toPerson } from "@/lib/map";
import { useSession } from "../Providers";

export function DropSection({ className }: { className?: string }) {
  const drop = useDrop();
  const swipe = useSwipe();
  const toast = useToast();
  const qc = useQueryClient();
  const { token } = useSession();

  if (drop.isPending) return <DropSkeleton />;
  if (drop.isError) return <p role="alert" className="t-body text-danger">Couldn't load today's drop. Check your connection and try again.</p>;
  const d = drop.data;
  if (d.cards.length === 0) {
    return <EmptyState className="px-0" text="No new people for you today. Add what you need and what you can offer to get a drop." />;
  }
  return (
    <DropStack
      className={className}
      doneText="That's today's drop. New one tomorrow at 8."
      cards={d.cards.map((c) => {
        const [lead, ...rest] = c.reason.split(/(?<=\.)\s+/);
        return {
        id: c.member.id,
        person: toPerson(c.member),
        reason: lead,
        detail: rest.join(" "),
        helpWith: c.help_with,
        offers: c.offers_you_need,
        strength: c.strength,
        via: c.via ? { id: c.via.id, name: c.via.display_name, role: roleLabel(c.via.role) } : null,
        image: c.image ? { src: c.image.w1440, alt: c.image.alt } : null,
        bridge: c.is_bridge,
        answered: (c.outcome as "intro" | "skip" | null) ?? null,
        };
      })}
      onAnswer={(id, direction) =>
        swipe.mutate(
          { id, direction },
          {
            onSuccess: () => { if (direction === "intro") toast({ text: "Intro requested. We'll tell you when they reply." }); },
            onError: () => {
              toast({ text: "Couldn't send that. Try again." });
              qc.invalidateQueries({ queryKey: [token, "drop"] });
            },
          },
        )
      }
    />
  );
}

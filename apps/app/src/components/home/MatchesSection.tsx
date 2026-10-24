"use client";

import { MatchCard, Skeleton, useToast } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { loadFailed, useMatches, useRequestIntro } from "@/data";

/** People worth meeting, each with a one-line reason. Shown on Home whatever the flags say. */
export function MatchesSection({ limit = 5, offset = 0, title = "Worth meeting", className }: { limit?: number; offset?: number; title?: string; className?: string }) {
  const q = useMatches({ limit, offset });
  const intro = useRequestIntro();
  const router = useRouter();
  const toast = useToast();
  const [asked, setAsked] = useState<number[]>([]);

  if (q.isPending) {
    return <section aria-label={title} className={className}><Skeleton className="h-36" /></section>;
  }
  if (q.isError) return <p role="alert" className="t-body text-danger">{loadFailed("people for you")}</p>;
  if (q.data.items.length === 0) return null;
  return (
    <section aria-label={title} className={className}>
      <h2 className="t-title3 mb-3">{title}</h2>
      <ul className="flex flex-col gap-3">
        {q.data.items.map((m) => (
          <li key={m.id}>
            <MatchCard
              match={m}
              asked={asked.includes(m.id)}
              onOpen={() => router.push(`/members/${m.id}`)}
              onIntro={() =>
                intro.mutate(m.id, {
                  onSuccess: () => { setAsked((a) => [...a, m.id]); toast({ text: "Intro requested. We'll tell you when they reply." }); },
                  onError: () => toast({ text: "Couldn't send that. Try again." }),
                })
              }
            />
          </li>
        ))}
      </ul>
    </section>
  );
}

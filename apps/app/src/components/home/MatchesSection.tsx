"use client";

import { MatchCard, Section, Skeleton, useToast } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { loadFailed, memberHref, useMatches, useRequestIntro } from "@/data";

/** People worth meeting, each with a one-line reason. Shown on Home whatever the flags say. */
export function MatchesSection({ limit = 5, offset = 0, title = "Worth meeting", className }: { limit?: number; offset?: number; title?: string; className?: string }) {
  const q = useMatches({ limit, offset });
  const intro = useRequestIntro();
  const router = useRouter();
  const toast = useToast();
  const [asked, setAsked] = useState<number[]>([]);

  if (q.isPending) {
    return <Section label={title} className={className}><Skeleton className="h-36" /></Section>;
  }
  if (q.isError) return <Section><p role="alert" className="t-body text-danger">{loadFailed("people for you")}</p></Section>;
  if (q.data.items.length === 0) return null;
  return (
    <Section title={title} className={className}>
      <ul className="flex flex-col">
        {q.data.items.map((m) => (
          <li key={m.id} className="border-b border-separator py-4 first:pt-0 last:border-b-0 last:pb-0">
            <MatchCard
              match={m}
              asked={asked.includes(m.id)}
              onOpen={memberHref(m.id) ? () => router.push(memberHref(m.id)!) : undefined}
              onIntro={() =>
                intro.mutate({ id: m.id }, {
                  onSuccess: () => { setAsked((a) => [...a, m.id]); toast({ text: "Intro requested. We'll tell you when they reply." }); },
                  onError: () => toast({ text: "Couldn't send that. Try again." }),
                })
              }
            />
          </li>
        ))}
      </ul>
    </Section>
  );
}

"use client";

import { StoryViewer, TodayStrip, TodayStripSkeleton, type Story } from "@circuit/ui";
import { useMemo, useState } from "react";
import { useMarkCircleSeen, useMe, useToday } from "@/hooks/home";
import { ago } from "@/lib/format";
import { toPost } from "@/lib/map";

const KIND_LABEL: Record<string, string> = { internship: "Internship", full_time: "Full-time", part_time: "Part-time", contract: "Contract", project: "Project" };

export function TodaySection() {
  const today = useToday();
  const me = useMe().data;
  const seen = useMarkCircleSeen();
  const [openKey, setOpenKey] = useState<string | null>(null);
  const circles = today.data ?? [];
  const current = circles.find((c) => `${c.kind}:${c.id}` === openKey);
  const stories = useMemo<Story[]>(() => {
    if (!current) return [];
    return [
      ...current.posts.map((p) => ({ kind: "post" as const, key: `p${p.id}`, post: toPost(p, me?.id) })),
      ...current.roles.map((r) => ({
        kind: "role" as const,
        key: `r${r.id}`,
        when: ago(r.created_at),
        role: { id: r.id, title: r.title, startup: current.name, place: KIND_LABEL[r.kind] ?? r.kind, km: null, stipend: null, match: null, tags: [] },
      })),
    ];
  }, [current, me?.id]);

  if (today.isPending) return <TodayStripSkeleton />;
  if (today.isError) return <p role="alert" className="t-caption py-3 text-text-muted">Couldn't load Today. Pull to refresh.</p>;
  if (circles.length === 0) return <p className="t-caption py-3 text-text-muted">No one you know has posted today.</p>;
  return (
    <>
      <TodayStrip circles={circles.map((c) => ({ key: `${c.kind}:${c.id}`, name: c.name, seen: c.seen }))} onOpen={setOpenKey} />
      <StoryViewer
        open={!!current}
        name={current?.name ?? ""}
        stories={stories}
        onClose={() => setOpenKey(null)}
        onViewed={() => current && !current.seen && seen.mutate({ id: current.id, kind: current.kind })}
      />
    </>
  );
}

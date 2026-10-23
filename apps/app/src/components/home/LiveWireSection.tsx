"use client";

import { LiveWire, LiveWireSkeleton, UpdateView, useToast } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useLiveWire, useMarkUpdateSeen, useRequestIntro } from "@/hooks/home";

export function LiveWireSection() {
  const wire = useLiveWire();
  const seen = useMarkUpdateSeen();
  const intro = useRequestIntro();
  const router = useRouter();
  const toast = useToast();
  const [open, setOpen] = useState<number | null>(null);
  const items = wire.data ?? [];
  const current = open === null ? undefined : items[open];

  if (wire.isPending) return <LiveWireSkeleton />;
  if (wire.isError) return <p role="alert" className="t-caption py-3 text-text-muted">Couldn't load the Live wire. Check your connection and try again.</p>;

  const show = (i: number | null) => {
    if (i !== null && items[i] && !items[i].seen) seen.mutate(items[i].key);
    setOpen(i);
  };
  return (
    <>
      <LiveWire updates={items} onOpen={show} onEmptyAction={() => router.push("/discover")} />
      <UpdateView
        open={current !== undefined}
        updates={items}
        index={open ?? 0}
        onIndex={show}
        onClose={() => setOpen(null)}
        onAction={(u) => {
          const { action } = items.find((x) => x.key === u.key)!;
          if (action.kind === "view_role") router.push(`/discover/jobs/${action.target_id}`);
          else if (action.kind === "reply") router.push("/inbox");
          else
            intro.mutate(action.target_id, {
              onSuccess: () => toast({ text: "Intro requested. We'll tell you when they reply." }),
              onError: () => toast({ text: "Couldn't send that. Try again." }),
            });
        }}
      />
    </>
  );
}

"use client";

import { LiveWire, LiveWireSkeleton, UpdateView, useToast } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useLiveWire, useMarkCircleSeen, useRequestIntro } from "@/hooks/home";

export function LiveWireSection() {
  const wire = useLiveWire();
  const seen = useMarkCircleSeen();
  const intro = useRequestIntro();
  const router = useRouter();
  const toast = useToast();
  const [open, setOpen] = useState<number | null>(null);
  const items = wire.data ?? [];
  const current = open === null ? undefined : items[open];

  if (wire.isPending) return <LiveWireSkeleton />;
  if (wire.isError) return <p role="alert" className="t-caption py-3 text-text-muted">Couldn't load the Live wire. Check your connection and try again.</p>;

  const close = () => {
    if (current) seen.mutate(current.circle);
    setOpen(null);
  };
  return (
    <>
      <LiveWire updates={items} onOpen={setOpen} onEmptyAction={() => router.push("/discover")} />
      <UpdateView
        open={current !== undefined}
        updates={items}
        index={open ?? 0}
        onIndex={(i) => { if (current) seen.mutate(current.circle); setOpen(i); }}
        onClose={close}
        onAction={(u) => {
          const it = items.find((x) => x.key === u.key)!;
          if (it.action.kind === "view_role") { router.push(`/discover/jobs/${it.action.target_id}`); return; }
          intro.mutate(it.action.target_id, {
            onSuccess: () => toast({ text: "Intro requested. We'll tell you when they reply." }),
            onError: () => toast({ text: "Couldn't send that. Try again." }),
          });
        }}
      />
    </>
  );
}

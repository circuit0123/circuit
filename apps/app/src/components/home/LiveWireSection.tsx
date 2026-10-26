"use client";

import { LiveWire, LiveWireSkeleton, UpdateView, useToast } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { composeHref, loadFailed, useLiveWire, useMarkUpdateSeen, useRequestIntro, wireActionHref } from "@/data";

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
  if (wire.isError) return <p role="alert" className="t-footnote py-3 text-text-muted">{loadFailed("the Live wire")}</p>;

  const show = (i: number | null) => {
    if (i !== null && items[i] && !items[i].seen) seen.mutate(items[i].key);
    setOpen(i);
  };
  return (
    <>
      <LiveWire updates={items} onOpen={show} onEmptyAction={() => (composeHref ? router.push(composeHref) : toast({ text: "The build log composer is coming next." }))} />
      <UpdateView
        open={current !== undefined}
        updates={items}
        index={open ?? 0}
        onIndex={show}
        onClose={() => setOpen(null)}
        onAction={(u) => {
          const { action } = items.find((x) => x.key === u.key)!;
          const href = wireActionHref(action);
          if (href) router.push(href);
          else
            intro.mutate({ id: action.target_id }, {
              onSuccess: () => toast({ text: "Intro requested. We'll tell you when they reply." }),
              onError: () => toast({ text: "Couldn't send that. Try again." }),
            });
        }}
      />
    </>
  );
}

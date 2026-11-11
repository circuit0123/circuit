"use client";

import { LiveWire, LiveWireSkeleton, UpdateView, spokenUpdate, useToast } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { composeHref, loadFailed, useHome, useLiveWire, useMarkUpdateSeen, wireActionHref } from "@/data";
import { useAskIntro } from "./IntroSheet";

/** `pill` (ui_v2): a one-line LIVE strip above the wire, from the newest real update. No updates, no pill. */
export function LiveWireSection({ pill }: { pill?: boolean }) {
  const wire = useLiveWire();
  const seen = useMarkUpdateSeen();
  const ask = useAskIntro();
  const router = useRouter();
  const toast = useToast();
  const { minor } = useHome();
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
      {pill && items[0] && (
        <button type="button" onClick={() => show(0)} className="mb-3 flex h-8 w-full items-center gap-2 rounded-full border border-c-border bg-c-card px-3 text-left text-[12px] text-c-text">
          <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-c-bright" />
          <span className="font-mono text-c-muted">LIVE</span>
          <span className="min-w-0 flex-1 truncate">{spokenUpdate(items[0])}</span>
          <span className="shrink-0 font-mono text-c-muted">{items[0].when}</span>
        </button>
      )}
      <LiveWire updates={items} onOpen={show} onEmptyAction={() => (composeHref ? router.push(composeHref) : toast({ text: "The build log composer is coming next." }))} />
      <UpdateView
        open={current !== undefined}
        updates={items}
        index={open ?? 0}
        onIndex={show}
        onClose={() => setOpen(null)}
        hideAction={(u) => minor && items.find((x) => x.key === u.key)?.action.kind === "intro"}
        onAction={(u) => {
          const { action } = items.find((x) => x.key === u.key)!;
          const href = wireActionHref(action);
          if (href) router.push(href);
          else {
            setOpen(null); // one sheet at a time: the Update view steps aside for the confirm sheet
            ask({ id: action.target_id, name: u.person.name });
          }
        }}
      />
    </>
  );
}

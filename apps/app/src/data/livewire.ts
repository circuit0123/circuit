import type { Schemas } from "@circuit/api-client";
import type { WireUpdate } from "@circuit/ui";
import { ago } from "@/lib/format";

type Item = Schemas["WireItemOut"];
export type LiveWireItem = WireUpdate & { action: Item["action"] };

const LABEL: Record<Item["action"]["kind"], string> = { intro: "Intro me", view_role: "View role", reply: "Reply" };
const VERB: Record<Item["kind"], WireUpdate["verb"]> = {
  shipped: "shipped", hiring: "hiring", needs: "needs", joined: "joined", circuit_closed: "closed a circuit",
};

/** A Live wire item from the API as the UI package draws it. */
export function toUpdate(it: Item): LiveWireItem {
  const who = it.actor
    ? { id: it.actor.id, name: it.actor.display_name, level: it.actor.verification_level }
    : { id: it.startup?.id ?? 0, name: it.startup?.name ?? "", level: 0 };
  const visual: WireUpdate["visual"] = it.image
    ? { kind: "image", src: it.image.w1440, alt: it.image.alt }
    : it.kind === "circuit_closed"
      ? { kind: "circuit" }
      : { kind: "pattern", id: it.actor ? it.actor.id : `startup-${it.startup?.id}` };
  return {
    key: it.key,
    verb: VERB[it.kind],
    visual,
    person: who,
    seen: it.seen,
    when: ago(it.created_at),
    headline: it.headline,
    reason: it.reason,
    actionLabel: LABEL[it.action.kind],
    action: it.action,
  };
}

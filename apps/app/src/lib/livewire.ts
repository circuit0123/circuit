import type { Schemas } from "@circuit/api-client";
import type { WireUpdate } from "@circuit/ui";
import { ago } from "./format";

/**
 * The shape the Live wire endpoint will return (LAUNCH.md Stage 3b, backend list). Until it exists, `fromToday`
 * builds the same items from /api/today. Delete the adapter when the endpoint lands.
 */
export type LiveWireAction = { kind: "intro" | "view_role" | "reply"; target_id: number };
export type LiveWireItem = WireUpdate & { action: LiveWireAction; circle: { id: number; kind: "member" | "startup" } };

// TODO(livewire-endpoint): replace with GET /api/livewire.
export function fromToday(circles: Schemas["CircleOut"][]): LiveWireItem[] {
  const out: LiveWireItem[] = [];
  for (const c of circles) {
    const circle = { id: c.id, kind: c.kind };
    const post = c.posts[0];
    if (c.kind === "member" && c.author && post) {
      const m = post.media[0];
      out.push({
        key: `shipped:${post.id}`,
        verb: "shipped",
        visual: m ? { kind: "image", src: m.w1440, alt: m.alt_text } : { kind: "pattern", id: c.author.id },
        person: { id: c.author.id, name: c.author.display_name, level: c.author.verification_level },
        seen: c.seen,
        when: ago(c.latest_at),
        headline: post.body.length > 90 ? `${post.body.slice(0, 87).trimEnd()}...` : post.body,
        reason: [c.author.headline, c.author.city].filter(Boolean).join(" · "),
        actionLabel: "Intro me",
        action: { kind: "intro", target_id: c.author.id },
        circle,
      });
    } else if (c.kind === "startup" && c.roles[0]) {
      const r = c.roles[0];
      out.push({
        key: `hiring:${r.id}`,
        verb: "hiring",
        visual: { kind: "pattern", id: `startup-${c.id}` },
        person: { id: c.id, name: c.name, level: 0 },
        seen: c.seen,
        when: ago(c.latest_at),
        headline: `${c.name} is hiring: ${r.title}`,
        reason: ago(r.created_at) === "now" ? "Posted just now" : `Posted ${ago(r.created_at)} ago`,
        actionLabel: "View role",
        action: { kind: "view_role", target_id: r.id },
        circle,
      });
    }
  }
  return out;
}

import type { Schemas } from "@circuit/api-client";
import type { MediaItem, Person, PostView, RoleView } from "@circuit/ui";
import { ago, rupees, roleLabel } from "@/lib/format";

export function toPerson(a: Schemas["AuthorOut"]): Person {
  return { id: a.id, name: a.display_name, role: roleLabel(a.role), headline: a.headline, place: a.city, level: a.verification_level };
}

export function toPost(p: Schemas["PostOut"], meId: number | undefined): PostView {
  const media: MediaItem[] = p.media.map((m) => ({ src: m.w1440, srcSmall: m.w480, alt: m.alt_text, width: m.width ?? null, height: m.height ?? null }));
  return {
    id: p.id,
    author: toPerson(p.author),
    body: p.body,
    tags: p.capabilities.map((c) => c.name),
    link: p.link,
    media,
    when: ago(p.created_at),
    mine: p.author.id === meId,
    reactions: p.my_reactions as PostView["reactions"],
  };
}

export function toRole(j: Schemas["JobOut"]): RoleView {
  return {
    id: j.id,
    title: j.title,
    startup: j.startup_name,
    place: j.location,
    km: j.distance_km ?? null,
    stipend: rupees(j.stipend_min, j.stipend_max),
    match: j.skill_match === null || j.skill_match === undefined ? null : Math.round(j.skill_match * 100),
    tags: j.capabilities.filter((c) => c.required).map((c) => c.name),
  };
}

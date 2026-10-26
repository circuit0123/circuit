/**
 * Where a tap goes. One map for notifications, Live wire actions and the `+` button. Each entry points at its real screen once that
 * screen exists; until then it points at the nearest tab, so a tap never lands on a 404. When a session builds a screen, change its line here.
 */
import type { Schemas } from "@circuit/api-client";

type Target = Schemas["TargetOut"];

/** A notification's `target` (what the API says to open) as an app path. */
export function notificationHref(target: Target | null | undefined): string {
  switch (target?.type) {
    case "intro": return "/inbox"; // F5: Inbox → Requests
    case "conversation": return "/inbox"; // F5: /inbox/{id}
    case "circuit": return "/inbox"; // F5: Circuits tab; until then nothing of its own
    case "application": return "/discover"; // F4: /discover/jobs/applications
    case "startup": return "/discover"; // F4: /startups/{id}
    case "post": return "/"; // F6: /posts/{id}
    default: return "/";
  }
}

/** The one action on a Live wire update. `intro` is handled by the intro sheet, not a path. */
export function wireActionHref(action: { kind: "intro" | "view_role" | "reply"; target_id: number }): string | null {
  if (action.kind === "view_role") return "/discover"; // F4: /discover/jobs/{id}
  if (action.kind === "reply") return "/inbox"; // F5: /inbox/{member}
  return null;
}

/** The `+` in the top bar. Null until F6 builds the composer; the caller says so in a toast. */
export const composeHref: string | null = null; // F6: "/compose"

/** A role's page. F4 builds `/discover/jobs/{id}`; until then the Discover tab. */
export const roleHref = (_id: number): string => "/discover"; // F4: `/discover/jobs/${id}`

/** Someone's profile. Null until F6 builds it, so the name simply isn't a link yet. */
export const memberHref = (_id: number): string | null => null; // F6: `/members/${id}`

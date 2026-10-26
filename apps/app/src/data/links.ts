/**
 * Where a tap goes. One map for notifications, Live wire actions and the `+` button. Each entry points at its real screen once that
 * screen exists; until then it points at the nearest tab, so a tap never lands on a 404. When a session builds a screen, change its line here.
 */
import type { Schemas } from "@circuit/api-client";

type Target = Schemas["TargetOut"];

/** A notification's `target` (what the API says to open) as an app path. */
export function notificationHref(target: Target | null | undefined): string {
  switch (target?.type) {
    case "intro": return "/inbox";
    case "conversation": return conversationHref(target.id);
    case "circuit": return circuitsHref;
    case "application": return "/discover/applications";
    case "startup": return startupHref(target.id);
    case "post": return postHref(target.id);
    default: return "/";
  }
}

/** The one action on a Live wire update. `intro` is handled by the intro sheet, not a path. */
export function wireActionHref(action: { kind: "intro" | "view_role" | "reply"; target_id: number }): string | null {
  if (action.kind === "view_role") return roleHref(action.target_id);
  if (action.kind === "reply") return newMessageHref(action.target_id);
  return null;
}

/** The `+` in the top bar: the build log composer. */
export const composeHref: string | null = "/compose";

/** A role's page. */
export const roleHref = (id: number): string => `/discover/jobs/${id}`;

/** A startup's page; `hiring` lands on its Hiring section (the map sheet's "See open roles"). */
export const startupHref = (id: number, hiring = false): string => `/startups/${id}${hiring ? "#hiring" : ""}`;

/** A role's applicants (founders of that startup only). */
export const applicantsHref = (jobId: number): string => `/discover/jobs/${jobId}/applicants`;

/** "My applications". */
export const applicationsHref = "/discover/applications";

/** Someone's profile. */
export const memberHref = (id: number): string | null => `/members/${id}`;

/** One build log. */
export const postHref = (id: number): string => `/posts/${id}`;

/** Settings, or one of its screens ("privacy", "appearance", …). */
export const settingsHref = (screen?: string): string => (screen ? `/settings/${screen}` : "/settings");

/** The Circuits tab (only there while the `circuits` flag is on; the server sends no circuit notifications otherwise). */
export const circuitsHref = "/circuits";

/** One conversation. */
export const conversationHref = (id: number): string => `/inbox/${id}`;

/** A new message to someone (opens their existing conversation if there is one). */
export const newMessageHref = (memberId: number): string => `/inbox/new?to=${memberId}`;

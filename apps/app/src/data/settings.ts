"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { Schemas } from "@circuit/api-client";
import { roleLabel } from "@/lib/format";
import { ACCENTS } from "@circuit/ui";
import { api, ApiError, unwrap } from "./client";
import { useKey } from "./keys";
import { useSession } from "./session";

type Settings = Schemas["SettingsOut"];
export type NotificationType = Exclude<keyof Schemas["NotificationPrefsOut"], "push_daily_cap" | "quiet_hours" | "quiet_hours_locked">;
export type Channel = "in_app" | "email";
export type ProfileVisibility = "public" | "members" | "hidden";

/** The six notification types, in the words Settings shows (DESIGN.md §8: every type can be turned off). */
export const NOTIFICATION_TYPES: Array<{ id: NotificationType; label: string; hint: string }> = [
  { id: "intros", label: "Intros", hint: "Someone asks for an intro, or yours is answered" },
  { id: "messages", label: "Messages", hint: "New messages and message requests" },
  { id: "applications", label: "Applications", hint: "Updates on roles you applied to" },
  { id: "circuits", label: "Circuits", hint: "A circuit is proposed, closes or needs you" },
  { id: "pulse_replies", label: "Replies", hint: "Replies to your build logs" },
  { id: "announcements", label: "Announcements", hint: "From your organisation, at most one a day" },
];

export const VISIBILITY_OPTIONS: Array<{ id: ProfileVisibility; label: string; hint: string }> = [
  { id: "public", label: "Everyone", hint: "Anyone on Circuit can find and see your profile." },
  { id: "members", label: "Members", hint: "Signed-in members can see your profile." },
  { id: "hidden", label: "Hidden", hint: "Only your connections see your profile." },
];

const themeWord = { system: "System", dark: "Dark", light: "Light" } as const;

/**
 * Everything the Settings screens show, in one call (GET /api/me/settings): the hub's row values come ready to draw. Changes go through
 * the hooks below, which update this cache at once and put the old value back if saving fails.
 */
export function useSettings() {
  const { key, enabled } = useKey("settings");
  const q = useQuery({ queryKey: key, enabled, queryFn: () => unwrap(api.GET("/api/me/settings")) });
  const s = q.data;
  const on = s ? NOTIFICATION_TYPES.filter((t) => s.notifications[t.id].in_app || s.notifications[t.id].email) : [];
  const summary = s && {
    name: s.profile.display_name,
    line: [roleLabel(s.profile.role), s.profile.city].filter(Boolean).join(" · "),
    emailHint: s.profile.email_hint,
    minor: s.profile.is_minor,
    level: s.profile.verification_level,
    privacy: VISIBILITY_OPTIONS.find((v) => v.id === s.privacy.profile_visibility)?.label ?? "",
    notifications: on.length === 0 ? "Off" : on.length === NOTIFICATION_TYPES.length ? "All on" : on.slice(0, 2).map((t, i) => (i === 0 ? t.label : t.label.toLowerCase())).join(", ") + (on.length > 2 ? ", more" : ""),
    appearance: `${themeWord[s.appearance.theme]} · ${ACCENTS.find((a) => a.id === s.appearance.accent)?.label ?? ""}`,
    blocked: s.blocked_count,
    policyVersion: s.consent.accepted_version ?? s.consent.policy_version,
    support: s.support,
    export: s.export,
  };
  return { data: s, summary, isPending: q.isPending, isError: q.isError, refetch: q.refetch };
}

/** Patches one part of the settings cache optimistically; rolls back on failure. */
function useOptimistic<T>(part: (s: Settings, v: T) => Settings, call: (v: T) => Promise<unknown>) {
  const qc = useQueryClient();
  const { key } = useKey("settings");
  return useMutation({
    mutationFn: call,
    onMutate: (v: T) => {
      const before = qc.getQueryData<Settings>(key);
      if (before) qc.setQueryData(key, part(before, v));
      return { before };
    },
    onError: (_e, _v, ctx) => { if (ctx?.before) qc.setQueryData(key, ctx.before); },
    onSettled: () => { qc.invalidateQueries({ queryKey: key }); qc.invalidateQueries({ queryKey: ["me"] }); },
  });
}

export type PrivacyPatch = Schemas["PrivacyPatch"];

/**
 * Privacy toggles. Under-18 members can never make the profile public or take requests from strangers: those rows are `locked` (the server
 * answers 403 `under_18_restricted` anyway). Showing up in circuits needs work verification (level 2).
 */
export function usePrivacy() {
  const save = useOptimistic<PrivacyPatch>(
    (s, v) => ({ ...s, privacy: { ...s.privacy, ...Object.fromEntries(Object.entries(v).filter(([, x]) => x !== null && x !== undefined)) } }),
    (v) => unwrap(api.PATCH("/api/me/privacy", { body: v })),
  );
  const problem = save.error instanceof ApiError && save.error.code === "under_18_restricted" ? "That isn't available for under-18 accounts." : save.error ? "Couldn't save that. Try again." : null;
  return { save, problem };
}

/** Notifications per type × channel (in the app, by email). */
export function useNotificationPrefs() {
  const save = useOptimistic<{ type: NotificationType; channel: Channel; on: boolean }>(
    (s, { type, channel, on }) => ({ ...s, notifications: { ...s.notifications, [type]: { ...s.notifications[type], [channel]: on } } }),
    ({ type, channel, on }) => unwrap(api.PATCH("/api/me/notification-preferences", { body: { [type]: { [channel]: on } } })),
  );
  return { save };
}

/** People you blocked, with Unblock. */
export function useBlocks() {
  const qc = useQueryClient();
  const { key, enabled } = useKey("blocks");
  const q = useQuery({ queryKey: key, enabled, queryFn: async () => (await unwrap(api.GET("/api/me/blocks"))).items });
  const unblock = useMutation({
    mutationFn: (id: number) => unwrap(api.DELETE("/api/members/{member_id}/block", { params: { path: { member_id: id } } })),
    onMutate: (id) => { qc.setQueryData<Schemas["PersonOut"][]>(key, (old) => old?.filter((p) => p.id !== id)); },
    onError: () => qc.invalidateQueries({ queryKey: key }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["settings"] }),
  });
  return { people: (q.data ?? []).map((p) => ({ id: p.id, name: p.display_name, role: roleLabel(p.role), level: p.verification_level })), isPending: q.isPending, isError: q.isError, refetch: q.refetch, unblock };
}

export type ExportState =
  | { kind: "none" }
  | { kind: "preparing"; requestedAt: string }
  | { kind: "ready"; expiresAt: string | null }
  | { kind: "expired" };

const exportStateOf = (e: Schemas["ExportStatus"] | null | undefined): ExportState => {
  if (!e) return { kind: "none" };
  if (e.status === "ready") return e.expires_at && new Date(e.expires_at) < new Date() ? { kind: "expired" } : { kind: "ready", expiresAt: e.expires_at };
  if (e.status === "expired") return { kind: "expired" };
  if (e.status === "failed") return { kind: "none" };
  return { kind: "preparing", requestedAt: e.requested_at };
};

/** Export my data: ask for it, then "preparing", then an email link. One open at a time, 3 a day. */
export function useExport() {
  const qc = useQueryClient();
  const { key, enabled } = useKey("export");
  const q = useQuery({
    queryKey: key,
    enabled,
    queryFn: async () => (await unwrap(api.GET("/api/me/export"))) as Schemas["ExportStatus"] | null,
    refetchInterval: (query) => (exportStateOf(query.state.data).kind === "preparing" ? 15_000 : false),
  });
  const request = useMutation({
    mutationFn: () => unwrap(api.POST("/api/me/export")),
    onSuccess: (e) => { qc.setQueryData(key, e); qc.invalidateQueries({ queryKey: ["settings"] }); },
  });
  const problem = request.error instanceof ApiError && (request.error.status === 429 || request.error.code === "rate_limited") ? "You've asked for your data three times today. Try again tomorrow." : request.error ? "Couldn't ask for your data. Try again." : null;
  return { state: exportStateOf(q.data), isPending: q.isPending, isError: q.isError, refetch: q.refetch, request, problem };
}

/** The download link from the export email (`/settings/export?token=`). 404: someone else's link; 410: it has expired. */
export function useExportDownload(token: string | null) {
  const { key, enabled } = useKey("export-download", token);
  const q = useQuery({
    queryKey: key,
    enabled: enabled && !!token,
    retry: false,
    queryFn: () => unwrap(api.GET("/api/me/export/download", { params: { query: { token: token! } } })),
  });
  const err = q.error as ApiError | null;
  const failure = !err ? null : err.status === 410 || err.code === "export_expired" ? "expired" : err.status === 404 ? "not_yours" : "failed";
  return { link: q.data ? { url: q.data.url, sizeBytes: q.data.size_bytes } : null, isPending: !!token && q.isPending, failure: failure as null | "expired" | "not_yours" | "failed", refetch: q.refetch };
}

/** Delete account: the typed word is checked here and by the server; then the session ends. Every later call would be 403 `account_deleted`. */
export const DELETE_WORD = "DELETE" as const;
export function useDeleteAccount() {
  const { signOut } = useSession();
  return useMutation({
    mutationFn: (typed: string) => unwrap(api.POST("/api/me/deletion", { body: { confirm: typed.trim() as typeof DELETE_WORD } })),
    onSuccess: () => signOut(),
  });
}

export type SupportKind = "question" | "correction" | "data_request" | "grievance";
export const SUPPORT_KINDS: Array<{ id: SupportKind; label: string }> = [
  { id: "question", label: "Question" },
  { id: "correction", label: "Correction" },
  { id: "data_request", label: "My data" },
  { id: "grievance", label: "Complaint" },
];

/** Contact support. Returns a reference to quote. 5 a day. */
export function useSupport() {
  return useMutation({
    mutationFn: (b: { kind: SupportKind; message: string }) => unwrap(api.POST("/api/support", { body: { kind: b.kind, message: b.message.trim() } })),
  });
}

/** Sign out: the session ends here and on Supabase; the cache is cleared with it. */
export function useSignOut() {
  const { signOut } = useSession();
  return useMutation({ mutationFn: () => signOut() });
}

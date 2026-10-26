"use client";

import { ErrorState, Skeleton, Toggle, useToast } from "@circuit/ui";
import { NOTIFICATION_TYPES, loadFailed, useNotificationPrefs, useSettings } from "@/data";
import { SettingsScreen } from "./SettingsHome";

/**
 * Notifications per type × channel (in the app, by email). Every type can be turned off (DESIGN.md §8). One grid: a row per type, a
 * column per channel, and every switch says both out loud ("Intros by email").
 */
export function Notifications() {
  const toast = useToast();
  const s = useSettings();
  const { save } = useNotificationPrefs();
  const n = s.data?.notifications;
  return (
    <SettingsScreen title="Notifications">
      {s.isError && !n && <ErrorState className="px-4 lg:px-0" text={loadFailed("your notification settings")} onRetry={() => void s.refetch()} />}
      {!n && !s.isError && <div className="px-4 lg:px-0" aria-label="Loading notifications"><Skeleton className="h-96" /></div>}
      {n && (
        <section className="px-4 lg:px-0" aria-label="Notification settings">
          <div className="overflow-hidden rounded-group bg-surface">
            <div className="flex items-center gap-4 px-4 pb-1 pt-3" aria-hidden>
              <span className="flex-1" />
              <span className="t-footnote w-[51px] text-center text-text-muted">App</span>
              <span className="t-footnote w-[51px] text-center text-text-muted">Email</span>
            </div>
            <ul>
              {NOTIFICATION_TYPES.map((t, i) => (
                <li key={t.id} className={i > 0 ? "ml-4 border-t border-separator" : undefined}>
                  <div className={`flex min-h-row-sub items-center gap-4 py-2 pr-4 ${i > 0 ? "" : "pl-4"}`}>
                    <span className="min-w-0 flex-1">
                      <span className="t-body block">{t.label}</span>
                      <span className="t-subhead block text-text-muted">{t.hint}</span>
                    </span>
                    {(["in_app", "email"] as const).map((ch) => (
                      <Toggle
                        key={ch}
                        label={`${t.label} ${ch === "in_app" ? "in the app" : "by email"}`}
                        checked={n[t.id][ch]}
                        onChange={(on) => save.mutate({ type: t.id, channel: ch, on }, { onError: () => toast({ text: "Couldn't save that. Try again.", tone: "error" }) })}
                      />
                    ))}
                  </div>
                </li>
              ))}
            </ul>
          </div>
          <p className="t-footnote mt-2 px-4 text-text-muted">Notices from the Circuit team about your account always show in the app. Push stays under 3 a day and quiet from 10 pm to 8 am.</p>
        </section>
      )}
    </SettingsScreen>
  );
}

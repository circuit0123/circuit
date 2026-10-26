"use client";

import { Avatar, EmptyState, ErrorState, GroupedList, ListRow, Skeleton, useToast } from "@circuit/ui";
import { loadFailed, useBlocks } from "@/data";
import { ROW_INSET } from "../sheets";
import { SettingsScreen } from "./SettingsHome";

/** People you blocked, with Unblock. They aren't told either way. */
export function Blocked() {
  const toast = useToast();
  const b = useBlocks();
  return (
    <SettingsScreen title="Blocked people" backLabel="Privacy" back="/settings/privacy">
      {b.isPending && <div className="px-4 lg:px-0" aria-label="Loading blocked people"><Skeleton className="h-28" /></div>}
      {b.isError && <ErrorState className="px-4 lg:px-0" text={loadFailed("blocked people")} onRetry={() => void b.refetch()} />}
      {!b.isPending && !b.isError && b.people.length === 0 && <EmptyState className="px-4 lg:px-0" text="You haven't blocked anyone." />}
      {b.people.length > 0 && (
        <GroupedList footer="They can't see your profile, posts or messages, or ask you for intros. Unblocking doesn't tell them.">
          {b.people.map((p) => (
            <ListRow className={ROW_INSET}
              key={p.id}
              title={p.name}
              subtitle={p.role}
              leading={<Avatar id={p.id} name={p.name} size={40} />}
              trailing={
                <button
                  type="button"
                  onClick={() => b.unblock.mutate(p.id, { onSuccess: () => toast({ text: `Unblocked ${p.name}.` }), onError: () => toast({ text: "Couldn't unblock. Try again.", tone: "error" }) })}
                  className="min-h-11 rounded-full bg-surface-2 px-4 t-subhead font-semibold active:opacity-80"
                >
                  Unblock<span className="sr-only"> {p.name}</span>
                </button>
              }
            />
          ))}
        </GroupedList>
      )}
    </SettingsScreen>
  );
}

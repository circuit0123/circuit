"use client";

import { EmptyState, Screen } from "@circuit/ui";

export function Inbox() {
  return <Screen title="Inbox"><EmptyState className="px-0" text="Chats arrive in a later step." /></Screen>;
}

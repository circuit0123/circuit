"use client";

import { EmptyState, Screen, Section } from "@circuit/ui";

export function Inbox() {
  return <Screen title="Inbox"><Section><EmptyState text="Chats arrive in a later step." /></Section></Screen>;
}

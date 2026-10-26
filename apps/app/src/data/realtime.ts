"use client";

import { useEffect, useRef } from "react";
import { useKey } from "./keys";
import { on } from "./mocks/bus";
import { MOCK } from "./mocks/config";
import { getSupabase } from "./supabase";

type Payload = Record<string, unknown>;

/**
 * Listens to one private Realtime Broadcast topic (`circuit:<id>`, `conversation:<id>`). Only ids travel over a channel; the caller
 * refetches through the API, so permissions are checked there. In mock mode it listens to the mock bus (mocks/bus.ts). Without a
 * Supabase session (dev personas) it does nothing and the caller's polling covers it. `topic: null` listens to nothing.
 */
export function useChannel(topic: string | null, event: string, onEvent: (payload: Payload) => void) {
  useChannels(topic ? [topic] : [], event, onEvent);
}

/** The same for several topics at once (the Inbox listens to every conversation it lists). */
export function useChannels(topics: string[], event: string, onEvent: (payload: Payload) => void) {
  const { token } = useKey();
  const latest = useRef(onEvent);
  useEffect(() => { latest.current = onEvent; });
  const joined = topics.join(",");

  useEffect(() => {
    const list = joined ? joined.split(",") : [];
    if (!list.length || !token) return;
    if (MOCK) {
      const offs = list.map((t) => on(t, event, (p) => latest.current(p)));
      return () => offs.forEach((off) => off());
    }
    const sb = getSupabase();
    if (!sb) return;
    const channels: Array<ReturnType<typeof sb.channel>> = [];
    let cancelled = false;
    sb.auth.getSession().then(({ data }) => {
      if (cancelled || !data.session) return;
      for (const t of list) {
        channels.push(sb.channel(t, { config: { private: true } }).on("broadcast", { event }, (msg) => latest.current((msg.payload ?? {}) as Payload)).subscribe());
      }
    });
    return () => { cancelled = true; channels.forEach((c) => sb.removeChannel(c)); };
  }, [joined, event, token]);
}

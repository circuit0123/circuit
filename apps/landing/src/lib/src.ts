"use client";

import { useSyncExternalStore } from "react";
import { isSrc } from "./env";

const noSubscribe = () => () => {};

/**
 * The `src` for links and forms on this page: `?src=…` from the address bar when it is valid (a campaign link keeps its label),
 * otherwise the page's own default. The server HTML always has the default, so without JavaScript the default is what you get.
 */
export function useSrc(fallback: string): string {
  return useSyncExternalStore(
    noSubscribe,
    () => {
      const v = new URLSearchParams(window.location.search).get("src");
      return isSrc(v) ? v : fallback;
    },
    () => fallback,
  );
}

"use client";

import { useSyncExternalStore } from "react";

/**
 * The ui_v2 switch is frontend only (docs/ui-v2-plan.md §1). One build-time variable:
 *   off      the v2 code is never reached (default)
 *   preview  old UI for everyone, except a browser that has opened `?ui=v2` (saved in localStorage; `?ui=v1` clears it)
 *   on       v2 for everyone
 * A tiny inline script in layout.tsx puts data-ui="v2" on <html> before first paint; `useUiV2()` reads it.
 */
export type UiV2Mode = "off" | "preview" | "on";

const raw = process.env.NEXT_PUBLIC_UI_V2;
export const UI_V2_MODE: UiV2Mode = raw === "on" || raw === "preview" ? raw : "off";

const STORAGE_KEY = "circuit.ui";

/** Runs in <head> before first paint. Not rendered at all when the mode is off. */
export const uiV2Script = `try{var m="${UI_V2_MODE}",d=document.documentElement,v=m==="on";if(m==="preview"){var q=new URLSearchParams(location.search).get("ui");try{if(q==="v2")localStorage.setItem("${STORAGE_KEY}","v2");else if(q==="v1")localStorage.removeItem("${STORAGE_KEY}");v=localStorage.getItem("${STORAGE_KEY}")==="v2"}catch(e){v=q==="v2"}}if(v){d.dataset.ui="v2";var t=document.querySelector("meta[data-circuit]");if(t)t.content="#0A0A0C"}}catch(e){}`;

const subscribe = () => () => {};
const read = () => document.documentElement.dataset.ui === "v2";

/** True when this browser is showing v2. Server render and first hydration pass say false, then it flips. */
export function useUiV2(): boolean {
  return useSyncExternalStore(subscribe, read, () => false);
}

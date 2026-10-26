"use client";

import { useCallback } from "react";
import { CITIES } from "./missing";

export type Place = { lat: number; lng: number; city: string };
export type Locate = { ok: true; place: Place } | { ok: false; reason: "denied" | "unavailable" };

const NEAR_KM = 100;
const km = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) => {
  const r = (d: number) => (d * Math.PI) / 180;
  const h = Math.sin(r(b.lat - a.lat) / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(r(b.lng - a.lng) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
};
const coarse = (n: number) => Math.round(n * 100) / 100;

/** "Use my location" and "Choose a city" (sign-up step 7). Only a coarse point (two decimals, about 1 km) is ever kept. */
export function useWhere() {
  const locate = useCallback(
    (): Promise<Locate> =>
      new Promise((resolve) => {
        if (typeof navigator === "undefined" || !navigator.geolocation) return resolve({ ok: false, reason: "unavailable" });
        navigator.geolocation.getCurrentPosition(
          (p) => {
            const here = { lat: coarse(p.coords.latitude), lng: coarse(p.coords.longitude) };
            const nearest = CITIES.map((c) => ({ c, d: km(here, c) })).sort((a, b) => a.d - b.d)[0];
            resolve({ ok: true, place: { ...here, city: nearest && nearest.d <= NEAR_KM ? nearest.c.name : "" } });
          },
          (e) => resolve({ ok: false, reason: e.code === e.PERMISSION_DENIED ? "denied" : "unavailable" }),
          { timeout: 10_000, maximumAge: 10 * 60_000 },
        );
      }),
    [],
  );
  return { cities: CITIES, locate };
}

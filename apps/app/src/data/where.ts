"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";
import { api, unwrap } from "./client";
import { useKey } from "./keys";

export type Place = { lat: number; lng: number; city: string };
export type Locate = { ok: true; place: Place } | { ok: false; reason: "denied" | "unavailable" };

const NEAR_KM = 100;
const km = (a: { lat: number; lng: number }, b: { lat: number; lng: number }) => {
  const r = (d: number) => (d * Math.PI) / 180;
  const h = Math.sin(r(b.lat - a.lat) / 2) ** 2 + Math.cos(r(a.lat)) * Math.cos(r(b.lat)) * Math.sin(r(b.lng - a.lng) / 2) ** 2;
  return 6371 * 2 * Math.asin(Math.sqrt(h));
};
const coarse = (n: number) => Math.round(n * 100) / 100;

/** The cities we run in, the pilot city first (`GET /api/cities`). Changes rarely, so it is asked once. */
export function useCities() {
  const { key, enabled } = useKey("cities");
  return useQuery({ queryKey: key, enabled, staleTime: Infinity, queryFn: () => unwrap(api.GET("/api/cities")) });
}

/** "Use my location" and "Choose a city" (sign-up step 7). Only a coarse point (two decimals, about 1 km) is ever kept. */
export function useWhere() {
  const qc = useQueryClient();
  const { key } = useKey("cities");
  const cities = useCities().data ?? [];
  const locate = useCallback(
    (): Promise<Locate> =>
      new Promise((resolve) => {
        if (typeof navigator === "undefined" || !navigator.geolocation) return resolve({ ok: false, reason: "unavailable" });
        navigator.geolocation.getCurrentPosition(
          async (p) => {
            const here = { lat: coarse(p.coords.latitude), lng: coarse(p.coords.longitude) };
            const all = await qc.fetchQuery({ queryKey: key, staleTime: Infinity, queryFn: () => unwrap(api.GET("/api/cities")) }).catch(() => []);
            const nearest = all.map((c) => ({ c, d: km(here, c) })).sort((a, b) => a.d - b.d)[0];
            resolve({ ok: true, place: { ...here, city: nearest && nearest.d <= NEAR_KM ? nearest.c.name : "" } });
          },
          (e) => resolve({ ok: false, reason: e.code === e.PERMISSION_DENIED ? "denied" : "unavailable" }),
          { timeout: 10_000, maximumAge: 10 * 60_000 },
        );
      }),
    [qc, key],
  );
  return { cities, locate };
}

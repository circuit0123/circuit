"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import { SlidersHorizontal, X } from "lucide-react";
import { Avatar, Button, Chip, ErrorState, cx, useToast } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import {
  activeFilters, kmOrNull, loadFailed, metaLine, roleHref, startupHref, useFollow, useFollows, useHere, useInterest, useMapPins, useMe, useStartupJobs,
  type Bounds, type DiscoverFilters, type StartupTile,
} from "@/data";
import { MAP_TILES_URL } from "@/lib/env";

type Pin = StartupTile & { lat: number; lng: number };
type View = { lng: number; lat: number; zoom: number; selected: number | null };

/** The map's place, zoom and selected pin, kept for the session so Back (or a reload) comes back to the same spot (DESIGN.md §4). */
const VIEW_KEY = "circuit.discover.map";
const readView = (): View | null => { try { return JSON.parse(sessionStorage.getItem(VIEW_KEY) ?? "null"); } catch { return null; } };
const saveView = (v: View) => { try { sessionStorage.setItem(VIEW_KEY, JSON.stringify(v)); } catch { /* not kept */ } };

/** Bounds around a point when there is no map to ask (no WebGL): roughly the 15 km the first view shows. */
const around = (c: { lat: number; lng: number }): Bounds => ({ west: c.lng - 0.16, east: c.lng + 0.16, south: c.lat - 0.14, north: c.lat + 0.14 });

/** Raster tiles look like a lit window on a black screen, so the dark theme dims and greys them (the pins and photos stay the loud things). */
const isDark = () => getComputedStyle(document.body).backgroundColor === "rgb(0, 0, 0)";
const paint = (dark: boolean) => ({
  bg: dark ? "#050b08" : "#c2bcc8",
  raster: dark ? { "raster-saturation": -0.85, "raster-brightness-max": 0.32, "raster-contrast": 0.1 } : { "raster-saturation": -0.5, "raster-brightness-max": 1, "raster-contrast": 0 },
});

type Props = {
  visible: boolean;
  filters: DiscoverFilters;
  onFilters: (f: DiscoverFilters) => void;
  onOpenFilters: () => void;
  segment: React.ReactNode;
};

/**
 * Discover → Map (Map.dc.html): full screen MapLibre with OpenStreetMap tiles, pins by hiring status. A pin tap only selects it and opens
 * the sheet, never navigates (an accidental tap while panning). Drawn in a layer of its own over the page; hidden, not destroyed, while a
 * pushed screen shows, so Back finds the same pin and zoom.
 */
export function MapView({ visible, filters, onFilters, onOpenFilters, segment }: Props) {
  const here = useHere();
  const box = useRef<HTMLDivElement>(null);
  const map = useRef<import("maplibre-gl").Map | null>(null);
  const markers = useRef(new Map<number, { marker: import("maplibre-gl").Marker; el: HTMLButtonElement }>());
  const [first] = useState<View>(() => readView() ?? { ...here, zoom: 11, selected: null });
  const start = useRef<View>(first);
  const [bounds, setBounds] = useState<Bounds | null>(null);
  const [selected, setSelected] = useState<number | null>(first.selected);
  const [broken, setBroken] = useState(false);
  const [mounted, setMounted] = useState(false);
  const pins = useMapPins(bounds ?? (broken ? around(here) : null), filters);
  const sel = pins.pins.find((p) => p.id === selected) ?? null;

  useEffect(() => { setMounted(true); }, []); // eslint-disable-line react-hooks/set-state-in-effect

  // Create the map once.
  useEffect(() => {
    if (!mounted || !box.current) return;
    let gone = false;
    void (async () => {
      try {
        const ml = await import("maplibre-gl");
        // MapLibre 6 runs its tile work in a module worker that sits next to its own file; the bundler emits it as an asset here.
        ml.setWorkerUrl(new URL("maplibre-gl/dist/maplibre-gl-worker.mjs", import.meta.url).href);
        if (gone || !box.current) return;
        const look = paint(isDark());
        const m = new ml.Map({
          container: box.current,
          center: [start.current.lng, start.current.lat],
          zoom: start.current.zoom,
          attributionControl: { compact: true },
          dragRotate: false,
          pitchWithRotate: false,
          style: {
            version: 8,
            sources: { osm: { type: "raster", tiles: [MAP_TILES_URL], tileSize: 256, maxzoom: 19, attribution: "© OpenStreetMap contributors" } },
            layers: [
              { id: "bg", type: "background", paint: { "background-color": look.bg } },
              { id: "osm", type: "raster", source: "osm", paint: look.raster },
            ],
          },
        });
        m.touchZoomRotate.disableRotation();
        map.current = m;
        const report = () => {
          const b = m.getBounds();
          setBounds({ west: b.getWest(), south: b.getSouth(), east: b.getEast(), north: b.getNorth() });
          const c = m.getCenter();
          start.current = { ...start.current, lng: c.lng, lat: c.lat, zoom: m.getZoom() };
          saveView(start.current);
        };
        report();
        m.on("moveend", report);
        // Follow theme changes (Settings, or the system switching at sunset).
        const retheme = () => {
          if (!m.isStyleLoaded()) return;
          const l = paint(isDark());
          m.setPaintProperty("bg", "background-color", l.bg);
          for (const [k, v] of Object.entries(l.raster)) m.setPaintProperty("osm", k as "raster-saturation", v);
        };
        const watch = new MutationObserver(() => requestAnimationFrame(retheme));
        watch.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });
        const media = window.matchMedia("(prefers-color-scheme: dark)");
        media.addEventListener("change", retheme);
        m.once("remove", () => { watch.disconnect(); media.removeEventListener("change", retheme); });
        // A tile that can't load (offline, slow 3G) leaves the plain background; only other errors are worth a warning.
        m.on("error", (e) => { if (!/tile|fetch/i.test(String(e.error?.message))) console.warn("[map]", e.error?.message ?? e); });
      } catch (e) {
        console.warn("[map] could not start", e);
        if (!gone) setBroken(true);
      }
    })();
    const placed = markers.current;
    return () => {
      gone = true;
      map.current?.remove();
      map.current = null;
      placed.clear();
    };
  }, [mounted]);

  // Back from a pushed screen: the layer was hidden, so the canvas needs its size again.
  useEffect(() => { if (visible) map.current?.resize(); }, [visible]);

  // Keep the selection for Back and reloads.
  useEffect(() => { start.current = { ...start.current, selected }; saveView(start.current); }, [selected]);

  // A pin the sheet would cover glides up into the open part of the map.
  useEffect(() => {
    const m = map.current;
    const p = pins.pins.find((x) => x.id === selected);
    if (!m || !p || window.innerWidth >= 1024) return;
    const y = m.project([p.lng, p.lat]).y;
    if (y > m.getContainer().clientHeight * 0.5) m.easeTo({ center: [p.lng, p.lat], offset: [0, -m.getContainer().clientHeight * 0.2], duration: matchMedia("(prefers-reduced-motion: reduce)").matches ? 0 : 350 });
  }, [selected]); // eslint-disable-line react-hooks/exhaustive-deps

  // Pins as real buttons (keyboard and screen readers reach them), updated in place.
  useEffect(() => {
    const m = map.current;
    if (!m) return;
    void import("maplibre-gl").then((ml) => {
      const keep = new Set(pins.pins.map((p) => p.id));
      for (const [id, x] of markers.current) if (!keep.has(id)) { x.marker.remove(); markers.current.delete(id); }
      for (const p of pins.pins) {
        let x = markers.current.get(p.id);
        if (!x) {
          const el = document.createElement("button");
          el.type = "button";
          el.className = "map-pin";
          el.addEventListener("click", (e) => { e.stopPropagation(); setSelected(p.id); });
          const marker = new ml.Marker({ element: el }).setLngLat([p.lng, p.lat]).addTo(m);
          x = { marker, el };
          markers.current.set(p.id, x);
        }
        x.el.setAttribute("aria-label", `${p.name}, ${p.hiring ? "hiring" : "not hiring"}`);
        x.el.setAttribute("aria-pressed", String(p.id === selected));
        x.el.dataset.hiring = String(p.hiring);
        x.el.dataset.selected = String(p.id === selected);
      }
    });
  }, [pins.pins, selected]);

  // Esc closes the sheet.
  useEffect(() => {
    if (selected === null) return;
    const f = (e: KeyboardEvent) => { if (e.key === "Escape") setSelected(null); };
    window.addEventListener("keydown", f);
    return () => window.removeEventListener("keydown", f);
  }, [selected]);

  if (!mounted) return null;
  return createPortal(
    <div
      className={cx("fixed inset-x-0 bottom-0 z-10 bg-bg lg:left-60", !visible && "hidden")}
      style={{ top: "var(--dev-bar, 0px)" }}
      data-no-swipe
      aria-label="Map of startups near you"
      role="region"
    >
      {/* MapLibre makes its container `position: relative`, so the container fills a positioned wrapper instead of being one. */}
      <div className={cx("absolute inset-0", broken && "hidden")}><div ref={box} className="h-full w-full" /></div>
      {broken && (
        <div className="absolute inset-x-0 top-36 bottom-0 overflow-y-auto px-4 pb-48">
          <ErrorState text="The map can't load on this device. Here are the same startups as a list." />
          <ul className="mt-6" aria-label="Startups on the map">
            {pins.pins.map((p) => (
              <li key={p.id}>
                <button type="button" onClick={() => setSelected(p.id)} aria-pressed={p.id === selected} aria-label={`${p.name}, ${p.hiring ? "hiring" : "not hiring"}`} className="flex min-h-row w-full items-center justify-between gap-4 border-b border-separator text-left">
                  <span className="t-body">{p.name}</span><span className="t-subhead text-text-muted">{p.hiring ? "Hiring" : "Not hiring"}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="absolute inset-x-4 top-[calc(12px+env(safe-area-inset-top))] flex flex-col gap-3 lg:left-6 lg:right-auto lg:w-[420px]">
        {segment}
        <div className="flex gap-2" role="group" aria-label="Map filters">
          <Chip label="Hiring" selected={filters.hiringOnly} onToggle={() => onFilters({ ...filters, hiringOnly: !filters.hiringOnly })} className={filters.hiringOnly ? undefined : "material"} />
          <Chip label="Within 10 km" selected={filters.distanceKm === 10} onToggle={() => onFilters({ ...filters, distanceKm: filters.distanceKm === 10 ? null : 10 })} className={filters.distanceKm === 10 ? undefined : "material"} />
          <button type="button" onClick={onOpenFilters} className="material relative inline-flex min-h-8 items-center gap-1 rounded-full px-3 t-subhead before:absolute before:-inset-1.5 before:content-['']">
            <SlidersHorizontal size={16} strokeWidth={1.75} aria-hidden />{activeFilters(filters, "map") > 0 ? `Filters · ${activeFilters(filters, "map")}` : "Filters"}
          </button>
        </div>
        {pins.isError && <p role="alert" className="material rounded-control px-3 py-2 t-subhead">{loadFailed("startups on the map")}</p>}
        {(bounds || broken) && !pins.isPending && !pins.isError && pins.pins.length === 0 && <p className="material rounded-control px-3 py-2 t-subhead">No startups here match these filters. Zoom out or clear a filter.</p>}
      </div>

      {sel && <PinSheet pin={sel} onClose={() => setSelected(null)} />}
    </div>,
    document.body,
  );
}

/** The selected startup (Map.dc.html): name, sector and distance, what it is hiring for and how well you fit, and one primary action. */
function PinSheet({ pin, onClose }: { pin: Pin; onClose: () => void }) {
  const router = useRouter();
  const me = useMe().data;
  const jobs = useStartupJobs(pin.hiring ? pin.id : null);
  const follows = useFollows();
  const follow = useFollow();
  const following = follows.data?.has(pin.id) ?? false;
  const interest = useInterest(pin.id);
  const toast = useToast();
  const toggleInterest = async () => {
    if (!(await interest.set(!interest.interested))) toast({ text: "Couldn't save that. Try again.", tone: "error" });
  };
  const roles = jobs.data ?? [];
  // Under-18 members only see roles from verified startups; for them an unverified startup is simply not hiring.
  const hiring = pin.hiring && (!me?.isMinor || pin.verified);
  const best = [...roles].sort((a, b) => Number(!!b.fit) - Number(!!a.fit))[0];
  const summary = hiring
    ? metaLine("Hiring", roles.length === 1 ? roles[0].title : `${pin.openRoles} open roles`, best?.fit)
    : "Not hiring right now · Follow for updates";

  return (
    <section
      aria-label="Selected startup"
      className="absolute inset-x-0 bottom-0 rounded-t-sheet bg-surface px-4 pb-[calc(104px+env(safe-area-inset-bottom))] pt-2 shadow-lift lg:bottom-6 lg:left-6 lg:right-auto lg:w-[420px] lg:rounded-sheet lg:pb-5"
    >
      <div className="mx-auto mb-3 h-1 w-10 rounded-full bg-text-subtle/50 lg:hidden" aria-hidden />
      <div className="flex items-center gap-4">
        <Avatar id={`s${pin.id}`} name={pin.name} size={44} shape="square" />
        <div className="min-w-0 flex-1">
          <h2 className="t-headline">{pin.name}</h2>
          <p className="t-subhead text-text-muted">{metaLine(pin.sector, kmOrNull(pin.km))}</p>
        </div>
        <button type="button" onClick={onClose} aria-label="Close" className="-mr-2 flex h-11 w-11 items-center justify-center rounded-full text-text-muted"><X size={20} strokeWidth={1.75} /></button>
      </div>
      <p className="t-subhead mt-4 text-text-muted">{summary}</p>
      <div className="mt-4 flex flex-col gap-1">
        {hiring ? (
          <Button
            variant="primary"
            className="w-full"
            disabled={jobs.isPending}
            onClick={() => router.push(roles.length === 1 ? roleHref(roles[0].id) : startupHref(pin.id, true))}
          >
            See open roles
          </Button>
        ) : (
          <Button variant={following ? "secondary" : "primary"} className="w-full" aria-pressed={following} onClick={() => follow.mutate({ id: pin.id, on: !following })}>
            {following ? "Following" : "Follow"}
          </Button>
        )}
        {me?.role === "student" && (
          <Button variant="text" className="w-full" aria-pressed={interest.interested} disabled={interest.pending} onClick={toggleInterest}>
            {interest.interested ? "Interested · tap to withdraw" : "I'm interested"}
          </Button>
        )}
        <Button variant="text" className="w-full" onClick={() => router.push(startupHref(pin.id))}>View startup</Button>
      </div>
    </section>
  );
}

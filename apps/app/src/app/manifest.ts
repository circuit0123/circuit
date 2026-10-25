import type { MetadataRoute } from "next";

/** PWA basics (F1): installable, black ground, the brand icons from docs/brand. The service worker and offline shell come in F7. */
export default function manifest(): MetadataRoute.Manifest {
  return {
    name: "Circuit",
    short_name: "Circuit",
    description: "See who near you is building, who needs help and who is hiring.",
    start_url: "/",
    scope: "/",
    display: "standalone",
    orientation: "portrait",
    background_color: "#000000",
    theme_color: "#000000",
    icons: [
      { src: "/icons/circuit-app-icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
      { src: "/icons/circuit-app-icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
      { src: "/icons/circuit-app-icon-maskable-192.png", sizes: "192x192", type: "image/png", purpose: "maskable" },
      { src: "/icons/circuit-app-icon-maskable-512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  };
}

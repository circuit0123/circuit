import type { Metadata, Viewport } from "next";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Circuit",
  description: "See who near you is building, who needs help and who is hiring.",
};

export const viewport: Viewport = {
  viewportFit: "cover",
  // The on-screen keyboard shrinks the page, so the pinned primary button rides above it.
  interactiveWidget: "resizes-content",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
    { media: "(prefers-color-scheme: light)", color: "#FFFFFF" },
  ],
};

/** Runs before first paint: puts the saved theme and accent on <html> so there is no flash of the default colour. */
const FIRST_PAINT = `try{var a=JSON.parse(localStorage.getItem("circuit.appearance")||"{}"),d=document.documentElement;if(a.theme==="dark"||a.theme==="light")d.dataset.theme=a.theme;if(/^(sky|indigo|rose|lime|mono)$/.test(a.accent))d.dataset.accent=a.accent}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: FIRST_PAINT }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

import type { Metadata, Viewport } from "next";
import { firstPaintScript } from "@circuit/ui";
import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import { Providers } from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "Circuit",
  description: "See who near you is building, who needs help and who is hiring.",
  icons: { icon: "/favicon.ico", apple: "/apple-touch-icon.png" },
  appleWebApp: { capable: true, title: "Circuit", statusBarStyle: "black-translucent" },
  // The app is signed-in only (PRODUCTION.md §2): search engines stay out. The landing site is the indexed one.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  viewportFit: "cover",
  // The on-screen keyboard shrinks the page, so the pinned primary button rides above it.
  interactiveWidget: "resizes-content",
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
    { media: "(prefers-color-scheme: light)", color: "#C2BCC8" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={`${GeistSans.variable} ${GeistMono.variable}`} suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: firstPaintScript }} />
      </head>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}

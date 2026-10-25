import type { Metadata, Viewport } from "next";
import { GeistSans } from "geist/font/sans";
import { LandingMotion } from "@/components/LandingMotion";
import { LANDING_URL } from "@/lib/env";
import "./globals.css";

const TITLE = "Circuit — build with people near you";
const DESCRIPTION =
  "Circuit matches students, founders, mentors and investors on what each needs and can offer, not on job titles or college names. Invite-only, starting in one city.";

export const metadata: Metadata = {
  metadataBase: new URL(LANDING_URL),
  title: { default: TITLE, template: "%s — Circuit" },
  description: DESCRIPTION,
  alternates: { canonical: "/" },
  robots: { index: true, follow: true },
  icons: { icon: "/favicon.ico", apple: "/apple-touch-icon.png" },
  openGraph: {
    type: "website",
    siteName: "Circuit",
    locale: "en_IN",
    url: "/",
    title: TITLE,
    description: DESCRIPTION,
    images: [{ url: "/og.png", width: 1200, height: 630, alt: "Circuit" }],
  },
  twitter: { card: "summary_large_image", title: TITLE, description: DESCRIPTION, images: ["/og.png"] },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: dark)", color: "#000000" },
    { media: "(prefers-color-scheme: light)", color: "#c2bcc8" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={GeistSans.variable}>
      <body>
        <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-10 focus:rounded-control focus:bg-surface focus:px-4 focus:py-3">Skip to content</a>
        {children}
        <LandingMotion />
      </body>
    </html>
  );
}

import type { Metadata } from "next";
import { Bricolage_Grotesque, Hanken_Grotesk } from "next/font/google";
import "./globals.css";

const display = Bricolage_Grotesque({ subsets: ["latin"], variable: "--font-display", weight: ["600", "700", "800"] });
const text = Hanken_Grotesk({ subsets: ["latin"], variable: "--font-text" });

export const metadata: Metadata = {
  title: "Circuit",
  description: "Circuit matches students, founders and mentors on what each needs and can offer, not on job titles or college names.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en-IN" className={`${display.variable} ${text.variable}`}>
      <body>{children}</body>
    </html>
  );
}

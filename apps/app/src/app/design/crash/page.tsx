import { notFound } from "next/navigation";
import { APP_ENV } from "@/lib/env";

/** Dev only: throws on purpose so the 500 page can be seen and tested (/design/crash). */
export default function Crash() {
  if (APP_ENV !== "dev") notFound();
  throw new Error("Deliberate crash to show the 500 page.");
}

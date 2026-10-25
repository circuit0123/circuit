import { notFound } from "next/navigation";
import { PagerDemo } from "@/components/design/PagerDemo";
import { APP_ENV } from "@/lib/env";

/** Dev only: the five-tab TabPager on its own, with something swipeable on some tabs, for the touch tests (tests/tabpager.spec.ts). */
export default function PagerPage() {
  if (APP_ENV !== "dev") notFound();
  return <PagerDemo />;
}

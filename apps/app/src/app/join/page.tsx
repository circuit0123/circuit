import { Suspense } from "react";
import { JoinRoute } from "@/components/JoinRoute";

export default function Page() {
  return (
    <Suspense>
      <JoinRoute />
    </Suspense>
  );
}

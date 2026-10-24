import { Suspense } from "react";
import { AuthCallback } from "@/components/AuthCallback";

export default function Page() {
  return (
    <Suspense>
      <AuthCallback />
    </Suspense>
  );
}

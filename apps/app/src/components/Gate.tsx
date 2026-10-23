"use client";

import { Skeleton } from "@circuit/ui";
import { useSession } from "./Providers";
import { SignIn } from "./SignIn";

export function Gate({ children }: { children: React.ReactNode }) {
  const { ready, token } = useSession();
  if (!ready) return <Skeleton className="m-4 h-40" />;
  if (!token) return <SignIn />;
  return <>{children}</>;
}

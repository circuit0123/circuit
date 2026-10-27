"use client";

import { Skeleton } from "@circuit/ui";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { parseJoin, reportJoinVisit, useJoinContext } from "@/data";
import { Centered } from "./Centered";

/**
 * `/join?role=student&src=landing-students&code=…&org=…`: where the landing site, partner invites and member invites arrive. The link is
 * remembered (it has to survive the trip to Google and back), then the person goes to the front door; the gate does the rest and skips
 * the steps the link already answers.
 */
export function JoinRoute() {
  const params = useSearchParams();
  const router = useRouter();
  const join = useJoinContext();
  useEffect(() => {
    join.clear(); // the newest link wins; an old invite code must not linger
    const link = parseJoin(params);
    join.save(link);
    reportJoinVisit(link.src);
    router.replace("/");
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, on arrival
  }, []);
  return <Centered><Skeleton className="h-10 w-2/3" /><Skeleton className="h-24" /></Centered>;
}

"use client";

import { Skeleton, Step, StepTransition } from "@circuit/ui";
import { useOnboarding } from "@/data";
import { Centered } from "../Centered";
import { Age } from "./Age";
import { Name } from "./Name";
import { Needs } from "./Needs";
import { Offers } from "./Offers";
import { Organisation } from "./Organisation";
import { Role } from "./Role";
import { Safety } from "./Safety";
import { Where } from "./Where";
import { Work } from "./Work";

/** Sign-up steps 4–14, one screen at a time. The flow decides which screen; each screen asks one thing. */
export function Onboarding() {
  const flow = useOnboarding();
  if (!flow.ready) return <Centered><Skeleton className="h-10 w-2/3" /><Skeleton className="h-24" /></Centered>;
  const screen = (() => {
    switch (flow.current) {
      case "name": return <Name flow={flow} />;
      case "role": return <Role flow={flow} />;
      case "age": return <Age flow={flow} />;
      case "safety": return <Safety flow={flow} />;
      case "where": return <Where flow={flow} />;
      case "work": return <Work flow={flow} />;
      case "offers": return <Offers flow={flow} />;
      case "needs": return <Needs flow={flow} />;
      case "organisation": return <Organisation flow={flow} />;
      default: return <Step title="Almost there" progress={flow.progress} onBack={flow.canGoBack ? flow.back : undefined} />; // photo, colour and ready arrive in F2 part 4
    }
  })();
  return <StepTransition stepKey={flow.current} direction={flow.direction}>{screen}</StepTransition>;
}

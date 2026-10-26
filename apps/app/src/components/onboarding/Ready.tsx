"use client";

import { Button, DropCardFace, Logo, Skeleton, Step } from "@circuit/ui";
import { motion, useReducedMotion } from "motion/react";
import { useRouter } from "next/navigation";
import { type Flow, useDailyDrop } from "@/data";

/** Step 14. The first person in today's drop, if there is one. The drop never blocks finishing: no drop yet just means "tomorrow". */
export function Ready({ flow }: { flow: Flow }) {
  const router = useRouter();
  const reduce = useReducedMotion();
  const drop = useDailyDrop();
  const card = drop.data?.cards.find((c) => !c.answered);
  const loading = drop.isPending;

  const finish = async () => {
    if (await flow.actions.finish()) router.replace("/");
  };

  return (
    <Step
      lead={<Logo kind="mark" height={64} />}
      title="You're on the circuit."
      subhead={card || loading ? "Here's the first person in today's drop." : "Your first drop arrives tomorrow at 8."}
      progress={1}
      footer={
        <>
          {flow.error && <p role="alert" className="t-footnote text-danger">{flow.error}</p>}
          <Button variant="primary" className="w-full" disabled={flow.saving} onClick={() => void finish()}>See today's drop</Button>
        </>
      }
    >
      {loading ? (
        <Skeleton className="mt-4 h-40 rounded-card" />
      ) : card ? (
        <motion.article
          aria-label="First in today's drop"
          className="mt-4 overflow-hidden rounded-card bg-surface shadow-lift"
          initial={reduce ? { opacity: 0 } : { opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: reduce ? 0.15 : 0.4, ease: "easeOut" }}
        >
          <DropCardFace card={card} compact />
        </motion.article>
      ) : null}
    </Step>
  );
}

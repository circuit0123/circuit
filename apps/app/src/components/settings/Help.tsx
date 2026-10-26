"use client";

import { ChevronDown } from "lucide-react";
import { Button, GroupedList, ListRow, SegmentedControl, TextArea, cx } from "@circuit/ui";
import { useRouter } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { SUPPORT_KINDS, settingsHref, useSettings, useSupport, type SupportKind } from "@/data";
import { ROW_INSET } from "../sheets";
import { SettingsScreen } from "./SettingsHome";

const FAQ: Array<{ q: string; a: string }> = [
  { q: "How does Circuit choose my matches?", a: "On what you need and what you can offer, not on your college or job title. Every match tells you why in one line, and some connect you across sectors (a Bridge match)." },
  { q: "Who can see my profile?", a: "You choose in Settings → Privacy: everyone, members, or only your connections. Under 18, your profile is private and only your connections can message you." },
  { q: "What is an intro?", a: "A mutual connection introduces you to someone. You get a few each week, so every one means something." },
  { q: "What is a circuit?", a: "Three people who each help the next: you give what you're good at and get what you need. Rounds are weekly and you can always say no." },
  { q: "Why are there no likes or follower counts?", a: "We don't show public counts. If you post a build log, you see its reactions and replies privately." },
  { q: "How do I get my data or delete my account?", a: "Settings → Your data. Export sends you a file by email; Delete removes your profile and signs you out." },
];

/** Help and FAQ, Contact support (with a reference to quote) and the Grievance Officer (IT Rules 2021), from GET /api/me/settings. */
export function Help() {
  const router = useRouter();
  const s = useSettings();
  const support = s.data?.support;
  useEffect(() => { if (window.location.hash === "#contact") document.getElementById("contact")?.scrollIntoView({ block: "start" }); }, []);
  return (
    <SettingsScreen title="Help">
      <section aria-labelledby="faq-h" className="px-4 lg:px-0">
        <h2 id="faq-h" className="t-headline mb-2">Questions</h2>
        <ul className="overflow-hidden rounded-group bg-surface">{FAQ.map((f, i) => <Faq key={f.q} {...f} first={i === 0} />)}</ul>
      </section>
      <Contact email={support?.support_email} />
      {support && (
        <GroupedList header="Grievance Officer" footer="For complaints about content or how we handle your data. We acknowledge within 24 hours and resolve within 15 days.">
          <ListRow className={ROW_INSET} title={support.grievance.name} subtitle={support.grievance.address} />
          <ListRow className={ROW_INSET} title={support.grievance.email} onClick={() => { window.location.href = `mailto:${support.grievance.email}`; }} />
        </GroupedList>
      )}
      <GroupedList header="Policies">
        <ListRow className={ROW_INSET} title="Privacy policy" onClick={() => router.push(settingsHref("legal/privacy"))} />
        <ListRow className={ROW_INSET} title="Terms" onClick={() => router.push(settingsHref("legal/terms"))} />
        <ListRow className={ROW_INSET} title="Community guidelines" onClick={() => router.push(settingsHref("legal/guidelines"))} />
      </GroupedList>
    </SettingsScreen>
  );
}

/** One question. The answer fades in and rises 8px, the chevron turns (DESIGN.md §7 FAQ); no height animation. */
function Faq({ q, a, first }: { q: string; a: string; first: boolean }) {
  const [open, setOpen] = useState(false);
  const id = useId();
  return (
    <li className={cx(!first && "ml-4 border-t border-separator")}>
      <button type="button" aria-expanded={open} aria-controls={id} onClick={() => setOpen(!open)} className={cx("flex min-h-row w-full items-center justify-between gap-4 py-2 pr-4 text-left t-body", first && "pl-4")}>
        {q}
        <ChevronDown size={20} strokeWidth={1.75} aria-hidden className={cx("shrink-0 text-text-subtle transition-transform duration-200 motion-reduce:transition-none", open && "rotate-180")} />
      </button>
      <div id={id} hidden={!open} className={cx("pb-4 pr-4", first && "pl-4")}>
        <p className="t-subhead max-w-[540px] animate-[faq_220ms_ease-out] text-text-muted motion-reduce:animate-none">{a}</p>
      </div>
    </li>
  );
}

function Contact({ email }: { email?: string }) {
  const send = useSupport();
  const [kind, setKind] = useState<SupportKind>("question");
  const [message, setMessage] = useState("");
  return (
    <section id="contact" aria-labelledby="contact-h" className="scroll-mt-16 px-4 lg:px-0">
      <h2 id="contact-h" className="t-headline">Contact support</h2>
      <p className="t-subhead mb-4 mt-1 text-text-muted">We reply within two working days{email ? `, from ${email}` : ""}.</p>
      {send.data ? (
        <p role="status" className="t-body rounded-card bg-surface p-4">Sent. Your reference is <span className="num font-semibold">{send.data.reference}</span>. We&apos;ve emailed you a copy.</p>
      ) : (
        <form onSubmit={(e) => { e.preventDefault(); if (message.trim()) send.mutate({ kind, message }); }} className="flex flex-col gap-4">
          <SegmentedControl stretch label="What is it about?" items={SUPPORT_KINDS} value={kind} onChange={setKind} />
          <TextArea label="How can we help?" value={message} onChange={(e) => setMessage(e.target.value.slice(0, 2000))} maxLength={2000} className="[&_textarea]:h-36" />
          <Button type="submit" variant="primary" className="w-full" disabled={!message.trim() || send.isPending}>{send.isPending ? "Sending…" : "Send"}</Button>
          {send.isError && <p role="alert" className="t-footnote text-danger">Couldn&apos;t send that. Check your connection and try again.</p>}
        </form>
      )}
    </section>
  );
}

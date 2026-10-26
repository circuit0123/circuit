"use client";

import { Bell, Plus, Search } from "lucide-react";
import {
  ACCENTS, AccentPicker, AddChip, Avatar, BarButton, BridgeBadge, Button, Card, Chip, DistanceBadge, DropCardFace, EmptyState, ErrorState, GroupedList, HiringBadge, LargeTitleHeader,
  ListRow, Logo, MatchStrength, PrivateBadge, SegmentedControl, Sheet, Skeleton, TabBar, TextArea, TopBar, VerifiedBadge, memberTabs, partnerTabs, useToast,
  type Accent, type ButtonVariant, type Detent, type DropCard,
} from "@circuit/ui";
import { useMotionValue } from "motion/react";
import Link from "next/link";
import { createContext, useContext, useState } from "react";

const PHOTO = `data:image/svg+xml;utf8,${encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128"><rect width="128" height="128" fill="#6b8f7f"/><circle cx="64" cy="50" r="22" fill="#d9c7b0"/><path d="M20 128c4-30 24-44 44-44s40 14 44 44z" fill="#2c4a3d"/></svg>')}`;

const SAKTHI = { id: 41, name: "Sakthi Vel", role: "Mentor", headline: "Backend mentor", place: "Chennai", level: 3 };
const SAMPLE_DROP: DropCard = {
  id: 41, person: SAKTHI, reason: "Sakthi can help you with backend.", detail: "You both build for small teams. 3 km away.", helpWith: "backend",
  via: { id: 7, name: "Meera Krishnan", role: "mentor" }, offers: ["Backend", "APIs", "Mentoring"], strength: "strong", bridge: false, answered: null,
};

const Theme = createContext<"dark" | "light">("dark");

function Block({ title, children }: { title: string; children: React.ReactNode }) {
  const theme = useContext(Theme);
  return (
    // The name carries the theme, so the two panels' landmarks stay unique for screen readers.
    <section aria-label={`${title} (${theme})`} className="flex flex-col gap-3">
      <h2 className="t-title3">{title}</h2>
      {children}
    </section>
  );
}
const Row = ({ children, label }: { children: React.ReactNode; label?: string }) => (
  <div className="flex flex-col gap-1">
    {label && <span className="t-caption text-text-subtle">{label}</span>}
    <div className="flex flex-wrap items-center gap-3">{children}</div>
  </div>
);

const VARIANTS: ButtonVariant[] = ["primary", "secondary", "text", "destructive"];

function Bars({ circuits }: { circuits: boolean }) {
  const theme = useContext(Theme);
  const [active, setActive] = useState("home");
  const progress = useMotionValue(0);
  const tabs = memberTabs({ circuits, inboxDot: true });
  const set = (id: string, ps: typeof tabs) => { setActive(id); progress.set(Math.max(0, ps.findIndex((t) => t.id === id))); };
  const partner = partnerTabs({ inboxDot: false });
  return (
    <div className="flex flex-col gap-3">
      <div className="overflow-hidden rounded-card"><TabBar inline label={`Member bar (${theme})`} tabs={tabs} active={active} progress={progress} onSelect={(id) => set(id, tabs)} /></div>
      <div className="overflow-hidden rounded-card"><TabBar inline label={`Partner bar (${theme})`} tabs={partner} active={active === "circuits" ? "dashboard" : active} progress={progress} onSelect={(id) => set(id, partner)} /></div>
    </div>
  );
}

function Panel({ theme, accent }: { theme: "dark" | "light"; accent: Accent }) {
  const toast = useToast();
  const [box, setBox] = useState<HTMLElement | null>(null);
  const [seg, setSeg] = useState("people");
  const [chip, setChip] = useState(true);
  const [big, setBig] = useState(true);
  const [chips, setChips] = useState(["React", "Figma"]);
  const [sheet, setSheet] = useState<Detent | null>(null);
  const progress = useMotionValue(0);
  const fiveTabs = memberTabs({ circuits: true });
  const fourTabs = memberTabs({ circuits: false });

  return (
    <Theme.Provider value={theme}>
    <div ref={setBox} data-theme={theme} data-accent={accent} aria-label={`${theme} theme`} role="region" className="flex flex-col gap-10 px-4 py-8 lg:px-8">
      <h2 className="t-title2">{theme === "dark" ? "Dark" : "Light"}</h2>

      <Block title="Logo">
        <Row><Logo kind="lockup" height={32} /><Logo kind="mark" height={32} /></Row>
      </Block>

      <Block title="Button">
        {VARIANTS.map((v) => (
          <Row key={v} label={v}>
            <Button variant={v}>Intro me</Button>
            <Button variant={v} data-pressed-demo className="opacity-80 scale-[0.97]">Pressed</Button>
            <Button variant={v} disabled>Disabled</Button>
            <Button variant={v} icon={<Plus size={20} strokeWidth={1.75} aria-hidden />}>With icon</Button>
          </Row>
        ))}
      </Block>

      <Block title="Chip">
        <Row label="static · selectable · selected · removable">
          <Chip label="Marketing" />
          <Chip label="Fundraising" selected={!chip} onToggle={() => setChip(false)} />
          <Chip label="Hiring" selected={chip} onToggle={() => setChip(true)} />
          {chips.map((c) => <Chip key={c} label={c} onRemove={() => setChips((x) => x.filter((y) => y !== c))} />)}
        </Row>
        <Row label="large (sign-up picks) · selected · add">
          <Chip size="lg" label="React" selected={big} onToggle={() => setBig((b) => !b)} />
          <Chip size="lg" label="Maps" selected={!big} onToggle={() => setBig((b) => !b)} />
          <AddChip label="Add a skill" onClick={() => {}} />
        </Row>
      </Block>

      <Block title="Text area">
        <TextArea label="About your work" placeholder="I'm a third-year student who builds…" className="max-w-[440px]" />
      </Block>

      <Block title="Accent picker">
        <AccentPicker value={accent} onChange={() => {}} className="max-w-[440px]" />
      </Block>

      <Block title="Drop card face">
        <Row label="full (Daily Drop) · compact (end of sign-up)">
          <div className="w-full max-w-[400px] overflow-hidden rounded-card bg-surface"><DropCardFace card={SAMPLE_DROP} /></div>
          <div className="w-full max-w-[400px] overflow-hidden rounded-card bg-surface"><DropCardFace card={SAMPLE_DROP} compact /></div>
        </Row>
      </Block>

      <Block title="Card">
        <Card className="p-surface"><p className="t-headline">Asha is building a Kannada voice assistant</p><p className="t-subhead mt-1 text-text-muted">She needs a frontend developer. You build in React.</p></Card>
      </Block>

      <Block title="ListRow">
        <div className="overflow-hidden rounded-group bg-surface">
          <ListRow title="Plain row" />
          <ListRow title="With chevron" onClick={() => {}} />
          <ListRow title="With subtitle" subtitle="Two full lines are never cut" onClick={() => {}} />
          <ListRow title="Appearance" value="Dark" onClick={() => {}} />
          <ListRow title="Ravi Kumar" subtitle="Student · Chennai" leading={<Avatar id={1} name="Ravi Kumar" size={40} />} onClick={() => {}} />
          <ListRow title="Delete account" danger onClick={() => {}} />
        </div>
      </Block>

      <Block title="GroupedList">
        <GroupedList header="Privacy" footer="Under-18 accounts stay private by default.">
          <ListRow title="Profile visibility" value="Members" onClick={() => {}} />
          <ListRow title="Visible to my organisation" value="Off" onClick={() => {}} />
          <ListRow title="Messages from strangers" value="Off" onClick={() => {}} />
        </GroupedList>
      </Block>

      <Block title="SegmentedControl">
        <SegmentedControl label="Discover" value={seg} onChange={setSeg} items={[{ id: "people", label: "People" }, { id: "startups", label: "Startups" }, { id: "jobs", label: "Jobs" }, { id: "map", label: "Map" }]} />
      </Block>

      <Block title="TopBar and LargeTitleHeader">
        <Row label="expanded">
          <div className="w-full overflow-hidden rounded-card bg-bg">
            <TopBar inline={0} title="Discover" left={<BarButton label="Create"><Plus size={24} strokeWidth={1.75} /></BarButton>} right={<BarButton label="Notifications"><Bell size={24} strokeWidth={1.75} /></BarButton>} />
            <LargeTitleHeader title="Discover" />
          </div>
        </Row>
        <Row label="collapsed">
          <div className="w-full overflow-hidden rounded-card bg-bg">
            <TopBar inline={1} title="Discover" left={<BarButton label="Search"><Search size={24} strokeWidth={1.75} /></BarButton>} />
          </div>
        </Row>
      </Block>

      <Block title="TabBar">
        <p className="t-footnote text-text-muted">Five tabs, four tabs (Circuits off), and the partner bar (Dashboard in third place). The dot is an unread Inbox.</p>
        <div className="overflow-hidden rounded-card"><TabBar inline label={`Five tabs (${theme})`} tabs={fiveTabs} active="home" progress={progress} onSelect={() => {}} /></div>
        <div className="overflow-hidden rounded-card"><TabBar inline label={`Four tabs (${theme})`} tabs={fourTabs} active="discover" progress={progress} onSelect={() => {}} /></div>
        <Bars circuits />
      </Block>

      <Block title="TabPager">
        <p className="t-body text-text-muted">The pager draws the whole screen, so it has its own page: <Link href="/design/pager" className="underline">/design/pager</Link>. Swipe it on a phone, or run <code>make mock</code> and swipe the app.</p>
      </Block>

      <Block title="Sheet">
        <Row>
          <Button onClick={() => setSheet("medium")}>Medium detent</Button>
          <Button onClick={() => setSheet("large")}>Large detent</Button>
        </Row>
        <Sheet open={sheet !== null} detent={sheet ?? "medium"} onClose={() => setSheet(null)} title="Report this post" container={box}>
          <ul className="flex flex-col gap-2">
            {["It's spam", "It's rude or unkind", "It's not true", "Something else"].map((r) => <li key={r}><Button className="w-full justify-start" onClick={() => setSheet(null)}>{r}</Button></li>)}
          </ul>
        </Sheet>
      </Block>

      <Block title="Toast">
        <Row>
          <Button onClick={() => toast({ text: "Reported. Our team will review it." })}>Plain toast</Button>
          <Button onClick={() => toast({ text: "Skipped", undo: () => {} })}>With Undo</Button>
          <Button onClick={() => toast({ text: "Couldn't send. Try again.", tone: "error" })}>Error</Button>
        </Row>
      </Block>

      <Block title="Avatar">
        <Row label="circuit pattern, every size">
          {([20, 32, 40, 44, 64, 96, 128] as const).map((s) => <Avatar key={s} id={s * 7} name="Priya Nair" size={s} />)}
        </Row>
        <Row label="photo · square">
          <Avatar id={3} name="Priya Nair" src={PHOTO} size={64} />
          <Avatar id={4} name="Arjun Mehta" size={64} shape="square" />
        </Row>
      </Block>

      <Block title="Badge">
        <Row>
          <VerifiedBadge level={1} /><VerifiedBadge level={2} /><VerifiedBadge level={3} />
          <BridgeBadge /><HiringBadge /><PrivateBadge /><DistanceBadge km={4.2} />
        </Row>
      </Block>

      <Block title="MatchStrength">
        <Row><MatchStrength strength="strong" /><MatchStrength strength="good" /></Row>
      </Block>

      <Block title="EmptyState">
        <EmptyState text="When three people can help each other, your circuit shows up here." action={<Button>Add what you need</Button>} />
      </Block>

      <Block title="ErrorState">
        <ErrorState text="Couldn't load jobs. Check your connection and pull to refresh." onRetry={() => toast({ text: "Trying again" })} />
      </Block>

      <Block title="Skeleton">
        <div className="flex items-center gap-4"><Skeleton round className="h-10 w-10" /><div className="flex flex-1 flex-col gap-2"><Skeleton className="h-4 w-2/3" /><Skeleton className="h-4 w-1/3" /></div></div>
      </Block>
    </div>
    </Theme.Provider>
  );
}

/** Both themes side by side (stacked on a phone), with one accent row that recolours every panel. */
export function Gallery() {
  const [accent, setAccent] = useState<Accent>("emerald");
  return (
    <main>
      <header className="flex flex-wrap items-center gap-4 px-4 py-4 lg:px-8">
        <h1 className="t-title1">Design</h1>
        <div role="group" aria-label="Accent" className="flex flex-wrap gap-2">
          {ACCENTS.map((a) => (
            <Chip key={a.id} label={a.label} selected={a.id === accent} onToggle={() => setAccent(a.id)} />
          ))}
        </div>
        <Link href="/" className="t-body underline">Back to the app</Link>
      </header>
      <div className="grid lg:grid-cols-2">
        <Panel theme="dark" accent={accent} />
        <Panel theme="light" accent={accent} />
      </div>
    </main>
  );
}

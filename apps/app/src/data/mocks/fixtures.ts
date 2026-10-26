/**
 * TEMPORARY fixtures for mock mode — replace with the B7 contract fixtures (tests/contract/).
 *
 * Every body is checked against the generated API types with `satisfies`, so `tsc` fails here the moment openapi.json changes shape.
 * People, places and rupees are the kind the seed uses (Chennai, Indian names, ₹ stipends); nothing is lorem ipsum.
 */
import type { Schemas } from "@circuit/api-client";

const minutes = (m: number) => new Date(Date.now() - m * 60_000).toISOString();

export const author = (id: number, display_name: string, role: string, headline: string, city = "Chennai", verification_level = 1) =>
  ({ id, display_name, role, headline, city, verification_level }) satisfies Schemas["AuthorOut"];

export const PEOPLE = {
  me: author(1, "Ravi Kumar", "student", "Frontend developer, third year", "Chennai", 1),
  asha: author(2, "Asha Raman", "founder", "Building a Kannada voice assistant", "Chennai", 2),
  priya: author(3, "Priya Nair", "founder", "Running a lab-diagnostics startup", "Chennai", 2),
  arjun: author(4, "Arjun Mehta", "founder", "Hiring for an inventory platform", "Chennai", 3),
  kavya: author(5, "Dr. Kavya Subramanian", "founder", "Biotech founder, assay kits", "Chennai", 3),
  rohan: author(6, "Rohan Gupta", "founder", "Logistics for small kirana shops", "Chennai", 2),
  lakshmi: author(7, "Dr. Lakshmi Narayanan", "mentor", "Ex-VP sales, deep tech", "Chennai", 3),
  divya: author(8, "Divya Menon", "founder", "Climate data for farms", "Chennai", 2),
  sneha: author(9, "Sneha Pillai", "founder", "Design-first fintech", "Chennai", 1),
  vikram: author(10, "Vikram Anand", "investor", "Pre-seed, health and climate", "Chennai", 3),
} as const;

export const CONFIG = {
  env: "dev",
  beta_mode: false,
  beta_access: true,
  features: { pulse: true, daily_drop: true, circuits: true, investor_mode: true, partner_mode: true, promotions: true, payments: true },
} satisfies Schemas["ConfigOut"];

export const ME = {
  id: 1,
  display_name: "Ravi Kumar",
  role: "student",
  bio: "Third-year student. I build interfaces in React and want to work on something real.",
  city: "Chennai",
  college: "Sri Venkateswara Institute of Technology",
  lat: 13.0827,
  lng: 80.2707,
  verification_level: 1,
  is_minor: false,
  organisation_id: null,
  open_intro_slots: 3,
  circuits_opt_in: true,
  profile_visibility: "members",
  visible_to_org: false,
  allow_requests: true,
  beta_access: true,
  needs_consent: false,
  policy_version: "2026-10",
  appearance: { theme: "system", accent: "mint", swipe_tabs: true },
} satisfies Schemas["MeOut"];

export const PERSONAS = [
  { key: "ravi", display_name: "Ravi Kumar", role: "student" },
  { key: "asha", display_name: "Asha Raman", role: "founder" },
  { key: "lakshmi", display_name: "Dr. Lakshmi Narayanan", role: "mentor" },
  { key: "vikram", display_name: "Vikram Anand", role: "investor" },
  { key: "meenakshi", display_name: "Meenakshi Iyer", role: "partner_admin" },
] satisfies Schemas["Persona"][];

export const ONBOARDING = {
  branch: "default",
  steps: ["invite", "name", "role", "age", "safety", "where", "work", "offers", "needs", "organisation", "photo", "colour", "ready"],
  skip: [],
  current_step: null,
  completed_at: minutes(60 * 24 * 3),
  signup_source: "landing-students",
  answers: {},
} satisfies Schemas["OnboardingOut"];

/** A believable build-log picture: an inventory dashboard with real labels and ₹ figures, as an inline SVG (DESIGN.md §5 Imagery). */
const dashboard = () => {
  const rows = [["Paracetamol 500 mg", "1,240", "₹18,600"], ["ORS sachets", "860", "₹10,320"], ["Surgical gloves (M)", "412", "₹24,720"], ["Digital thermometer", "95", "₹28,500"]];
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="720" height="720" viewBox="0 0 720 720" font-family="Arial, sans-serif"><rect width="720" height="720" fill="#0b1f18"/><text x="36" y="140" font-size="26" font-weight="700" fill="#f3eef5">Stock today · Adyar pharmacy</text><text x="36" y="178" font-size="16" fill="#a79fad">Updated 9:42 am</text>${rows.map((r, i) => `<g transform="translate(36 ${230 + i * 76})"><rect width="648" height="60" rx="10" fill="#142c23"/><text x="20" y="37" font-size="20" fill="#f3eef5">${r[0]}</text><text x="440" y="37" font-size="20" fill="#2fbf8a">${r[1]} units</text><text x="560" y="37" font-size="20" fill="#f3eef5">${r[2]}</text></g>`).join("")}<text x="36" y="590" font-size="18" fill="#a79fad">Low stock: 3 items · Reorder by Friday</text></svg>`;
  return `data:image/svg+xml;utf8,${encodeURIComponent(svg)}`;
};

export const POST = {
  id: 101,
  author: PEOPLE.arjun,
  body: "Shipped the stock-alert screen today. Pharmacists in Adyar told us they check it before opening, so it is the first thing they see now.",
  capabilities: [{ slug: "frontend-dev", name: "Frontend" }, { slug: "ux-research", name: "UX research" }],
  created_at: minutes(95),
  link: "",
  media: [{ w480: dashboard(), w1440: dashboard(), alt_text: "Dashboard listing four medicines with units in stock and their value in rupees", width: 720, height: 720 }],
  my_reactions: [],
  status: "visible",
  visibility: "everyone",
} satisfies Schemas["PostOut"];

const POST_TEXT = {
  id: 102,
  author: PEOPLE.kavya,
  body: "We need a marketer who understands long sales cycles and technical buyers. If you have sold to labs or hospitals before, I would like to hear how.",
  capabilities: [{ slug: "marketing", name: "Marketing" }],
  created_at: minutes(60 * 20),
  link: "",
  media: [],
  my_reactions: ["helpful"],
  status: "visible",
  visibility: "everyone",
} satisfies Schemas["PostOut"];

export const JOB = {
  id: 301,
  title: "Frontend intern",
  description: "Build the stock and reorder screens for pharmacies in Adyar and Velachery.",
  kind: "internship",
  is_open: true,
  sector: "healthtech",
  startup_id: 41,
  startup_name: "Aravind Pathology",
  location: "Adyar, Chennai",
  lat: 13.0067,
  lng: 80.2573,
  distance_km: 4.2,
  stipend_min: 12000,
  stipend_max: 15000,
  skill_match: 0.82,
  applied: false,
  created_at: minutes(60 * 30),
  capabilities: [{ slug: "frontend-dev", name: "Frontend", required: true, your_level: 3 }, { slug: "ui-design", name: "UI design", required: false, your_level: 2 }],
} satisfies Schemas["JobOut"];

export const PULSE = {
  caught_up: true,
  next_cursor: null,
  items: [
    { key: "post-101", kind: "post", created_at: POST.created_at, seen: false, post: POST },
    { key: "role-301", kind: "role", created_at: JOB.created_at, seen: false, role: JOB },
    { key: "activity-1", kind: "activity", created_at: minutes(60 * 26), seen: false, activity: { type: "circuit_completed", circuit_id: 12 } },
    { key: "post-102", kind: "post", created_at: POST_TEXT.created_at, seen: false, post: POST_TEXT },
    { key: "skills-1", kind: "skills_in_demand", created_at: minutes(60 * 30), seen: false, skills_in_demand: { skills: [{ slug: "frontend-dev", name: "Frontend", open_roles: 9 }, { slug: "marketing", name: "Marketing", open_roles: 6 }, { slug: "data-analysis", name: "Data analysis", open_roles: 4 }] } },
  ],
} satisfies Schemas["PulseOut"];

const strength = (s: "strong" | "good") => s;

export const DROP_CARDS = [
  { member: PEOPLE.asha, reason: "Asha is building a Kannada voice assistant and needs a frontend developer. You build interfaces in React and have shipped two.", strength: strength("strong"), help_with: "frontend development", offers_you_need: ["mentoring"], via: PEOPLE.lakshmi, image: null, is_bridge: false, outcome: null },
  { member: PEOPLE.kavya, reason: "Kavya sells assay kits to hospital labs and needs help with marketing. Your classmate Divya did her first campaign.", strength: strength("good"), help_with: "marketing", offers_you_need: [], via: null, image: null, is_bridge: true, outcome: null },
  { member: PEOPLE.arjun, reason: "Arjun is hiring a frontend intern 4 km from you. The stipend is ₹12,000 to ₹15,000 a month.", strength: strength("good"), help_with: "frontend development", offers_you_need: ["ui-design"], via: null, image: null, is_bridge: false, outcome: null },
] satisfies Schemas["DropCardOut"][];

export const dropOf = (cards: Schemas["DropCardOut"][]) =>
  ({ cards, date: new Date().toISOString().slice(0, 10), done: cards.every((c) => c.outcome), next_drop_at: new Date(Date.now() + 14 * 3600_000).toISOString() }) satisfies Schemas["DropOut"];

export const MATCHES = [
  { candidate_id: 5, display_name: "Dr. Kavya Subramanian", role: "founder", city: "Chennai", sector: "healthtech", verification_level: 3, strength: "strong", is_bridge: true, reason: "Kavya needs marketing for lab buyers, which you offer. You both prefer long, careful sales." },
  { candidate_id: 6, display_name: "Rohan Gupta", role: "founder", city: "Chennai", sector: "logistics", verification_level: 2, strength: "good", is_bridge: false, reason: "Rohan needs a frontend developer for his kirana dashboard. You are 3 km apart." },
  { candidate_id: 8, display_name: "Divya Menon", role: "founder", city: "Chennai", sector: "climate", verification_level: 2, strength: "good", is_bridge: false, reason: "Divya needs data visualisation help and offers mentoring on pitching." },
  { candidate_id: 9, display_name: "Sneha Pillai", role: "founder", city: "Chennai", sector: "fintech", verification_level: 1, strength: "good", is_bridge: false, reason: "Sneha wants a design review of her sign-up flow. You offer UI design." },
  { candidate_id: 7, display_name: "Dr. Lakshmi Narayanan", role: "mentor", city: "Chennai", sector: null, verification_level: 3, strength: "good", is_bridge: false, reason: "Lakshmi offers mentoring on first sales calls, which you asked for." },
] satisfies Schemas["MatchOut"][];

const wire = (key: string, kind: Schemas["WireItemOut"]["kind"], actor: Schemas["AuthorOut"] | null, headline: string, reason: string, mins: number, seen: boolean, action: Schemas["WireActionOut"]["kind"]): Schemas["WireItemOut"] =>
  ({ key, kind, actor, startup: null, headline, reason, created_at: minutes(mins), seen, image: null, action: { kind: action, target_id: action === "view_role" ? 301 : actor?.id ?? 1 } }); // a role points at a mock job (mocks/discover.ts)

export const LIVEWIRE = [
  wire("w1", "shipped", PEOPLE.arjun, "Arjun shipped the stock-alert screen", "He builds with the same tools you do.", 95, false, "reply"),
  wire("w2", "hiring", PEOPLE.rohan, "Rohan is hiring a frontend intern", "4 km away, ₹12,000 to ₹15,000 a month.", 180, false, "view_role"),
  wire("w3", "needs", PEOPLE.kavya, "Kavya needs a marketer for lab buyers", "You offer marketing support.", 240, false, "intro"),
  wire("w4", "joined", PEOPLE.divya, "Divya joined from your college", "Same department, one year ahead.", 400, true, "intro"),
  wire("w5", "circuit_closed", PEOPLE.sneha, "Sneha closed a circuit with two founders", "Three people helped each other this week.", 900, true, "reply"),
] satisfies Schemas["WireItemOut"][];

export const INTRO = {
  id: 501,
  message: "",
  my_role: "requester",
  stage: "broker",
  status: "pending",
  can_respond: false,
  outcome_rating: null,
  created_at: minutes(0),
  expires_at: new Date(Date.now() + 7 * 86400_000).toISOString(),
  requester: { id: 1, display_name: "Ravi Kumar", role: "student", verification_level: 1 },
  target: { id: 2, display_name: "Asha Raman", role: "founder", verification_level: 2 },
  via: { id: 7, display_name: "Dr. Lakshmi Narayanan", role: "mentor", verification_level: 3 },
} satisfies Schemas["IntroOut"];

const note = (id: number, kind: string, text: string, actor: Schemas["AuthorOut"] | null, target: Schemas["TargetOut"] | null, mins: number, read: boolean): Schemas["NotificationOut"] =>
  ({ id, kind, text, actor: actor && { id: actor.id, display_name: actor.display_name, role: actor.role, verification_level: actor.verification_level }, target, payload: {}, read, created_at: minutes(mins) });

/** Newest first, as the API sends them: a few minutes ago, yesterday, and a few days back. Two are unread. */
export const NOTIFICATIONS = [
  note(1, "intro.accepted", `${PEOPLE.lakshmi.display_name} accepted your introduction.`, PEOPLE.lakshmi, { type: "intro", id: 501 }, 8, false),
  note(2, "application.status", "Your application has a new status.", null, { type: "application", id: 9 }, 30, false),
  note(3, "circuit.proposed", "A new circuit is waiting for your answer.", null, { type: "circuit", id: 12 }, 50, true),
  note(4, "post.reply", `${PEOPLE.divya.display_name} replied to your build log.`, PEOPLE.divya, { type: "post", id: 201 }, 60 * 26, true),
  note(5, "message.new", "Farhan Ali sent you a message.", author(22, "Farhan Ali", "student", "Maps and mobile, final year"), { type: "conversation", id: 502 }, 60 * 28, true), // a chat in mocks/inbox.ts
  note(6, "startup.interest", "Someone showed interest in your startup.", null, { type: "startup", id: 41 }, 60 * 24 * 3, true),
  note(7, "intro.received", `${PEOPLE.kavya.display_name} would like to meet you.`, PEOPLE.kavya, { type: "intro", id: 502 }, 60 * 24 * 3 + 40, true),
] satisfies Schemas["NotificationOut"][];

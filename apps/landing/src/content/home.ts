import type { Role } from "@/lib/env";

export const SRC = "landing-home";

/** One tile per audience: the line and call to action come from DESIGN.md §4 "Landing site". */
export const AUDIENCES: ReadonlyArray<{ role: Role; id: string; who: string; line: string; cta: string }> = [
  { role: "student", id: "students", who: "Students", line: "Startups near you want your skills, not your college name.", cta: "Find work near you" },
  { role: "founder", id: "founders", who: "Founders", line: "Find people who can help you, and students who want to work with you.", cta: "Claim your startup" },
  { role: "mentor", id: "mentors", who: "Mentors", line: "Help founders who need exactly what you know.", cta: "Start mentoring" },
  { role: "investor", id: "investors", who: "Investors", line: "Three startups a day that fit your thesis. No noise.", cta: "Set your focus" },
  { role: "partner", id: "partners", who: "Partners", line: "See what your ecosystem is missing, and fix it.", cta: "Bring Circuit to your campus" },
];

/** `shot` is the file in public/shots (without extension); null = the screen doesn't exist in the app yet, so a labelled placeholder is shown. */
export const STEPS: ReadonlyArray<{ n: string; title: string; body: string; shot: string | null; alt: string; missing: string }> = [
  { n: "01", title: "Say what you need and offer", body: "Paste a bio. We suggest your skills; you confirm them in a few taps.", shot: null, alt: "", missing: "You offer" },
  { n: "02", title: "Get three matches a day", body: "Each one comes with the reason and the mutual connection who can introduce you.", shot: "daily-drop", alt: "The Daily Drop in the Circuit app: a person to meet, with the reason they match you and an Intro me button.", missing: "Daily Drop" },
  { n: "03", title: "Meet through people you trust", body: "Warm intros and three-way circuits where everyone helps someone.", shot: null, alt: "", missing: "Circuit ring" },
];

export const FAQ: ReadonlyArray<{ q: string; a: string }> = [
  { q: "Is Circuit free?", a: "Yes for students, founders, mentors and investors. Startups can pay to promote a role, always labelled as promoted." },
  { q: "Why is it invite-only?", a: "We are starting with one city and one partner college so every match is worth your time." },
  { q: "What do you do with my data?", a: "We use it to match you. We never sell it, and you can export or delete it any time from Settings." },
  { q: "I am under 18. Can I join?", a: "Yes, with a private profile by default and no messages from strangers." },
  { q: "Do you charge investors or founders a fee on deals?", a: "No. Circuit only makes introductions. No success fees, ever." },
];

export const WAITLIST_ROLES: ReadonlyArray<{ value: Role; label: string }> = [
  { value: "student", label: "Student" },
  { value: "founder", label: "Founder" },
  { value: "mentor", label: "Mentor" },
  { value: "investor", label: "Investor" },
  { value: "partner", label: "Partner (college, incubator, programme)" },
];

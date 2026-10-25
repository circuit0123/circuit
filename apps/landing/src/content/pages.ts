import type { AudiencePageContent, Slug, Step } from "./types";

/** The same real screenshot as the home page (public/shots/daily-drop-*). */
const DAILY_DROP_ALT = "The Daily Drop in the Circuit app: a person to meet, with the reason they match you and an Intro me button.";
const dailyDrop = (n: string, title: string, body: string): Step => ({ n, title, body, shot: "daily-drop", alt: DAILY_DROP_ALT, missing: "Daily Drop" });
const coming = (n: string, title: string, body: string, missing: string): Step => ({ n, title, body, shot: null, alt: "", missing });

const DATA_FAQ = { q: "What do you do with my data?", a: "We use it to match you. We never sell it, and you can export or delete it any time from Settings." };
const INVITE_FAQ = { q: "Why is it invite-only?", a: "We are starting with one city and one partner college so every match is worth your time." };

/** Copy for the five audience pages. Headlines and calls to action are the DESIGN.md §4 "Landing site" table. Honest answers only: nothing here promises a feature that isn't built. */
const ALL: ReadonlyArray<AudiencePageContent> = [
  {
    slug: "students",
    role: "student",
    who: "Students",
    title: "Circuit for students",
    description: "Startups near you want your skills, not your college name. Circuit matches students with nearby hiring startups on skills and proof of work.",
    headline: "Startups near you want your skills, not your college name.",
    subhead: "Show what you can build and what you want to learn. Circuit finds the startups near you that are hiring for exactly that.",
    cta: "Find work near you",
    steps: [
      coming("01", "Say what you can do", "Paste a bio. We suggest your skills from a fixed list; you confirm them in a few taps.", "You offer"),
      dailyDrop("02", "Get three matches a day", "Each one comes with the reason, and the mutual connection who can introduce you."),
      coming("03", "Apply in one tap", "Your profile is your application. Founders see applicants ranked by skill match, not by college.", "Apply"),
    ],
    faq: [
      { q: "Is Circuit free for students?", a: "Yes. Students never pay. Startups can pay to promote a role, always labelled as promoted, and promotion never changes your matches." },
      { q: "Does my college name affect my matches?", a: "No. We match on what you can do and what you need. Your college name is never used to rank you or the roles you see." },
      { q: "Do I need a CV or experience?", a: "No. Paste a short bio and confirm the skills we suggest. A build log of something you made counts for more than a title." },
      { q: "I am under 18. Can I join?", a: "Yes, with a private profile by default and no messages from strangers. You only see promoted roles from verified startups." },
      DATA_FAQ,
      INVITE_FAQ,
    ],
  },
  {
    slug: "founders",
    role: "founder",
    who: "Founders",
    title: "Circuit for founders",
    description: "Find people who can help you, and students who want to work with you. Claim your startup on Circuit and get matches with a reason for each.",
    headline: "Find people who can help you, and students who want to work with you.",
    subhead: "Say what you need and what you can offer. Circuit finds the people nearby who fit, and tells you why.",
    cta: "Claim your startup",
    steps: [
      coming("01", "Claim your startup", "We may already list it. Verify with your company email and the profile is yours.", "Claim"),
      coming("02", "Say what you need", "Hiring, marketing, fundraising help: pick from a fixed list, and add what you can offer back.", "You need"),
      dailyDrop("03", "Meet people with a reason", "Every match says why, and shows the mutual connection who can introduce you."),
    ],
    faq: [
      { q: "How does claiming work?", a: "Sign in, find your startup and verify with an email on your company’s domain. Once it is claimed, what you write is never overwritten by our data." },
      { q: "What if my startup isn’t listed?", a: "You can create it yourself when you sign up, with your own details." },
      { q: "Is Circuit free for founders?", a: "Yes. You can pay to promote your startup, a role or a build log. Promotions are always labelled Promoted and never change who you are matched with." },
      { q: "Do you take a fee when I hire or raise money?", a: "No. Circuit only makes introductions. No success fees, ever." },
      DATA_FAQ,
      INVITE_FAQ,
    ],
  },
  {
    slug: "mentors",
    role: "mentor",
    who: "Mentors",
    title: "Circuit for mentors",
    description: "Help founders who need exactly what you know. Circuit introduces mentors to founders on what they need, with the reason shown first.",
    headline: "Help founders who need exactly what you know.",
    subhead: "Tell us what you can offer. Circuit introduces you to founders who need it, with the reason and a mutual connection where there is one.",
    cta: "Start mentoring",
    steps: [
      coming("01", "Say what you can offer", "Pick from a fixed list of skills and topics. Add what you would like help with too.", "You offer"),
      dailyDrop("02", "See why someone matches", "Each introduction shows the reason before you decide anything."),
      coming("03", "Join a circuit", "Three people, each helping the next. Nothing starts without your yes.", "Circuit ring"),
    ],
    faq: [
      { q: "How much time does it take?", a: "You set how many introductions you accept each week, and you can turn it off any time. A circuit asks for one specific favour, and you have 72 hours to say yes or no." },
      { q: "Can I say no?", a: "Yes. Every introduction and every circuit needs your consent." },
      { q: "Does Circuit cost anything for mentors?", a: "No. Mentors use Circuit for free." },
      { q: "Do I need to be verified?", a: "You can start with an email address. Verifying a work email adds a badge that helps founders trust a request from you." },
      DATA_FAQ,
    ],
  },
  {
    slug: "investors",
    role: "investor",
    who: "Investors",
    title: "Circuit for investors",
    description: "Three startups a day that fit your thesis, from founders who chose to be seen by investors. Circuit only makes introductions.",
    headline: "Three startups a day that fit your thesis. No noise.",
    subhead: "Set your sectors, stages and cities once. Each morning at 8:00 IST you get three startups that fit, from founders who chose to be seen by investors.",
    cta: "Set your focus",
    steps: [
      coming("01", "Set your focus", "Sectors, stages and cities. A cheque range is optional.", "Investor focus"),
      coming("02", "Get three picks each morning", "A short list that stays the same all day, each with the reason it fits.", "Today’s picks"),
      coming("03", "Ask for an introduction", "The founder decides whether to say yes. Unverified investors can browse but can’t request introductions.", "Introduction request"),
    ],
    faq: [
      { q: "Do you take a fee on deals?", a: "No. Circuit only makes introductions: no deal-making, no investment handling, no success fees." },
      { q: "Which startups can I see?", a: "Only startups whose founders switched on “Open to investor conversations”. It is off by default." },
      { q: "Who decides on an introduction?", a: "The founder. They get your request and say yes or no." },
      { q: "Will promoted startups show up in my picks?", a: "No. Promotion never changes your picks." },
      DATA_FAQ,
    ],
  },
  {
    slug: "partners",
    role: "partner",
    who: "Partners",
    title: "Circuit for colleges, incubators and programmes",
    description: "See what your ecosystem is missing, and fix it. A dashboard of your own members’ needs and offers, aggregates only.",
    headline: "See what your ecosystem is missing, and fix it.",
    subhead: "A dashboard of what your own members need and offer, so you can see the gaps and act on them. Aggregates only.",
    cta: "Bring Circuit to your campus",
    steps: [
      coming("01", "We verify your organisation", "We check your official email domain or website before you get admin powers.", "Organisation page"),
      coming("02", "Invite your members", "Students and startups join with your invite link, or when they verify an email on your domain.", "Invite"),
      coming("03", "See the gaps", "A gap chart and heatmap of what your members need and offer. Counts under 5 are hidden.", "Partner home"),
    ],
    faq: [
      { q: "What can you see about our members?", a: "Aggregates: counts and gaps. You see an individual profile only if that member or startup chose to share it with your organisation or joined your cohort." },
      { q: "Do we see other organisations’ members?", a: "Never. Your dashboard covers your own organisation only." },
      { q: "Are small numbers shown?", a: "No. Any count under 5 is hidden, so nobody can be picked out of a small group." },
      { q: "How do you verify an organisation?", a: "A person on our team checks your official email domain or website. Until then you have no admin powers." },
      DATA_FAQ,
    ],
  },
];

/** Pages that have a route. A page is added here when it ships, so the header, footer and sitemap never link to one that doesn't exist yet. */
const BUILT: ReadonlyArray<Slug> = ["students", "founders", "mentors", "investors"];
export const PAGES: ReadonlyArray<AudiencePageContent> = ALL.filter((p) => BUILT.includes(p.slug));

export const page = (slug: Slug): AudiencePageContent => {
  const p = ALL.find((x) => x.slug === slug);
  if (!p) throw new Error(`No page content for ${slug}`);
  return p;
};

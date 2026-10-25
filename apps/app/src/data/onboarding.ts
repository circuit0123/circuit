"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import type { Accent } from "@circuit/ui";
import { useAppearance } from "./appearance";
import { api, unwrap } from "./client";
import { problemOf } from "./errors";
import { useFeatures } from "./features";
import { useJoinContext } from "./join";
import { useKey } from "./keys";
import { useMe } from "./me";
import { MOCK } from "./mocks/config";
import type { Place } from "./where";
import { useSession } from "./session";

export type OnboardingState = {
  branch: "default" | "investor" | "partner";
  steps: string[];
  skip: string[];
  currentStep: string | null;
  completed: boolean;
  answers: Record<string, unknown>;
  signupSource: string;
};

type Raw = {
  branch: OnboardingState["branch"];
  steps: string[];
  skip: string[];
  current_step: string | null;
  completed_at: string | null;
  answers: Record<string, unknown>;
  signup_source: string;
};

const toState = (s: Raw): OnboardingState => ({
  branch: s.branch,
  steps: s.steps,
  skip: s.skip,
  currentStep: s.current_step,
  completed: !!s.completed_at,
  answers: s.answers,
  signupSource: s.signup_source,
});

/** Where the person is in onboarding. One call; the screen order and the skips come from the server. */
export function useOnboardingState(enabled = true) {
  const k = useKey("onboarding");
  return useQuery({
    queryKey: k.key,
    enabled: k.enabled && enabled,
    queryFn: async (): Promise<OnboardingState> => toState(await unwrap(api.GET("/api/onboarding/state"))),
  });
}

/* -------------------------------------------------------------------------------------------------------------------- */

/** The screens this build draws, in DESIGN.md §4 order (steps 4–14). Investor and partner screens come with their flags. */
export type StepId = "name" | "role" | "age" | "safety" | "where" | "work" | "offers" | "needs" | "organisation" | "photo" | "colour" | "ready";
const SCREENS: readonly StepId[] = ["name", "role", "age", "safety", "where", "work", "offers", "needs", "organisation", "photo", "colour", "ready"];

export type RoleChoice = "student" | "founder" | "mentor" | "invest" | "partner";
const ROLE_ROWS: ReadonlyArray<{ choice: RoleChoice; label: string; flag?: "investor_mode" | "partner_mode" }> = [
  { choice: "student", label: "Find work and internships" },
  { choice: "founder", label: "Build a startup" },
  { choice: "mentor", label: "Mentor people" },
  { choice: "invest", label: "Invest", flag: "investor_mode" },
  { choice: "partner", label: "Run a college or incubator programme", flag: "partner_mode" },
];
/** What `?role=` on a link means. */
const JOIN_ROLE: Record<string, RoleChoice> = { student: "student", founder: "founder", mentor: "mentor", investor: "invest", partner: "partner" };

/** The "What brings you here?" rows. A row whose feature is off isn't there (DESIGN.md §3). */
export function useRoleChoices() {
  const features = useFeatures();
  return ROLE_ROWS.filter((r) => !r.flag || features.on(r.flag));
}

export const LIMITS = { offers: 5, needs: 3 } as const;
const MIN_BIO = 10;

type Answers = Record<string, Record<string, unknown> | undefined>;
type Suggestions = { offers: string[]; needs: string[]; skills: string[]; traits: string[] };
const NONE: Suggestions = { offers: [], needs: [], skills: [], traits: [] };

/** Which of the steps show, in order. Pure: the same inputs give the same list, so a reload resumes in the same place. */
function visibleSteps(o: { steps: string[]; skipped: string[]; answers: Answers; joinRole?: RoleChoice; organisationKnown: boolean; roleChoice?: RoleChoice }): StepId[] {
  return o.steps.filter((s): s is StepId => (SCREENS as readonly string[]).includes(s)).filter((s) => {
    switch (s) {
      case "safety": return o.answers.age?.adult === false; // the server can't know the age answer yet (PROGRESS.md "Frontend → API needed")
      case "role": return !o.joinRole;
      case "organisation": return o.roleChoice === "student" && !o.organisationKnown && !o.skipped.includes(s);
      case "photo": return MOCK && !o.skipped.includes(s); // API needed: no avatar upload endpoint yet
      default: return !o.skipped.includes(s);
    }
  });
}

const sentence = (e: unknown) => {
  const p = problemOf(e);
  return p.kind === "network" || p.kind === "rate_limited" ? p.message : "Couldn't save that. Try again.";
};

/**
 * The sign-up flow (DESIGN.md §4 steps 4–14). Owns which screen shows, what each answer does, and saving: every answer is saved as the
 * person moves on (`PATCH /api/onboarding/state`), so closing the app resumes on the same screen with the same answers. Screens call
 * `actions.<step>(…)`; each returns true once saved and moved on, false (with `error` set, nothing cleared) if it failed.
 */
export function useOnboarding() {
  const qc = useQueryClient();
  const k = useKey("onboarding");
  const state = useOnboardingState().data;
  const me = useMe().data;
  const { identity, source } = useSession();
  const join = useJoinContext();
  const roleRows = useRoleChoices();
  const { appearance, save: saveAppearance } = useAppearance();

  // The server's "skip" list is read once, when the flow opens: saving the name makes the server skip it, and the screen must not vanish under the person.
  const [skipped] = useState(() => state?.skip ?? []);
  const [view, setView] = useState<StepId | null>(null);
  const [direction, setDirection] = useState<1 | -1>(1);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [organisationKnown, setOrganisationKnown] = useState(false);
  const startAccent = useRef<Accent | null>(null);
  startAccent.current ??= appearance?.accent ?? "emerald";

  const answers = (state?.answers ?? {}) as Answers;
  const joinRole = join.role ? JOIN_ROLE[join.role] : undefined;
  const linkRole = joinRole && roleRows.some((r) => r.choice === joinRole) ? joinRole : undefined;
  const roleChoice = (answers.role?.choice as RoleChoice | undefined) ?? linkRole;
  const visible = visibleSteps({ steps: state?.steps ?? [], skipped, answers, joinRole: linkRole, organisationKnown, roleChoice });

  const resume = (): StepId => {
    const saved = state?.currentStep as StepId | null | undefined;
    if (saved && visible.includes(saved)) return saved;
    return visible.find((s) => s !== "ready" && !answers[s]) ?? "ready";
  };
  const current: StepId = view && visible.includes(view) ? view : resume();
  const index = Math.max(0, visible.indexOf(current));
  const progress = visible.length ? (index + 1) / visible.length : 0;

  const patchState = useCallback(
    async (patch: { current_step?: StepId; answers?: Record<string, Record<string, unknown>>; completed?: boolean }) => {
      const body: Record<string, unknown> = { ...patch };
      if (join.src && !state?.signupSource) body.signup_source = join.src;
      const out = await unwrap(api.PATCH("/api/onboarding/state", { body: body as never }));
      qc.setQueryData(k.key, toState(out as Raw));
      return out as Raw;
    },
    [join.src, qc, k.key, state?.signupSource],
  );
  const patchMe = (body: Record<string, unknown>) => unwrap(api.PATCH("/api/me", { body: body as never })).then(() => qc.invalidateQueries({ queryKey: ["me"] }));

  /** Runs one step's work, saves the answer and moves to the next visible screen. */
  const run = async (step: StepId, work: () => Promise<Record<string, unknown>>) => {
    setSaving(true);
    setError(null);
    try {
      const answer = await work();
      const after = { ...answers, [step]: answer } as Answers;
      const list = visibleSteps({ steps: state?.steps ?? [], skipped, answers: after, joinRole: linkRole, organisationKnown, roleChoice: step === "role" ? (answer.choice as RoleChoice) : roleChoice });
      const next = list[list.indexOf(step) + 1] ?? "ready";
      await patchState({ current_step: next, answers: { [step]: answer } });
      setDirection(1);
      setView(next);
      return true;
    } catch (e) {
      setError(sentence(e));
      return false;
    } finally {
      setSaving(false);
    }
  };

  // A link that names the role (`/join?role=founder`) answers the Role question for the person: save it once, quietly.
  const roleSaved = useRef(false);
  useEffect(() => {
    if (!state || !linkRole || roleSaved.current || answers.role?.choice === linkRole) return;
    roleSaved.current = true;
    void (async () => {
      try {
        if (linkRole !== "partner") await patchMe({ role: linkRole === "invest" ? "investor" : linkRole });
        await patchState({ answers: { role: { choice: linkRole } } });
      } catch { /* the Role answer is saved again with the next step; nothing to show */ }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- once, when the state first arrives
  }, [state, linkRole]);

  // Students whose sign-in email is on a college's domain are already members of it: the "Where do you study?" step is skipped (inference before asking).
  const tried = useRef(false);
  useEffect(() => {
    if (tried.current || roleChoice !== "student" || me?.organisationId || source !== "supabase" || !identity?.email) return;
    tried.current = true;
    unwrap(api.POST("/api/organisations/join-by-email"))
      .then(() => { setOrganisationKnown(true); void qc.invalidateQueries({ queryKey: ["me"] }); })
      .catch(() => { /* no college on this domain: ask */ });
  }, [roleChoice, me?.organisationId, source, identity?.email, qc]);

  const suggestions = ((answers.work?.suggestions as Suggestions | undefined) ?? NONE);
  const putList = (path: "/api/me/offers" | "/api/me/needs", slugs: string[]) =>
    unwrap(api.PUT(path, { body: slugs.map((capability) => ({ capability, description: "" })) }));

  const actions = {
    name: (first: string, last: string) =>
      run("name", async () => {
        const display_name = [first.trim(), last.trim()].filter(Boolean).join(" ");
        await patchMe({ display_name });
        return { first: first.trim(), last: last.trim() };
      }),
    role: (choice: RoleChoice) =>
      run("role", async () => {
        if (choice !== "partner") await patchMe({ role: choice === "invest" ? "investor" : choice });
        return { choice };
      }),
    age: (adult: boolean) => run("age", async () => ({ adult })),
    safety: () =>
      run("safety", async () => {
        // Under-18 defaults the API lets us set today (PROGRESS.md "Frontend → API needed": the age answer should set is_minor itself).
        await unwrap(api.PATCH("/api/me/privacy", { body: { profile_visibility: "hidden", allow_requests: false } }));
        return { seen: true };
      }),
    where: (place: Place) =>
      run("where", async () => {
        await patchMe({ lat: place.lat, lng: place.lng, ...(place.city ? { city: place.city } : {}) });
        return { city: place.city };
      }),
    work: (text: string | null) =>
      run("work", async () => {
        const bio = (text ?? "").trim();
        if (!bio) return { skipped: true, source: "manual" };
        await patchMe({ bio: bio.slice(0, 2000) });
        if (bio.length < MIN_BIO) return { source: "manual" };
        try {
          const r = await unwrap(api.POST("/api/onboarding/extract", { body: { bio: bio.slice(0, 2000) } }));
          return { source: r.source, suggestions: r.suggestions };
        } catch {
          return { source: "manual" }; // the AI being down is never an error for the person: they get the pickers
        }
      }),
    offers: (slugs: string[]) =>
      run("offers", async () => {
        await putList("/api/me/offers", slugs);
        // What the AI read from the bio also fills skills and traits (fixed lists only); best effort, the person edits them on Profile.
        if (suggestions.skills.length) void unwrap(api.PUT("/api/me/skills", { body: suggestions.skills.slice(0, 8).map((capability) => ({ capability, level: 1, proof_url: "" })) })).catch(() => {});
        if (suggestions.traits.length) void unwrap(api.PUT("/api/me/traits", { body: suggestions.traits.slice(0, 10) })).catch(() => {});
        return { slugs };
      }),
    needs: (slugs: string[]) =>
      run("needs", async () => {
        await putList("/api/me/needs", slugs);
        return { slugs };
      }),
    organisation: (name: string | null) =>
      run("organisation", async () => {
        if (!name?.trim()) return { skipped: true };
        await patchMe({ college: name.trim().slice(0, 200) });
        return { name: name.trim() };
      }),
    photo: (chosen: boolean) => run("photo", async () => (chosen ? { chosen: true } : { skipped: true })),
    colour: (skip: boolean) =>
      run("colour", async () => {
        if (skip) saveAppearance.mutate({ accent: startAccent.current ?? "emerald" });
        return skip ? { skipped: true } : { accent: appearance?.accent ?? "emerald" };
      }),
    /** The last screen: marks sign-up finished. The gate then opens the app. */
    finish: async () => {
      setSaving(true);
      setError(null);
      try {
        await patchState({ current_step: "ready", completed: true });
        join.clear();
        return true;
      } catch (e) {
        setError(sentence(e));
        return false;
      } finally {
        setSaving(false);
      }
    },
  };

  const back = () => {
    const prev = visible[index - 1];
    if (!prev) return;
    setError(null);
    setDirection(-1);
    setView(prev);
    void patchState({ current_step: prev }).catch(() => {});
  };

  return {
    ready: !!state,
    current,
    direction,
    progress,
    /** False on the first screen: nothing to go back to inside sign-up. */
    canGoBack: index > 0,
    back,
    saving,
    error,
    answers,
    suggestions,
    /** Role chosen on a link, or on the Role screen. */
    roleChoice,
    actions,
    /** Whether the AI's suggestions were usable; false means show the searchable list straight away. */
    aiWorked: answers.work?.source === "llm",
    /** The rows for the Role screen. */
    roles: roleRows,
    /** The accent now, and a way to try one (applied at once, saved in the background). */
    accent: appearance?.accent ?? "emerald",
    setAccent: (a: Accent) => saveAppearance.mutate({ accent: a }),
  };
}

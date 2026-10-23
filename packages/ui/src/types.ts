/** Plain view types. The UI package knows nothing about the API; apps map responses into these. */
export type Person = {
  id: number;
  name: string;
  /** Role label already in plain words, e.g. "Student". */
  role: string;
  headline: string;
  place: string;
  level: number;
  photo?: string | null;
};

export type MediaItem = { src: string; srcSmall: string; alt: string; width: number | null; height: number | null };

export type PostView = {
  id: number;
  author: Person;
  body: string;
  tags: string[];
  link: string;
  media: MediaItem[];
  /** Short relative time such as "2h". */
  when: string;
  mine: boolean;
  reactions: Array<"helpful" | "intro_me" | "lets_talk">;
};

export type RoleView = {
  id: number;
  title: string;
  startup: string;
  place: string;
  km: number | null;
  stipend: string | null;
  /** 0–100, or null when we cannot say. */
  match: number | null;
  tags: string[];
};

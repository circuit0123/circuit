/** The phone screens in public/screens (rendered from the design reference by `make landing-screens`). Every picture shows sample data, never real people or startups. */
export type ScreenId =
  | "home-main" | "home-match" | "discover-jobs" | "map" | "circuits" | "job" | "people" | "inbox" | "chat" | "investor-picks" | "partner-home";

export const SCREEN_SIZE = { width: 780, height: 1688 } as const;

export const SCREENS: Record<ScreenId, { alt: string; caption: string }> = {
  "home-main": {
    alt: "Home in the Circuit app: a row of recent updates from people nearby, and today's first match with the reason, a mutual connection and an Intro me button.",
    caption: "Today: three matches a day, each with the reason.",
  },
  "home-match": {
    alt: "A match card in the Circuit app showing a Bridge match: a growth lead from a different sector who can help with go-to-market, the shared connection, and an Intro me button.",
    caption: "A match with the reason, and a Bridge badge when it crosses sectors.",
  },
  "discover-jobs": {
    alt: "The Jobs tab in the Circuit app: roles that fit your skills near you, with the startup, the distance, the pay in rupees and how strongly your skills match.",
    caption: "Jobs: roles that fit your skills, with pay and distance.",
  },
  map: {
    alt: "The startup map in the Circuit app: pins for startups nearby, hiring ones in green, and a card for the selected startup with its open role and an I'm interested button.",
    caption: "Map: who is hiring near you.",
  },
  circuits: {
    alt: "An exchange circuit in the Circuit app: a ring of three people, what you give and what you get, and Accept and Decline buttons.",
    caption: "Circuits: three people, each helping the next.",
  },
  job: {
    alt: "A job page in the Circuit app: stipend, duration and start date, the skills you match, a description of the role and an Apply with your profile button.",
    caption: "A job page: what it pays, what it needs, and your fit.",
  },
  people: {
    alt: "The People tab in the Circuit app: people near you matched on skills, each with their role and how well they match, including a Bridge match.",
    caption: "People: matched on skills, not job titles.",
  },
  inbox: {
    alt: "The Inbox in the Circuit app: a list of conversations with the latest message, the time and unread dots, and a Requests tab.",
    caption: "Inbox: conversations, and a separate place for requests.",
  },
  chat: {
    alt: "A conversation in the Circuit app where a mentor offers to introduce you to someone who can solve the problem you mentioned.",
    caption: "A conversation that leads to a warm introduction.",
  },
  "investor-picks": {
    alt: "Today's picks in the Circuit app: one startup that fits an investor's focus, with its stage, sector, recent activity and a Request intro button.",
    caption: "Today's picks: a short list with the reason for each.",
  },
  "partner-home": {
    alt: "The partner home in the Circuit app: things that need attention, this week's numbers for the organisation's members, and open calls and events.",
    caption: "Partner home: what needs attention, and how your members are doing.",
  },
};

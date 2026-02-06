export type RedesignId =
  | "mission-control"
  | "financial-terminal"
  | "editorial-intelligence"
  | "brutalist-lab"
  | "glass-operations";

export type RedesignMeta = {
  id: RedesignId;
  title: string;
  tone: string;
  summary: string;
  path: `/redesigns/${RedesignId}`;
};

export const REDESIGNS: RedesignMeta[] = [
  {
    id: "mission-control",
    title: "Mission Control",
    tone: "Aerospace operations console",
    summary:
      "Dense telemetry framing with a command-rail layout and cool cyan signals.",
    path: "/redesigns/mission-control",
  },
  {
    id: "financial-terminal",
    title: "Financial Terminal",
    tone: "Market floor analytics",
    summary:
      "Compact strips, numeric hierarchy, and trading-desk readability for rapid scanning.",
    path: "/redesigns/financial-terminal",
  },
  {
    id: "editorial-intelligence",
    title: "Editorial Intelligence",
    tone: "Magazine-grade data story",
    summary:
      "Narrative sections, warm paper textures, and elegant report-like pacing.",
    path: "/redesigns/editorial-intelligence",
  },
  {
    id: "brutalist-lab",
    title: "Brutalist Lab",
    tone: "Raw research artifact",
    summary:
      "Hard edges and oversized labels designed to feel explicit, urgent, and opinionated.",
    path: "/redesigns/brutalist-lab",
  },
  {
    id: "glass-operations",
    title: "Glass Operations",
    tone: "Premium observability cockpit",
    summary:
      "Layered translucent panels with atmospheric depth and a high-end control-room feel.",
    path: "/redesigns/glass-operations",
  },
];

export function getRedesign(id: RedesignId): RedesignMeta {
  return REDESIGNS.find((entry) => entry.id === id) ?? REDESIGNS[0];
}

export function getRedesignCycle(id: RedesignId) {
  const index = REDESIGNS.findIndex((entry) => entry.id === id);
  if (index < 0) {
    return {
      previous: REDESIGNS[REDESIGNS.length - 1],
      next: REDESIGNS[0],
    };
  }
  const previous = REDESIGNS[(index - 1 + REDESIGNS.length) % REDESIGNS.length];
  const next = REDESIGNS[(index + 1) % REDESIGNS.length];
  return { previous, next };
}

export type Loop = {
  id: string;
  filename: string;
  bpm: number;
  key: string;
  bars: number;
  seconds: number;
  trim_to_bars?: boolean;
  role: Role;
  subgenre: Subgenre;
};
export type Clip = { lane: string; loop_id: string };
export type Section = { id: string; name: string; bars: number; clips: Clip[] };
export type Project = {
  genre: "dnb";
  subgenre?: Subgenre;
  bpm: number;
  loops: Loop[];
  sections: Section[];
};
export type Suggestion = {
  kind: "tip" | "length" | "next";
  text: string;
  bars?: number;
  name?: string;
};
export const names = [
  "Intro",
  "Build",
  "Drop 1",
  "Breakdown",
  "Build 2",
  "Drop 2",
  "Outro",
];
export const initial: Project = {
  genre: "dnb",
  bpm: 174,
  loops: [],
  sections: [],
};
export function move(sections: Section[], from: number, to: number): Section[] {
  const copy = [...sections];
  const [section] = copy.splice(from, 1);
  copy.splice(to, 0, section);
  return copy;
}
export function applySuggestion(
  project: Project,
  id: string,
  suggestion: Suggestion,
): Project {
  const index = project.sections.findIndex((s) => s.id === id);
  if (index < 0) return project;
  const sections = [...project.sections];
  if (suggestion.kind === "length")
    sections[index] = { ...sections[index], bars: suggestion.bars! };
  if (suggestion.kind === "next")
    sections.splice(index + 1, 0, {
      id: crypto.randomUUID(),
      name: suggestion.name!,
      bars: suggestion.bars!,
      clips: [],
    });
  return { ...project, sections };
}

export const roles = ["Drop", "Intro", "Breakdown", "Build", "Other"] as const;
export type Role = (typeof roles)[number];
export const subgenres = [
  "General",
  "Liquid",
  "Neurofunk",
  "Jump-up",
  "Rollers",
] as const;
export type Subgenre = (typeof subgenres)[number];
export type ImportedLoop = Omit<Loop, "role"> & { suggested_role: Role };
export type Variation = {
  kind: "Full" | "Low-pass" | "High-pass" | "Filter sweep" | "Quieter" | "Fade";
  cutoff: number;
  gain: number;
};
export type Pending = { section: string; loop: string; variation: Variation };
export function matchesRole(role: Role, name: string): boolean {
  const matching: Record<Role, string[]> = {
    Drop: ["Drop 1", "Drop 2"],
    Intro: ["Intro"],
    Breakdown: ["Breakdown"],
    Build: ["Build"],
    Other: [],
  };
  return matching[role].includes(name);
}
export function confirmLoop(
  project: Project,
  loop: Loop,
  template: Section[],
): Project {
  if (!roles.includes(loop.role)) throw new Error("Confirm a loop role first");
  const sections = project.sections.length ? project.sections : template;
  return {
    ...project,
    subgenre: loop.subgenre,
    loops: [...project.loops, loop],
    sections: sections.map((s) =>
      matchesRole(loop.role, s.name) && !s.clips.some((c) => c.lane === "Loop")
        ? { ...s, clips: [...s.clips, { lane: "Loop", loop_id: loop.id }] }
        : s,
    ),
  };
}
export function variationFor(name: string): Variation {
  return {
    kind: name.startsWith("Build")
      ? "Filter sweep"
      : name === "Breakdown"
        ? "High-pass"
        : name === "Outro"
          ? "Fade"
          : name.startsWith("Drop")
            ? "Full"
            : "Low-pass",
    cutoff: name.startsWith("Build") ? 300 : name === "Breakdown" ? 400 : 500,
    gain:
      name.startsWith("Drop") || name.startsWith("Build")
        ? 1
        : name === "Breakdown"
          ? 0.63
          : 0.5,
  };
}

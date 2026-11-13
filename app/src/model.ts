export type Loop = {
  id: string;
  filename: string;
  bpm: number;
  key: string;
  bars: number;
  seconds: number;
};
export type Clip = { lane: string; loop_id: string };
export type Section = { id: string; name: string; bars: number; clips: Clip[] };
export type Project = {
  genre: "dnb";
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

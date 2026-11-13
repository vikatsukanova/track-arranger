import { describe, expect, it } from "vitest";
import { applySuggestion, move, type Project } from "./model";
const project: Project = {
  genre: "dnb",
  bpm: 174,
  loops: [],
  sections: [
    { id: "a", name: "Intro", bars: 8, clips: [] },
    { id: "b", name: "Drop 1", bars: 32, clips: [] },
  ],
};
describe("producer-controlled arrangement", () => {
  it("reorders whole sections without mutating the project", () => {
    expect(move(project.sections, 0, 1).map((s) => s.id)).toEqual(["b", "a"]);
    expect(project.sections[0].id).toBe("a");
  });
  it("applies only the accepted length change", () => {
    const result = applySuggestion(project, "a", {
      kind: "length",
      bars: 16,
      text: "Extend",
    });
    expect(result.sections[0].bars).toBe(16);
    expect(result.sections[1]).toEqual(project.sections[1]);
    expect(project.sections[0].bars).toBe(8);
  });
  it("inserts an empty next section after the selected one", () => {
    const result = applySuggestion(project, "a", {
      kind: "next",
      name: "Build",
      bars: 16,
      text: "Build next",
    });
    expect(result.sections.map((s) => s.name)).toEqual([
      "Intro",
      "Build",
      "Drop 1",
    ]);
    expect(result.sections[1].clips).toEqual([]);
  });
});

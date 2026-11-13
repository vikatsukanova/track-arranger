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

import { confirmLoop, initial, type Loop } from "./model";
const confirmed: Loop = {
  id: "loop",
  filename: "tone.wav",
  bpm: 174,
  key: "C",
  bars: 8,
  seconds: 11,
  role: "Drop",
  subgenre: "Liquid",
};
const template = [
  "Intro",
  "Build",
  "Drop 1",
  "Breakdown",
  "Build 2",
  "Drop 2",
  "Outro",
].map((name, i) => ({
  id: String(i),
  name,
  bars: name.startsWith("Drop")
    ? 48
    : name.startsWith("Build")
      ? 16
      : name === "Breakdown"
        ? 32
        : 16,
  clips: [],
}));
it.each([
  ["Drop", [2, 5]],
  ["Intro", [0]],
  ["Build", [1]],
  ["Breakdown", [3]],
  ["Other", []],
] as const)(
  "places confirmed %s only in matching sections",
  (role, expected) => {
    const result = confirmLoop(initial, { ...confirmed, role }, template);
    expect(
      result.sections.flatMap((s, i) => (s.clips.length ? [i] : [])),
    ).toEqual(expected);
    expect(template.every((s) => s.clips.length === 0)).toBe(true);
    expect(result.subgenre).toBe("Liquid");
  },
);
it("preserves an existing structure and occupied lanes", () => {
  const existing = {
    ...initial,
    sections: [
      {
        id: "custom",
        name: "Drop 1",
        bars: 24,
        clips: [{ lane: "Loop", loop_id: "mine" }],
      },
    ],
  };
  expect(confirmLoop(existing, confirmed, template).sections).toEqual(
    existing.sections,
  );
});
it("requires explicit confirmation of a role", () => {
  expect(() =>
    confirmLoop(
      initial,
      { ...confirmed, role: undefined } as unknown as Loop,
      template,
    ),
  ).toThrow("Confirm");
});

import { placeLoops, variationFor } from "./model";
it("repopulates a suggested structure with matching clips and pending variations", () => {
  const result = placeLoops({
    ...initial,
    loops: [confirmed],
    sections: template,
  });
  expect(
    result.sections.filter((s) => s.clips.length).map((s) => s.name),
  ).toEqual(["Drop 1", "Drop 2"]);
  expect(result.pending.map((p) => p.section)).toEqual([
    "0",
    "1",
    "3",
    "4",
    "6",
  ]);
  expect(template.every((s) => s.clips.length === 0)).toBe(true);
});
it("refills both drops with the remaining re-imported loop after the old one is removed", () => {
  const old = placeLoops({
    ...initial,
    loops: [confirmed],
    sections: template,
  });
  const replacement = { ...confirmed, id: "replacement" };
  const imported = confirmLoop(
    { ...initial, loops: [confirmed], sections: old.sections },
    replacement,
    template,
  );
  const removed = { ...imported, loops: [replacement] };
  const result = placeLoops(removed, old.pending);
  expect(
    result.sections
      .filter((s) => s.name.startsWith("Drop"))
      .map((s) => s.clips[0]?.loop_id),
  ).toEqual(["replacement", "replacement"]);
  expect(result.pending.every((p) => p.loop === "replacement")).toBe(true);
  const reimported = placeLoops(
    { ...initial, loops: [], sections: template },
    old.pending,
  );
  const restored = placeLoops(
    confirmLoop(
      { ...initial, ...reimported, loops: [] },
      replacement,
      template,
    ),
    reimported.pending,
  );
  expect(
    restored.sections
      .filter((s) => s.name.startsWith("Drop"))
      .every((s) => s.clips.length),
  ).toBe(true);
});
it("drops stale saved suggestions and retains modified and skipped suggestions on restore", () => {
  const modified = {
    section: "0",
    loop: confirmed.id,
    variation: { ...variationFor("Intro"), cutoff: 350 },
  };
  const skipped = {
    section: "1",
    loop: confirmed.id,
    variation: variationFor("Build"),
    skipped: true,
  };
  const stale = {
    section: "3",
    loop: "missing",
    variation: variationFor("Breakdown"),
  };
  const project = { ...initial, loops: [confirmed], sections: template };
  const result = placeLoops(project, [modified, skipped, stale]);
  expect(result.pending).toContainEqual(modified);
  expect(result.pending).toContainEqual(skipped);
  expect(result.pending.some((p) => p.loop === "missing")).toBe(false);
  expect(
    placeLoops({ ...project, sections: result.sections }, result.pending),
  ).toEqual(result);
});

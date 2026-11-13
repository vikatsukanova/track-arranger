import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  Playback,
  playbackPosition,
  previewPlan,
  sectionTimes,
} from "./playback";
import { api, audioBlob } from "./api";
import { variationFor, type Loop, type Pending, type Project } from "./model";
vi.mock("./api", () => ({ api: vi.fn(), audioBlob: vi.fn() }));
const loop: Loop = {
  id: "loop",
  filename: "tone.wav",
  bpm: 174,
  bars: 8,
  seconds: (8 * 240) / 174,
  key: "C",
  role: "Drop",
  subgenre: "General",
};
const project: Project = {
  genre: "dnb",
  bpm: 174,
  loops: [loop],
  sections: [
    { id: "intro", name: "Intro", bars: 8, clips: [] },
    {
      id: "drop",
      name: "Drop 1",
      bars: 8,
      clips: [{ lane: "Loop", loop_id: loop.id }],
    },
    { id: "outro", name: "Outro", bars: 8, clips: [] },
  ],
};
const pending: Pending[] = [
  { section: "intro", loop: loop.id, variation: variationFor("Intro") },
];

describe("arrangement preview", () => {
  it("includes pending audio without committing suggestions; skipped sections stay silent", async () => {
    const before = JSON.stringify({ project, pending });
    const render = vi.fn().mockResolvedValue({ ...loop, id: "rendered" });
    const plan = await previewPlan(project, pending, render);
    expect(
      plan.map((s) => s.clips.map((c) => [c.loop.id, c.suggestion])),
    ).toEqual([[["rendered", true]], [["loop", false]], []]);
    expect(render).toHaveBeenCalledTimes(1);
    expect(JSON.stringify({ project, pending })).toBe(before);
    const skipped = await previewPlan(project, [], render);
    expect(skipped[0].clips).toEqual([]);
  });
  it("uses occupied Loop clips instead of a stale pending suggestion", async () => {
    const render = vi.fn();
    const plan = await previewPlan(
      project,
      [{ ...pending[0], section: "drop" }],
      render,
    );
    expect(plan[1].clips).toHaveLength(1);
    expect(plan[1].clips[0].suggestion).toBe(false);
    expect(render).not.toHaveBeenCalled();
  });
  it("shares exact sample boundaries between consecutive sections", async () => {
    const plan = await previewPlan(project, [], vi.fn());
    for (const rate of [44100, 48000]) {
      const times = plan.map((s) => sectionTimes(s, project.bpm, rate, 10));
      expect(times[0].end).toBe(times[1].start);
      expect(times[1].end).toBe(times[2].start);
      expect(times[2].end).toBe(
        10 + Math.round(((24 * 240) / 174) * rate) / rate,
      );
    }
  });
  it("derives playhead bars and sections from audio time and resets at the end", async () => {
    const plan = await previewPlan(project, pending, async () => loop);
    expect(playbackPosition(plan, 174, 48000, 10, 9)).toEqual({
      bar: 0,
      section: "intro",
      suggestion: true,
    });
    expect(
      playbackPosition(plan, 174, 48000, 10, 10 + (4 * 240) / 174)?.bar,
    ).toBeCloseTo(4);
    const boundary = sectionTimes(plan[1], 174, 48000, 10).start;
    expect(playbackPosition(plan, 174, 48000, 10, boundary)).toMatchObject({
      section: "drop",
      suggestion: false,
    });
    expect(
      playbackPosition(
        plan,
        174,
        48000,
        10,
        sectionTimes(plan[2], 174, 48000, 10).end,
      ),
    ).toBeNull();
  });
});

describe("audio scheduling and caching", () => {
  let sources: {
    start: ReturnType<typeof vi.fn>;
    stop: ReturnType<typeof vi.fn>;
    disconnect: ReturnType<typeof vi.fn>;
  }[];
  let now: number;
  let frame: () => void;
  beforeEach(() => {
    vi.clearAllMocks();
    sources = [];
    now = 5;
    vi.stubGlobal(
      "requestAnimationFrame",
      vi.fn((callback) => {
        frame = callback;
        return 1;
      }),
    );
    vi.stubGlobal("cancelAnimationFrame", vi.fn());
    vi.stubGlobal(
      "AudioContext",
      class {
        sampleRate = 48000;
        get currentTime() {
          return now;
        }
        destination = {};
        resume = vi.fn().mockResolvedValue(undefined);
        decodeAudioData = vi
          .fn()
          .mockResolvedValue({ duration: (8 * 240) / 174 });
        createBufferSource() {
          const source = {
            start: vi.fn(),
            stop: vi.fn(),
            disconnect: vi.fn(),
            connect: vi.fn(),
          };
          sources.push(source);
          return source;
        }
      },
    );
    vi.mocked(api).mockResolvedValue({ ...loop, id: "rendered" });
    vi.mocked(audioBlob).mockResolvedValue(new Blob(["audio"]));
  });
  it("schedules pending and accepted clips back to back and reuses render/audio caches", async () => {
    const playback = new Playback();
    const progress = vi.fn();
    await playback.play(project, pending, progress);
    expect(sources).toHaveLength(2);
    expect(sources[0].stop.mock.calls[0][0]).toBe(
      sources[1].start.mock.calls[0][0],
    );
    expect(progress).toHaveBeenLastCalledWith({
      bar: 0,
      section: "intro",
      suggestion: true,
    });
    await playback.play(project, pending, progress);
    expect(api).toHaveBeenCalledTimes(1);
    expect(audioBlob).toHaveBeenCalledTimes(2);
    now = 100;
    frame();
    expect(progress).toHaveBeenLastCalledWith(null);
    await playback.play(project, pending, progress);
    playback.stop();
    expect(progress).toHaveBeenLastCalledWith(null);
    expect(cancelAnimationFrame).toHaveBeenCalled();
  });
  it("leaves the cursor at natural end and restarts playback from the end bar", async () => {
    const playback = new Playback();
    const progress = vi.fn();
    await playback.play(project, pending, progress);
    now = 100;
    frame();
    const lastPosition = progress.mock.calls
      .filter(([position]) => position !== null)
      .at(-1)![0];
    expect(lastPosition.bar).toBe(24);
    sources = [];
    await playback.play(project, pending, progress, lastPosition.bar);
    expect(sources).toHaveLength(2);
    expect(sources[0].start.mock.calls[0][1]).toBe(0);
    expect(progress).toHaveBeenLastCalledWith({
      bar: 0,
      section: "intro",
      suggestion: true,
    });
  });
  it("starts mid-section with the correct offset and skips earlier sections", async () => {
    const playback = new Playback();
    await playback.play(project, pending, vi.fn(), 4);
    expect(sources[0].start.mock.calls[0][1]).toBeCloseTo((4 * 240) / 174);
    expect(sources[0].stop.mock.calls[0][0]).toBe(
      sources[1].start.mock.calls[0][0],
    );
    playback.stop();
    sources = [];
    await playback.play(project, pending, vi.fn(), 12);
    expect(sources).toHaveLength(1);
    expect(sources[0].start.mock.calls[0][1]).toBeCloseTo((4 * 240) / 174);
  });
  it("invalidates the render when variation parameters, duration or tempo change", async () => {
    const playback = new Playback();
    await playback.variation(loop, project.sections[0], 174, pending[0]);
    await playback.variation(loop, project.sections[0], 174, {
      ...pending[0],
      variation: { ...pending[0].variation, cutoff: 400 },
    });
    await playback.variation(
      loop,
      { ...project.sections[0], bars: 16 },
      174,
      pending[0],
    );
    await playback.variation(loop, project.sections[0], 172, pending[0]);
    expect(api).toHaveBeenCalledTimes(4);
  });
});

it("uses clearly audible default variation parameters", () => {
  expect(variationFor("Intro")).toMatchObject({
    kind: "Low-pass",
    cutoff: 500,
    gain: 0.5,
  });
  expect(variationFor("Breakdown")).toMatchObject({
    kind: "High-pass",
    cutoff: 400,
    gain: 0.63,
  });
  expect(variationFor("Build")).toMatchObject({
    kind: "Filter sweep",
    cutoff: 300,
    gain: 1,
  });
  expect(variationFor("Outro")).toMatchObject({
    kind: "Fade",
    cutoff: 500,
    gain: 0.5,
  });
});

import { seekOffset, shouldToggleTransport } from "./playback";
it("keeps loop phase when seeking into a section", () => {
  expect(seekOffset(19, 16, 8, 174)).toBeCloseTo((3 * 240) / 174);
  expect(seekOffset(27, 16, 8, 174)).toBeCloseTo((3 * 240) / 174);
  // A rendered suggestion spans its section, so its sweep/fade keeps its phase.
  expect(seekOffset(27, 16, 32, 174)).toBeCloseTo((11 * 240) / 174);
});
it("ignores space while typing, editing selections, or holding the key", () => {
  const OriginalElement = globalThis.Element;
  class Target {
    constructor(private editing: boolean) {}
    closest() {
      return this.editing ? this : null;
    }
  }
  vi.stubGlobal("Element", Target);
  const event = (editing: boolean, overrides = {}) =>
    ({
      code: "Space",
      target: new Target(editing),
      ...overrides,
    }) as unknown as KeyboardEvent;
  expect(shouldToggleTransport(event(false))).toBe(true);
  expect(shouldToggleTransport(event(true))).toBe(false);
  expect(shouldToggleTransport(event(false, { repeat: true }))).toBe(false);
  expect(shouldToggleTransport(event(false, { code: "Enter" }))).toBe(false);
  vi.stubGlobal("Element", OriginalElement);
});

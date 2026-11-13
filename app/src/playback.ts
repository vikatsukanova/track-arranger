import { api, audioBlob } from "./api";
import type { Loop, Pending, Project, Section } from "./model";

export type PreviewSection = {
  id: string;
  startBar: number;
  endBar: number;
  clips: { loop: Loop; suggestion: boolean }[];
};
export type Position = { bar: number; section: string; suggestion: boolean };

export async function previewPlan(
  project: Project,
  pending: Pending[],
  render: (item: Pending, section: Section, loop: Loop) => Promise<Loop>,
): Promise<PreviewSection[]> {
  let bar = 0;
  const result: PreviewSection[] = [];
  for (const section of project.sections) {
    const clips = section.clips.map((c) => ({
      loop: project.loops.find((l) => l.id === c.loop_id)!,
      suggestion: false,
    }));
    if (!section.clips.some((c) => c.lane === "Loop")) {
      for (const item of pending.filter((p) => p.section === section.id)) {
        const loop = project.loops.find((l) => l.id === item.loop);
        if (loop)
          clips.push({
            loop: await render(item, section, loop),
            suggestion: true,
          });
      }
    }
    result.push({
      id: section.id,
      startBar: bar,
      endBar: bar + section.bars,
      clips,
    });
    bar += section.bars;
  }
  return result;
}

export function sectionTimes(
  section: PreviewSection,
  bpm: number,
  sampleRate: number,
  start: number,
) {
  return {
    start:
      start +
      Math.round(((section.startBar * 240) / bpm) * sampleRate) / sampleRate,
    end:
      start +
      Math.round(((section.endBar * 240) / bpm) * sampleRate) / sampleRate,
  };
}

export function playbackPosition(
  plan: PreviewSection[],
  bpm: number,
  sampleRate: number,
  start: number,
  now: number,
): Position | null {
  const section = plan.find(
    (s) => now < sectionTimes(s, bpm, sampleRate, start).end,
  );
  if (!section) return null;
  return {
    bar: Math.max(
      section.startBar,
      Math.min(section.endBar, (Math.max(0, now - start) * bpm) / 240),
    ),
    section: section.id,
    suggestion: section.clips.some((c) => c.suggestion),
  };
}

export class Playback {
  private context?: AudioContext;
  private nodes: AudioBufferSourceNode[] = [];
  private version = 0;
  private frame = 0;
  private onPosition?: (position: Position | null) => void;
  private variations = new Map<string, Promise<Loop>>();
  private buffers = new Map<string, AudioBuffer>();

  variation(
    loop: Loop,
    section: Section,
    bpm: number,
    item: Pending,
  ): Promise<Loop> {
    const request = {
      loop,
      bars: section.bars,
      bpm,
      variation: item.variation,
    };
    const key = JSON.stringify(request);
    let rendered = this.variations.get(key);
    if (!rendered) {
      rendered = api<Loop>("/variations", request).catch((error) => {
        this.variations.delete(key);
        throw error;
      });
      this.variations.set(key, rendered);
    }
    return rendered;
  }

  stop() {
    this.version++;
    cancelAnimationFrame(this.frame);
    this.nodes.forEach((n) => {
      n.stop();
      n.disconnect();
    });
    this.nodes = [];
    this.onPosition?.(null);
    this.onPosition = undefined;
  }

  async play(
    project: Project,
    pending: Pending[] = [],
    onPosition?: (position: Position | null) => void,
  ) {
    this.stop();
    const version = this.version;
    this.onPosition = onPosition;
    const context = (this.context ||= new AudioContext());
    await context.resume();
    const plan = await previewPlan(project, pending, (item, section, loop) =>
      this.variation(loop, section, project.bpm, item),
    );
    const buffers = new Map<string, AudioBuffer>();
    for (const { loop } of plan.flatMap((s) => s.clips)) {
      const key = JSON.stringify([loop.id, project.bpm, loop.bars]);
      let buffer = this.buffers.get(key);
      if (!buffer) {
        buffer = await context.decodeAudioData(
          await (
            await audioBlob(loop.id, project.bpm, loop.bars)
          ).arrayBuffer(),
        );
        this.buffers.set(key, buffer);
      }
      buffers.set(loop.id, buffer);
    }
    if (version !== this.version) return;
    const start =
      Math.ceil((context.currentTime + 0.1) * context.sampleRate) /
      context.sampleRate;
    for (const section of plan) {
      const times = sectionTimes(
        section,
        project.bpm,
        context.sampleRate,
        start,
      );
      for (const { loop } of section.clips) {
        const source = context.createBufferSource();
        source.buffer = buffers.get(loop.id)!;
        source.loop = true;
        source.connect(context.destination);
        source.start(times.start);
        source.stop(times.end);
        this.nodes.push(source);
      }
    }
    const tick = () => {
      if (version !== this.version) return;
      const position = playbackPosition(
        plan,
        project.bpm,
        context.sampleRate,
        start,
        context.currentTime,
      );
      if (!position) {
        this.stop();
        return;
      }
      this.onPosition?.(position);
      this.frame = requestAnimationFrame(tick);
    };
    tick();
  }
}

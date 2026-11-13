import { audioBlob } from "./api";
import type { Project } from "./model";
export class Playback {
  private context?: AudioContext;
  private nodes: AudioBufferSourceNode[] = [];
  private version = 0;
  stop() {
    this.version++;
    this.nodes.forEach((n) => n.stop());
    this.nodes = [];
  }
  async play(project: Project) {
    this.stop();
    const version = this.version;
    const context = (this.context ||= new AudioContext());
    await context.resume();
    const buffers = new Map<string, AudioBuffer>();
    for (const id of new Set(
      project.sections.flatMap((s) => s.clips.map((c) => c.loop_id)),
    )) {
      const loop = project.loops.find((l) => l.id === id)!;
      buffers.set(
        id,
        await context.decodeAudioData(
          await (await audioBlob(id, project.bpm, loop.bars)).arrayBuffer(),
        ),
      );
    }
    if (version !== this.version) return;
    let start = context.currentTime + 0.1;
    for (const section of project.sections) {
      const duration = (section.bars * 240) / project.bpm;
      for (const clip of section.clips) {
        const source = context.createBufferSource();
        source.buffer = buffers.get(clip.loop_id)!;
        source.loop = true;
        source.connect(context.destination);
        source.start(start);
        source.stop(start + duration);
        this.nodes.push(source);
      }
      start += duration;
    }
  }
}

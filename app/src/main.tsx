import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { isTauri } from "@tauri-apps/api/core";
import { getCurrentWebview } from "@tauri-apps/api/webview";
import { ask, open } from "@tauri-apps/plugin-dialog";
import {
  AudioLines,
  Plus,
  Upload,
  ArrowRight,
  ChevronLeft,
  ChevronRight,
  Minus,
  X,
  Download,
  Sparkles,
  Check,
  SkipForward,
  FolderOpen,
  RotateCcw,
} from "lucide-react";
import { Playback, type Position } from "./playback";
import { audioBlob } from "./api";
import {
  confirmLoop,
  matchesRole,
  roles,
  subgenres,
  variationFor,
  type ImportedLoop,
  type Pending,
  type Role,
  type Subgenre,
  type Variation,
} from "./model";
import { api, connect } from "./api";
import {
  applySuggestion,
  initial,
  move,
  names,
  type Loop,
  type Project,
  type Section,
  type Suggestion,
} from "./model";
import "./style.css";

function App() {
  const [project, setProject] = useState<Project>(() => {
    try {
      return (
        JSON.parse(localStorage.getItem("track-arranger-v1") || "null") ||
        initial
      );
    } catch {
      return initial;
    }
  });
  const [imports, setImports] = useState<ImportedLoop[]>([]);
  const [role, setRole] = useState<Role>("Drop");
  const [subgenre, setSubgenre] = useState<Subgenre>("General");
  const [pending, setPending] = useState<Pending[]>(() => {
    try {
      return JSON.parse(
        localStorage.getItem("track-arranger-pending-v1") || "[]",
      );
    } catch {
      return [];
    }
  });
  const importing = useRef(false);
  const busyRef = useRef(false);
  const projectRef = useRef(project);
  projectRef.current = project;
  const player = useRef(new Playback());
  const audition = useRef<HTMLAudioElement | null>(null);
  const audioUrl = useRef("");
  const audioVersion = useRef(0);
  const [playing, setPlaying] = useState("");
  const [position, setPosition] = useState<Position | null>(null);
  function stopAudio() {
    audioVersion.current++;
    player.current.stop();
    audition.current?.pause();
    audition.current = null;
    URL.revokeObjectURL(audioUrl.current);
    audioUrl.current = "";
    setPlaying("");
    setPosition(null);
  }
  async function preview(id: string) {
    if (playing === id && audition.current) {
      if (audition.current.paused) await audition.current.play();
      else audition.current.pause();
      return;
    }
    stopAudio();
    const version = audioVersion.current;
    const blob = await audioBlob(id);
    if (version !== audioVersion.current) return;
    audioUrl.current = URL.createObjectURL(blob);
    audition.current = new Audio(audioUrl.current);
    setPlaying(id);
    await audition.current.play();
  }
  useEffect(() => {
    stopAudio();
    localStorage.setItem("track-arranger-pending-v1", JSON.stringify(pending));
  }, [pending]);
  useEffect(() => {
    if (imports[0]) {
      setRole(imports[0].suggested_role);
      setSubgenre(project.subgenre || "General");
    }
  }, [imports[0]?.id]);
  const [selected, setSelected] = useState("");
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [tips, setTips] = useState<Record<string, string[]>>({});
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [accepted, setAccepted] = useState<Record<string, string[]>>(() => {
    try {
      return JSON.parse(
        localStorage.getItem("track-arranger-notes-v1") || "{}",
      );
    } catch {
      return {};
    }
  });
  useEffect(() => {
    localStorage.setItem("track-arranger-notes-v1", JSON.stringify(accepted));
  }, [accepted]);
  const [laneDraft, setLaneDraft] = useState("");
  const [extraLanes, setExtraLanes] = useState<string[]>([]);
  const [loopChoice, setLoopChoice] = useState("");
  const [format, setFormat] = useState("ableton");
  const fileInput = useRef<HTMLInputElement>(null);
  const suggestionVersion = useRef(0);
  const resize = useRef<{ id: string; x: number; bars: number } | null>(null);
  const active = project.sections.find((s) => s.id === selected);
  const lanes = Array.from(
    new Set([
      "Loop",
      "Drums",
      "Bass",
      "Texture",
      ...extraLanes,
      ...project.sections.flatMap((s) => s.clips.map((c) => c.lane)),
    ]),
  );
  const totalBars = project.sections.reduce((n, s) => n + s.bars, 0);
  const minutes = (totalBars * 240) / project.bpm / 60;

  async function run(label: string, action: () => Promise<void>) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(label);
    setError("");
    setMessage("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      busyRef.current = false;
      setBusy("");
    }
  }
  useEffect(() => {
    let live = true;
    connect()
      .then(async () => {
        const all =
          await api<Record<string, Record<string, string[]>>>("/tips");
        if (live) {
          setTips(all.dnb);
          setReady(true);
        }
      })
      .catch((e) => {
        if (live) setError(String(e.message));
      });
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    stopAudio();
    localStorage.setItem("track-arranger-v1", JSON.stringify(project));
    suggestionVersion.current++;
    setSuggestions([]);
  }, [project]);
  useEffect(() => {
    suggestionVersion.current++;
    setSuggestions([]);
  }, [selected]);
  async function importPaths(paths: string[]) {
    if (busyRef.current || importing.current || imports.length) return;
    importing.current = true;
    await run("Analyzing loops…", async () => {
      for (const path of paths) {
        const loops = await api<ImportedLoop[]>("/loops/import", {
          paths: [path],
        });
        setImports((p) => [...p, ...loops]);
      }
    });
    importing.current = false;
  }
  useEffect(() => {
    if (!isTauri() || !ready) return;
    const subscription = getCurrentWebview().onDragDropEvent((event) => {
      if (event.payload.type === "drop") void importPaths(event.payload.paths);
    });
    return () => {
      void subscription.then((unlisten) => unlisten());
    };
  }, [ready, imports.length]);
  useEffect(() => {
    function onMove(e: PointerEvent) {
      if (!resize.current) return;
      const { id, x, bars } = resize.current;
      const length = Math.max(
        8,
        Math.min(256, bars + Math.round((e.clientX - x) / 48) * 8),
      );
      updateSection(id, { bars: length });
    }
    function onUp() {
      resize.current = null;
    }
    window.addEventListener("pointermove", onMove);
    window.addEventListener("pointerup", onUp);
    return () => {
      window.removeEventListener("pointermove", onMove);
      window.removeEventListener("pointerup", onUp);
    };
  }, []);
  function updateSection(id: string, patch: Partial<Section>) {
    setProject((p) => ({
      ...p,
      sections: p.sections.map((s) => (s.id === id ? { ...s, ...patch } : s)),
    }));
  }
  function updateLoop(id: string, patch: Partial<Loop>) {
    setProject((p) => ({
      ...p,
      loops: p.loops.map((l) => (l.id === id ? { ...l, ...patch } : l)),
    }));
  }
  async function upload(files: FileList | File[]) {
    if (busyRef.current || importing.current || imports.length || !ready)
      return;
    importing.current = true;
    await run("Analyzing loops…", async () => {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        const loop = await api<ImportedLoop>("/loops/upload", form);
        setImports((p) => [...p, loop]);
      }
    });
    importing.current = false;
  }
  async function suggestStructure() {
    await run("Generating structure…", async () => {
      if (
        project.sections.length &&
        !(isTauri()
          ? await ask("Replace the existing arrangement?", {
              title: "Suggest structure",
            })
          : window.confirm("Replace the existing arrangement?"))
      )
        return;
      const sections = await api<Section[]>("/arrangement");
      setProject((p) => ({ ...p, sections }));
      setPending([]);
      setSelected(sections[0].id);
    });
  }
  async function acceptImport() {
    await run("Placing confirmed loop…", async () => {
      const loop: Loop = { ...imports[0], role, subgenre };
      const template = project.sections.length
        ? []
        : await api<Section[]>("/arrangement");
      const next = confirmLoop(projectRef.current, loop, template);
      setProject(next);
      setPending((p) => [
        ...p,
        ...next.sections
          .filter(
            (s) =>
              !matchesRole(role, s.name) &&
              !s.clips.some((c) => c.lane === "Loop"),
          )
          .map((s) => ({
            section: s.id,
            loop: loop.id,
            variation: variationFor(s.name),
          })),
      ]);
      setSelected(next.sections[0]?.id || "");
      setImports((p) => p.slice(1));
    });
  }
  async function renderPending(item: Pending, accept: boolean) {
    await run(
      accept ? "Rendering accepted variation…" : "Preparing audition…",
      async () => {
        const section = project.sections.find((s) => s.id === item.section);
        const loop = project.loops.find((l) => l.id === item.loop);
        if (!section || !loop) return;
        if (accept && section.clips.some((c) => c.lane === "Loop"))
          throw new Error("Loop lane is occupied. Clear it before accepting.");
        const rendered = await player.current.variation(
          loop,
          section,
          project.bpm,
          item,
        );
        if (!accept) {
          await preview(rendered.id);
          return;
        }
        const current = projectRef.current.sections.find(
          (s) => s.id === item.section,
        );
        if (
          !current ||
          current.clips.some((c) => c.lane === "Loop") ||
          !projectRef.current.loops.some((l) => l.id === item.loop)
        )
          throw new Error("Arrangement changed. Review the suggestion again.");
        setProject((p) => ({
          ...p,
          loops: [...p.loops, rendered],
          sections: p.sections.map((s) =>
            s.id === section.id
              ? {
                  ...s,
                  clips: [...s.clips, { lane: "Loop", loop_id: rendered.id }],
                }
              : s,
          ),
        }));
        setPending((p) => p.filter((x) => x !== item));
      },
    );
  }
  async function browse() {
    if (!isTauri()) {
      fileInput.current?.click();
      return;
    }
    const paths = await open({
      multiple: true,
      filters: [
        { name: "Audio loops", extensions: ["wav", "aif", "aiff", "mp3"] },
      ],
    });
    if (paths) await importPaths(Array.isArray(paths) ? paths : [paths]);
  }
  function place(section: Section, lane: string, loop_id: string) {
    if (!project.loops.some((l) => l.id === loop_id && l.role)) return;
    updateSection(section.id, {
      clips: [
        ...section.clips.filter((c) => c.lane !== lane),
        { lane, loop_id },
      ],
    });
  }
  function reorder(id: string, target: string) {
    setProject((p) => ({
      ...p,
      sections: move(
        p.sections,
        p.sections.findIndex((s) => s.id === id),
        p.sections.findIndex((s) => s.id === target),
      ),
    }));
  }
  const disabled = !ready || !!busy || !!imports.length;
  return (
    <div className="app">
      <header>
        <div className="brand">
          <span className="brand-icon">
            <AudioLines size={24} />
          </span>
          <div>
            track arranger<small>FROM LOOP TO SOMETHING MORE</small>
          </div>
          <span className="version">v0.1</span>
        </div>
        <div className="local">
          <span /> Local engine · No AI · No cloud
        </div>
      </header>
      <div className="toolbar">
        <div className="project-title">
          <span className="eyebrow">YOUR WORKSPACE</span>
          <h1>
            A little structure.
            <br />
            <span>All your sound.</span>
          </h1>
        </div>
        <div className="settings">
          <label>
            GENRE
            <select
              value={project.subgenre || "General"}
              aria-label="Genre / subgenre"
              onChange={(e) =>
                setProject((p) => ({
                  ...p,
                  subgenre: e.target.value as Subgenre,
                }))
              }
            >
              {subgenres.map((g) => (
                <option key={g} value={g}>
                  Drum &amp; bass · {g}
                </option>
              ))}
            </select>
          </label>
          <label>
            TEMPO
            <div className="tempo">
              <input
                aria-label="Project tempo"
                type="number"
                min="160"
                max="180"
                value={project.bpm}
                onChange={(e) =>
                  setProject((p) => ({ ...p, bpm: Number(e.target.value) }))
                }
              />
              <span>BPM</span>
            </div>
          </label>
          <button
            className="primary"
            disabled={disabled}
            onClick={() => void suggestStructure()}
          >
            <Sparkles size={16} /> Suggest structure
          </button>
        </div>
      </div>
      <div className={`status ${busy ? "working" : ""}`} role="status">
        {busy ||
          message ||
          (ready
            ? "Engine ready. Your project is saved automatically on this device."
            : "Starting local audio engine…")}
      </div>
      {error && (
        <div role="alert" className="error">
          {error}
          <button aria-label="Dismiss error" onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      {imports[0] && (
        <form
          key={imports[0].id}
          className="import-confirm"
          aria-label="Confirm loop role"
          onSubmit={(e) => {
            e.preventDefault();
            void acceptImport();
          }}
        >
          <h2>Where does {imports[0].filename} belong?</h2>
          <p>
            {imports[0].bpm} BPM · {imports[0].key} · {imports[0].bars} bars ·
            Drum &amp; bass
          </p>
          <p>Role is a rough guess. Confirm before adding this loop.</p>
          <label>
            Loop role{" "}
            <select
              value={role}
              onChange={(e) => setRole(e.target.value as Role)}
            >
              {roles.map((r) => (
                <option key={r}>{r}</option>
              ))}
            </select>
          </label>
          <label>
            Subgenre{" "}
            <select
              value={subgenre}
              onChange={(e) => setSubgenre(e.target.value as Subgenre)}
            >
              {subgenres.map((g) => (
                <option key={g}>{g}</option>
              ))}
            </select>
          </label>
          <button autoFocus className="primary" disabled={!!busy}>
            Confirm loop
          </button>
          <button
            type="button"
            disabled={!!busy}
            onClick={() => setImports((p) => p.slice(1))}
          >
            Cancel
          </button>
        </form>
      )}
      <main>
        <aside className="library">
          <div className="panel-title">
            <h2>Loop library</h2>
            <span>{project.loops.length.toString().padStart(2, "0")}</span>
          </div>
          <p className="muted">Your starting point. Make it yours.</p>
          <button
            disabled={disabled}
            className="dropzone"
            aria-busy={busy === "Analyzing loops…"}
            onClick={() => void browse()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              void upload(e.dataTransfer.files);
            }}
          >
            <span>
              <Upload size={22} />
            </span>
            <strong>
              {busy === "Analyzing loops…" ? (
                <>
                  <span className="spinner" /> Analyzing loops…
                </>
              ) : (
                "Drop your loops here"
              )}
            </strong>
            <small>or click to browse · WAV, AIFF, MP3</small>
          </button>
          <input
            hidden
            ref={fileInput}
            type="file"
            multiple
            accept=".wav,.aiff,.aif,.mp3"
            onChange={(e) => {
              if (e.target.files) void upload(e.target.files);
              e.target.value = "";
            }}
          />
          <p className="eyebrow library-label">
            IMPORTED LOOPS <span>4/4</span>
          </p>
          <div className="loop-list" aria-busy={busy === "Analyzing loops…"}>
            {busy === "Analyzing loops…" && (
              <article className="loop-card pending">
                <span className="spinner" /> Analyzing your audio…
              </article>
            )}
            {project.loops.length === 0 && (
              <div className="empty-library">
                <AudioLines size={32} />
                <p>
                  An 8-bar loop is enough.
                  <br />
                  Bring something you’re excited about.
                </p>
              </div>
            )}
            {project.loops.map((loop, i) => (
              <article
                className={`loop-card ${loopChoice === loop.id ? "chosen" : ""}`}
                key={loop.id}
                draggable={!!loop.role}
                onDragStart={(e) => e.dataTransfer.setData("loop", loop.id)}
              >
                <button
                  className="loop-name"
                  onClick={() => setLoopChoice(loop.id)}
                  title="Select this loop, then click a lane to place it"
                >
                  <AudioLines size={18} />
                  <strong>{loop.filename}</strong>
                  <span>{String(i + 1).padStart(2, "0")}</span>
                </button>
                <button
                  onClick={() =>
                    void run("Loading audio…", () => preview(loop.id))
                  }
                >
                  Play / pause
                </button>
                <p>Drum &amp; bass · {loop.subgenre || "General"}</p>
                <label>
                  Subgenre{" "}
                  <select
                    value={loop.subgenre || "General"}
                    onChange={(e) =>
                      updateLoop(loop.id, {
                        subgenre: e.target.value as Subgenre,
                      })
                    }
                  >
                    {subgenres.map((g) => (
                      <option key={g}>{g}</option>
                    ))}
                  </select>
                </label>
                <label>
                  Role{" "}
                  <select
                    value={loop.role || ""}
                    onChange={(e) =>
                      updateLoop(loop.id, { role: e.target.value as Role })
                    }
                  >
                    <option disabled value="">
                      Confirm role
                    </option>
                    {roles.map((r) => (
                      <option key={r}>{r}</option>
                    ))}
                  </select>
                </label>
                <div className="loop-metadata">
                  <label>
                    BPM
                    <input
                      aria-label={`${loop.filename} BPM`}
                      type="number"
                      min="30"
                      max="300"
                      value={loop.bpm}
                      onChange={(e) => {
                        const bpm = Number(e.target.value);
                        updateLoop(loop.id, {
                          bpm,
                          bars: Math.max(
                            0.125,
                            Math.round(((loop.seconds * bpm) / 240) * 8) / 8,
                          ),
                        });
                      }}
                    />
                  </label>
                  <label>
                    KEY
                    <input
                      aria-label={`${loop.filename} key`}
                      value={loop.key}
                      onChange={(e) =>
                        updateLoop(loop.id, { key: e.target.value })
                      }
                    />
                  </label>
                  <label>
                    BARS
                    <input
                      aria-label={`${loop.filename} bars`}
                      type="number"
                      min=".125"
                      step=".125"
                      max="1024"
                      value={loop.bars}
                      onChange={(e) =>
                        updateLoop(loop.id, { bars: Number(e.target.value) })
                      }
                    />
                  </label>
                </div>
                <button
                  className="remove-loop"
                  aria-label={`Remove ${loop.filename}`}
                  onClick={() =>
                    setProject((p) => ({
                      ...p,
                      loops: p.loops.filter((l) => l.id !== loop.id),
                      sections: p.sections.map((s) => ({
                        ...s,
                        clips: s.clips.filter((c) => c.loop_id !== loop.id),
                      })),
                    }))
                  }
                >
                  <X size={12} /> Remove
                </button>
              </article>
            ))}
          </div>
          <div className="library-note">
            <span /> Detection is a starting point.
            <br />
            Edit BPM, key and bars anytime.
          </div>
        </aside>
        <section
          className="workspace"
          onDragOver={(e) => e.preventDefault()}
          onDrop={(e) => {
            if (e.dataTransfer.files.length) {
              e.preventDefault();
              void upload(e.dataTransfer.files);
            }
          }}
        >
          <div className="panel-title">
            <div>
              <h2>Arrangement</h2>
              <p className="muted">
                Shape the energy. Leave room for instinct.
              </p>
            </div>
            <div className="timeline-meta">
              {totalBars} bars <span>·</span> {Math.floor(minutes)}:
              {String(Math.round((minutes % 1) * 60)).padStart(2, "0")}
            </div>
          </div>
          <div className="timeline-controls">
            <button
              disabled={disabled || !project.sections.length}
              onClick={() =>
                void run("Loading arrangement…", async () => {
                  stopAudio();
                  await player.current.play(project, pending, (next) => {
                    setPosition(next);
                    setPlaying(next ? "arrangement" : "");
                  });
                })
              }
            >
              Play arrangement
            </button>
            <button onClick={stopAudio}>Stop</button>
            <span>
              <span className="green-dot" /> 8-BAR GRID
            </span>
            <div>
              <button
                disabled={!project.sections.length}
                onClick={async () => {
                  const question =
                    "Clear the arrangement? Your loops will stay in the library.";
                  if (
                    isTauri()
                      ? await ask(question, { title: "Clear arrangement" })
                      : window.confirm(question)
                  ) {
                    setProject((p) => ({ ...p, sections: [] }));
                    setPending([]);
                    setSelected("");
                  }
                }}
              >
                <RotateCcw size={13} /> Clear
              </button>
              <button
                disabled={project.sections.length >= 64}
                onClick={() => {
                  const section = {
                    id: crypto.randomUUID(),
                    name: "Intro",
                    bars: 16,
                    clips: [],
                  };
                  setProject((p) => ({
                    ...p,
                    sections: [...p.sections, section],
                  }));
                  setSelected(section.id);
                }}
              >
                <Plus size={14} /> Add section
              </button>
            </div>
          </div>
          {!project.sections.length ? (
            <div className="empty-timeline">
              <div className="mini-blocks">
                <i />
                <i />
                <i />
                <i />
              </div>
              <h3>Your loop has places to go.</h3>
              <button
                className="primary"
                disabled={disabled}
                onClick={() => void suggestStructure()}
              >
                Suggest structure
              </button>
              <p>
                Suggest a DnB structure to start shaping your track,
                <br />
                or add a section and build at your own pace.
              </p>
            </div>
          ) : (
            <div className="timeline-scroll">
              <div
                className="timeline"
                style={{ width: `${Math.max(680, totalBars * 6 + 86)}px` }}
              >
                {position && (
                  <div
                    className="playhead"
                    data-testid="playhead"
                    aria-label={`Playing bar ${Math.floor(position.bar) + 1}`}
                    style={{ left: 86 + position.bar * 6 }}
                  />
                )}
                <div className="ruler">
                  <span>BAR</span>
                  {Array.from({ length: Math.ceil(totalBars / 8) }, (_, i) => (
                    <span key={i} style={{ width: 48 }}>
                      {i * 8 + 1}
                    </span>
                  ))}
                </div>
                <div className="section-row">
                  <span className="row-label">SECTIONS</span>
                  {project.sections.map((section, i) => (
                    <div
                      className={`section-block color-${i % 4} ${selected === section.id ? "selected" : ""} ${position?.section === section.id ? "is-playing" : ""}`}
                      key={section.id}
                      style={{ width: section.bars * 6 }}
                      draggable
                      onDragStart={(e) =>
                        e.dataTransfer.setData("section", section.id)
                      }
                      onDragOver={(e) => e.preventDefault()}
                      onDrop={(e) => {
                        const id = e.dataTransfer.getData("section");
                        if (id) reorder(id, section.id);
                      }}
                    >
                      <button onClick={() => setSelected(section.id)}>
                        <span>{String(i + 1).padStart(2, "0")}</span>
                        <strong>{section.name}</strong>
                        <small>{section.bars} bars</small>
                        {position?.section === section.id &&
                          position.suggestion && (
                            <small className="playing-suggestion">
                              Suggestion
                            </small>
                          )}
                      </button>
                      <div
                        role="separator"
                        aria-label={`Resize ${section.name}`}
                        aria-orientation="vertical"
                        aria-valuemin={8}
                        aria-valuemax={256}
                        aria-valuenow={section.bars}
                        tabIndex={0}
                        className="resize"
                        onPointerDown={(e) => {
                          e.preventDefault();
                          resize.current = {
                            id: section.id,
                            x: e.clientX,
                            bars: section.bars,
                          };
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
                            e.preventDefault();
                            updateSection(section.id, {
                              bars: Math.max(
                                8,
                                Math.min(
                                  256,
                                  section.bars +
                                    (e.key === "ArrowRight" ? 8 : -8),
                                ),
                              ),
                            });
                          }
                        }}
                      />
                    </div>
                  ))}
                </div>
                {lanes.map((lane, index) => (
                  <div className="lane-row" key={lane}>
                    <span className="row-label">
                      <i className={`lane-dot color-${index % 4}`} />
                      {lane}
                    </span>
                    {project.sections.map((section) => {
                      const clip = section.clips.find((c) => c.lane === lane);
                      const loop = project.loops.find(
                        (l) => l.id === clip?.loop_id,
                      );
                      return (
                        <div
                          className="lane-cell"
                          key={section.id}
                          style={{ width: section.bars * 6 }}
                          onDragOver={(e) => e.preventDefault()}
                          onDrop={(e) => {
                            e.preventDefault();
                            place(
                              section,
                              lane,
                              e.dataTransfer.getData("loop"),
                            );
                          }}
                        >
                          <button
                            className={
                              loop ? `clip color-${index % 4}` : "empty-clip"
                            }
                            aria-label={`${section.name}, ${lane}: ${loop ? loop.filename + ". Click to remove" : "place selected loop"}`}
                            onClick={() => {
                              if (loopChoice) place(section, lane, loopChoice);
                              else if (clip)
                                updateSection(section.id, {
                                  clips: section.clips.filter(
                                    (c) => c.lane !== lane,
                                  ),
                                });
                              else setSelected(section.id);
                            }}
                          >
                            {loop ? (
                              <>
                                <AudioLines size={14} />
                                <span>{loop.filename}</span>
                                <small>↻</small>
                              </>
                            ) : (
                              <span>
                                {lane === "Loop" &&
                                pending.some(
                                  (p) =>
                                    p.section === section.id &&
                                    project.loops.some((l) => l.id === p.loop),
                                )
                                  ? "Review suggestion"
                                  : "Drop loop +"}
                              </span>
                            )}
                          </button>
                          {clip && (
                            <button
                              className="clip-remove"
                              aria-label={`Remove ${lane} from ${section.name}`}
                              onClick={() =>
                                updateSection(section.id, {
                                  clips: section.clips.filter(
                                    (c) => c.lane !== lane,
                                  ),
                                })
                              }
                            >
                              <X size={10} />
                            </button>
                          )}
                        </div>
                      );
                    })}
                  </div>
                ))}
                <div className="timeline-foot">
                  <form
                    className="add-lane"
                    onSubmit={(e) => {
                      e.preventDefault();
                      const name = laneDraft.trim();
                      if (name && !lanes.includes(name))
                        setExtraLanes((l) => [...l, name]);
                      setLaneDraft("");
                    }}
                  >
                    <input
                      aria-label="New lane name"
                      placeholder="New lane name"
                      value={laneDraft}
                      maxLength={80}
                      onChange={(e) => setLaneDraft(e.target.value)}
                    />
                    <button disabled={!laneDraft.trim()}>
                      <Plus size={12} /> Add lane
                    </button>
                  </form>
                  Drag loops into lanes · Loops repeat to fill each section ·
                  Drag section edges to resize
                </div>
              </div>
            </div>
          )}
          <div className="below-grid">
            <span>
              <AudioLines size={15} />{" "}
              {loopChoice
                ? `${project.loops.find((l) => l.id === loopChoice)?.filename || "Loop"} selected — click a lane to place`
                : "Drag a loop, or select one and click a lane."}
            </span>
            {loopChoice && (
              <button onClick={() => setLoopChoice("")}>Deselect loop</button>
            )}
          </div>
          <section className="export-panel">
            <div className="export-icon">
              <FolderOpen size={22} />
            </div>
            <div>
              <h3>Take it to your DAW</h3>
              <p>Keep creating where you feel at home.</p>
            </div>
            <select
              aria-label="Export format"
              value={format}
              onChange={(e) => setFormat(e.target.value)}
            >
              <option value="ableton">Ableton Live Set (.als)</option>
              <option value="logic">Logic audio + MIDI</option>
              <option value="midi">MIDI markers (.mid)</option>
            </select>
            <button
              disabled={disabled || !project.sections.length}
              onClick={() =>
                void run("Exporting project…", async () => {
                  const directory = isTauri()
                    ? await open({ directory: true })
                    : window.prompt(
                        "Absolute path to an existing export folder",
                      );
                  if (!directory || Array.isArray(directory)) return;
                  const result = await api<{ path: string }>("/export", {
                    project,
                    format,
                    directory,
                  });
                  setMessage(`Exported to ${result.path}`);
                })
              }
            >
              <Download size={16} /> Export
            </button>
          </section>
          <p className="producer-note">
            A starting point, never a finished song. You make every call.
          </p>
        </section>
        <aside className="inspector">
          <div className="panel-title">
            <h2>Section details</h2>
            <span className="eyebrow">YOUR CALL</span>
          </div>
          {active ? (
            <>
              <div className="inspector-heading">
                <span className="eyebrow">SELECTED SECTION</span>
                <select
                  aria-label="Section name"
                  value={active.name}
                  onChange={(e) =>
                    updateSection(active.id, { name: e.target.value })
                  }
                >
                  {[...new Set([...names, active.name])].map((name) => (
                    <option key={name}>{name}</option>
                  ))}
                </select>
                <div className="length-edit">
                  <button
                    aria-label="Shorten section by eight bars"
                    disabled={active.bars <= 8}
                    onClick={() =>
                      updateSection(active.id, { bars: active.bars - 8 })
                    }
                  >
                    <Minus size={14} />
                  </button>
                  <span>
                    {active.bars} <small>bars</small>
                  </span>
                  <button
                    aria-label="Lengthen section by eight bars"
                    disabled={active.bars >= 256}
                    onClick={() =>
                      updateSection(active.id, { bars: active.bars + 8 })
                    }
                  >
                    <Plus size={14} />
                  </button>
                </div>
                <div className="section-actions">
                  <button
                    aria-label="Move section left"
                    disabled={project.sections[0].id === active.id}
                    onClick={() => {
                      const i = project.sections.indexOf(active);
                      reorder(active.id, project.sections[i - 1].id);
                    }}
                  >
                    <ChevronLeft size={14} /> Move
                  </button>
                  <button
                    aria-label="Move section right"
                    disabled={project.sections.at(-1)?.id === active.id}
                    onClick={() => {
                      const i = project.sections.indexOf(active);
                      reorder(active.id, project.sections[i + 1].id);
                    }}
                  >
                    Move <ChevronRight size={14} />
                  </button>
                  <button
                    aria-label="Delete section"
                    onClick={() => {
                      setProject((p) => ({
                        ...p,
                        sections: p.sections.filter((s) => s.id !== active.id),
                      }));
                      setSelected("");
                    }}
                  >
                    <X size={14} />
                  </button>
                </div>
              </div>
              {pending
                .filter(
                  (item) =>
                    item.section === active.id &&
                    project.loops.some((l) => l.id === item.loop),
                )
                .map((item) => (
                  <div className="suggestion-card" key={item.loop}>
                    <p>Suggested loop variation · {item.variation.kind}</p>
                    <button
                      disabled={!!busy}
                      onClick={() => void renderPending(item, false)}
                    >
                      Audition
                    </button>
                    <details>
                      <summary>Modify</summary>
                      <label>
                        Variation{" "}
                        <select
                          value={item.variation.kind}
                          onChange={(e) =>
                            setPending((p) =>
                              p.map((x) =>
                                x === item
                                  ? {
                                      ...x,
                                      variation: {
                                        ...x.variation,
                                        kind: e.target
                                          .value as Variation["kind"],
                                      },
                                    }
                                  : x,
                              ),
                            )
                          }
                        >
                          {[
                            "Full",
                            "Low-pass",
                            "High-pass",
                            "Filter sweep",
                            "Quieter",
                            "Fade",
                          ].map((k) => (
                            <option key={k}>{k}</option>
                          ))}
                        </select>
                      </label>
                      {(["cutoff", "gain"] as const).map((field) => (
                        <label key={field}>
                          {field}
                          <input
                            type="number"
                            min={field === "gain" ? 0 : 30}
                            max={field === "gain" ? 1 : 18000}
                            step={field === "gain" ? 0.05 : 10}
                            value={item.variation[field]}
                            onChange={(e) =>
                              setPending((p) =>
                                p.map((x) =>
                                  x === item
                                    ? {
                                        ...x,
                                        variation: {
                                          ...x.variation,
                                          [field]: Number(e.target.value),
                                        },
                                      }
                                    : x,
                                ),
                              )
                            }
                          />
                        </label>
                      ))}
                    </details>
                    <button
                      disabled={!!busy}
                      onClick={() => void renderPending(item, true)}
                    >
                      Accept
                    </button>
                    <button
                      onClick={() => {
                        stopAudio();
                        setPending((p) => p.filter((x) => x !== item));
                      }}
                    >
                      Skip
                    </button>
                  </div>
                ))}
              <div className="tips">
                <span className="eyebrow">A FEW THINGS TO TRY</span>
                {(
                  tips[active.name] || [
                    "Try contrast: remove a layer, then bring it back.",
                  ]
                ).map((tip, i) => (
                  <p key={tip}>
                    <span>{String(i + 1).padStart(2, "0")}</span>
                    {tip}
                  </p>
                ))}
              </div>
              <div className="suggestion-card">
                <div>
                  <Sparkles size={16} />
                  <span>Fresh perspective</span>
                </div>
                {suggestions.length ? (
                  <>
                    <p>{suggestions[0].text}</p>
                    <details
                      className="modify-suggestion"
                      key={`${active.id}-${suggestions[0].kind}`}
                    >
                      <summary>Modify suggestion</summary>
                      {suggestions[0].kind === "tip" ? (
                        <textarea
                          aria-label="Suggestion note"
                          value={suggestions[0].text}
                          onChange={(e) =>
                            setSuggestions((items) => [
                              { ...items[0], text: e.target.value },
                              ...items.slice(1),
                            ])
                          }
                        />
                      ) : (
                        <>
                          {suggestions[0].kind === "next" && (
                            <label>
                              Section name
                              <input
                                aria-label="Suggested section name"
                                value={suggestions[0].name}
                                maxLength={80}
                                onChange={(e) =>
                                  setSuggestions((items) => [
                                    { ...items[0], name: e.target.value },
                                    ...items.slice(1),
                                  ])
                                }
                              />
                            </label>
                          )}
                          <label>
                            Length in bars
                            <input
                              aria-label="Suggested length in bars"
                              type="number"
                              min={8}
                              max={256}
                              step={8}
                              value={suggestions[0].bars}
                              onChange={(e) =>
                                setSuggestions((items) => [
                                  { ...items[0], bars: Number(e.target.value) },
                                  ...items.slice(1),
                                ])
                              }
                            />
                          </label>
                        </>
                      )}
                    </details>
                    <div className="suggestion-buttons">
                      <button
                        className="primary"
                        disabled={
                          suggestions[0].kind !== "tip" &&
                          (!suggestions[0].bars ||
                            suggestions[0].bars < 8 ||
                            suggestions[0].bars > 256 ||
                            suggestions[0].bars % 8 !== 0 ||
                            (suggestions[0].kind === "next" &&
                              !suggestions[0].name?.trim()))
                        }
                        onClick={() => {
                          const suggestion = suggestions[0];
                          if (suggestion.kind === "tip") {
                            setAccepted((a) => ({
                              ...a,
                              [active.id]: [
                                ...(a[active.id] || []),
                                suggestion.text,
                              ],
                            }));
                            setMessage(
                              "Tip added to your section notes. Make the change in your DAW when ready.",
                            );
                          } else
                            setProject((p) =>
                              applySuggestion(p, active.id, suggestion),
                            );
                          setSuggestions((s) => s.slice(1));
                        }}
                      >
                        <Check size={14} /> Accept
                      </button>
                      <button onClick={() => setSuggestions((s) => s.slice(1))}>
                        <SkipForward size={14} /> Skip
                      </button>
                    </div>
                  </>
                ) : (
                  <>
                    <p>
                      A different angle on this section.
                      <br />
                      Take what fits. Leave the rest.
                    </p>
                    <button
                      disabled={disabled}
                      onClick={() =>
                        void run("Finding suggestions…", async () => {
                          const version = suggestionVersion.current;
                          const result = await api<Suggestion[]>(
                            `/suggestions/${active.id}`,
                            project,
                          );
                          if (version === suggestionVersion.current)
                            setSuggestions(result);
                        })
                      }
                    >
                      Suggest a change <ArrowRight size={14} />
                    </button>
                  </>
                )}
              </div>
              {accepted[active.id]?.length > 0 && (
                <div className="accepted">
                  <span className="eyebrow">ACCEPTED NOTES</span>
                  {accepted[active.id].map((tip, i) => (
                    <p key={i}>
                      <Check size={12} /> {tip}
                    </p>
                  ))}
                </div>
              )}
            </>
          ) : (
            <div className="no-selection">
              <span>↖</span>
              <p>
                Select a section to explore its shape, tips and possibilities.
              </p>
            </div>
          )}
          <div className="inspector-bottom">
            <span>YOU’RE THE PRODUCER.</span>
            <p>
              We suggest.
              <br />
              You decide.
            </p>
          </div>
        </aside>
      </main>
      <footer>
        <span>
          <span className="green-dot" /> MADE FOR GETTING UNSTUCK
        </span>
        <span>
          Free & open source <span className="footer-separator">/</span> Your
          sound stays yours.
        </span>
      </footer>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(<App />);

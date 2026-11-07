"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { frameUrl, getProject, packageUrl, previewUrl } from "@/lib/api";
import type { ProjectDetail } from "@/lib/types";

const PHASES = ["researching", "understanding", "exploring", "experimenting", "verifying", "packaging", "completed"];

const CHECK_LABELS: Record<string, string> = {
  file_reopened: "File reopened",
  object_exists: "Object exists",
  object_type_mesh: "Mesh type",
  material_assigned: "Material assigned",
};

export default function ProjectPage() {
  const params = useParams<{ id: string }>();
  const [project, setProject] = useState<ProjectDetail | null>(null);
  const [error, setError] = useState("");
  const [frameIndex, setFrameIndex] = useState(0);

  useEffect(() => {
    let timer = 0;
    const load = () => {
      getProject(params.id)
        .then((next) => {
          setProject(next);
          setFrameIndex(Math.max(0, (next.frames?.length || 1) - 1));
          setError("");
          if (next.status !== "completed" && next.status !== "failed") {
            timer = window.setTimeout(load, 2000);
          }
        })
        .catch((err: Error) => setError(err.message));
    };
    load();
    return () => window.clearTimeout(timer);
  }, [params.id]);

  if (!project) {
    return (
      <main className="grid min-h-screen place-items-center">
        <WireCube label={error || "Reading the software"} />
      </main>
    );
  }

  const verified = project.capabilities.filter((item) => item.verification_status === "verified");
  const observed = project.capabilities.filter((item) => item.verification_status === "experimented");
  const acquired = project.status === "completed" && verified.length > 0;
  const clicked = project.frames?.some((item) => item.action === "click");
  const matchedDocs =
    project.status === "completed" && !!project.frames?.length && !clicked && verified.length === 0;
  const fromText =
    project.status === "completed" && !project.frames?.length && verified.length === 0 && project.capabilities.length > 0;
  const headline = acquired
    ? "Capability acquired"
    : matchedDocs
      ? "Matched the documents"
      : fromText
        ? "Learned from the documents"
        : project.frames?.length
          ? "Watching and clicking"
          : project.status === "failed"
            ? "Not verified"
            : phaseLabel(project.status);
  const experiment = project.experiments[0];
  const frame = project.frames?.[frameIndex];

  return (
    <main className="mx-auto max-w-6xl px-6 py-8">
      <div className="flex items-center justify-between">
        <Link href="/" className="font-mono text-xs uppercase tracking-[0.22em] text-signal">
          AppDNA
        </Link>
        <span className="font-mono text-xs text-ink/50">
          {project.software_name} {project.software_version}
        </span>
      </div>

      <section className="mt-6 grid items-stretch gap-5 lg:grid-cols-[1.25fr_0.75fr]">
        <div className="scan relative min-h-[420px] overflow-hidden rounded-[28px] border border-white/10 bg-black">
          {frame ? (
            <div className="grid h-full content-center px-4 py-6">
              <div className="relative mx-auto" style={{ aspectRatio: `${frame.image_width} / ${frame.image_height}`, maxHeight: 480 }}>
                <img
                  src={frameUrl(project.id, frame.image)}
                  alt={`What the agent saw at step ${frame.step}`}
                  className="h-full w-full rounded-xl object-contain"
                />
                {frame.action === "click" || frame.action === "double_click" ? (
                  <span
                    className="absolute h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-signal bg-signal/40"
                    style={{ left: `${(frame.x / frame.image_width) * 100}%`, top: `${(frame.y / frame.image_height) * 100}%` }}
                  />
                ) : null}
              </div>
              <p className="mt-3 text-center font-mono text-xs text-ink/70">
                {frame.action}
                {frame.executed ? "" : " blocked"} — {frame.thought}
              </p>
              <div className="mt-3 flex justify-center gap-2">
                {project.frames.map((item, index) => (
                  <button
                    key={`${item.step}-${item.action}-${index}`}
                    type="button"
                    onClick={() => setFrameIndex(index)}
                    className={`h-12 w-16 overflow-hidden rounded-lg border ${index === frameIndex ? "border-signal" : "border-white/15"}`}
                  >
                    <img src={frameUrl(project.id, item.image)} alt="" className="h-full w-full object-cover" />
                  </button>
                ))}
              </div>
            </div>
          ) : project.preview_ready ? (
            <img
              src={previewUrl(project.id, project.updated_at)}
              alt="Rendered result of the verified scene"
              className="h-full w-full object-cover"
            />
          ) : (
            <div className="grid h-full min-h-[420px] place-items-center">
              <WireCube label={fromText ? "No click needed" : project.status === "exploring" ? "Looking at the app" : "Opening the software"} />
            </div>
          )}
          <div className="absolute left-4 top-4 rounded-full border border-white/15 bg-black/50 px-3 py-1 font-mono text-[11px] uppercase tracking-wider">
            {frame ? `step ${frame.step}` : experiment?.object_name || project.software_name}
          </div>
        </div>

        <div className="flex flex-col justify-between rounded-[28px] border border-line bg-white/5 p-6">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-signal">
              {acquired ? "Independent test passed" : matchedDocs ? "Live app matches the documents" : fromText ? "Written sources were enough" : observed.length ? "Observed from the screen" : "Learning run"}
            </p>
            <h1 className="mt-3 font-serif text-5xl leading-none">{headline}</h1>
            <p className="mt-4 text-sm leading-relaxed text-ink/70">{project.learning_objective}</p>
          </div>
          <div className="mt-6 grid grid-cols-2 gap-2">
            {Object.entries(CHECK_LABELS).map(([key, label]) => {
              const passed = project.checks?.[key];
              return (
                <div key={key} className="rounded-2xl border border-line px-3 py-3">
                  <p className={`font-mono text-[11px] uppercase ${passed ? "text-signal" : "text-ink/40"}`}>
                    {passed ? "Pass" : "Wait"}
                  </p>
                  <p className="mt-1 text-sm">{label}</p>
                </div>
              );
            })}
          </div>
          <div className="mt-6 flex items-center justify-between gap-3">
            <p className="font-mono text-xs text-ink/50">
              {verified.length} verified · {observed.length} observed
            </p>
            {project.package_ready ? (
              <a href={packageUrl(project.id)} className="rounded-full bg-signal px-4 py-2 text-sm font-medium text-black">
                Download package
              </a>
            ) : (
              <span className="font-mono text-xs uppercase text-ink/40">Packaging</span>
            )}
          </div>
        </div>
      </section>

      {project.error_message ? <p className="mt-4 text-sm text-clay">{project.error_message}</p> : null}
      {error ? <p className="mt-4 text-sm text-clay">{error}</p> : null}

      <ol className="mt-6 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
        {PHASES.map((phase, index) => {
          const active = phase === project.status;
          const done = project.status === "completed" || index < PHASES.indexOf(project.status);
          return (
            <li
              key={phase}
              className={`rounded-2xl border px-3 py-3 font-mono text-[10px] uppercase tracking-wider ${
                active
                  ? "border-signal bg-signal text-black"
                  : done
                    ? "border-signal/40 text-signal"
                    : "border-line text-ink/35"
              }`}
            >
              0{index + 1} {phase}
            </li>
          );
        })}
      </ol>

      <section className="mt-8">
        <h2 className="font-serif text-3xl">Capability graph</h2>
        <div className="mt-4 flex gap-3 overflow-x-auto pb-2">
          {project.capabilities.length === 0 ? <p className="text-sm text-ink/45">Capabilities appear after the corpus is read.</p> : null}
          {project.capabilities.map((capability, index) => (
            <article
              key={capability.id}
              className={`min-w-64 rounded-3xl border p-4 ${
                capability.verification_status === "verified" ? "border-signal/60 bg-signal/10" : "border-line bg-white/5"
              }`}
            >
              <p className="font-mono text-[11px] uppercase text-ink/45">0{index + 1}</p>
              <h3 className="mt-2 text-lg">{capability.name}</h3>
              <p className="mt-2 text-sm text-ink/65">{capability.description}</p>
              <div className="mt-4 h-1 overflow-hidden rounded-full bg-white/10">
                <div className="h-full bg-signal" style={{ width: `${Math.round(capability.confidence * 100)}%` }} />
              </div>
              <p className="mt-2 font-mono text-[11px] uppercase text-signal">{capability.verification_status}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-8 grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-3xl border border-line bg-black/40 p-4">
          <h2 className="font-mono text-xs uppercase tracking-[0.18em] text-ink/50">Run log</h2>
          <ul className="mt-3 space-y-2 font-mono text-xs leading-relaxed">
            {project.activities.map((item, index) => (
              <li key={`${item.created_at}-${index}`}>
                <span className="text-signal">{item.phase}</span>
                <span className="text-ink/70"> — {item.message}</span>
              </li>
            ))}
          </ul>
        </div>
        <div>
          <h2 className="font-serif text-3xl">Sources</h2>
          <div className="mt-3 space-y-2">
            {project.sources.length === 0 ? (
              <p className="text-sm text-ink/60">No public documentation was found for this application.</p>
            ) : null}
            {project.sources.slice(0, 6).map((source) => (
              <a
                key={source.id}
                href={source.url}
                target="_blank"
                className="block rounded-2xl border border-line px-4 py-3 hover:border-signal"
              >
                <p className="font-mono text-[11px] uppercase text-signal">{source.source_type}</p>
                <p className="mt-1 text-sm">{source.title}</p>
              </a>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}

function phaseLabel(status: string): string {
  return status.split("_").join(" ");
}

function WireCube({ label }: { label: string }) {
  return (
    <div className="grid justify-items-center gap-5">
      <div className="stage">
        <div className="cube">
          <span />
          <span />
          <span />
          <span />
          <span />
          <span />
        </div>
      </div>
      <p className="font-mono text-xs uppercase tracking-[0.18em] text-signal">{label}</p>
    </div>
  );
}

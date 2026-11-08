"use client";

import { WorkspaceHeader } from "@/components/WorkspaceHeader";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import { frameUrl, getProject, packageUrl, previewUrl, reportUrl, resumeProject, sourceUrl } from "@/lib/api";
import { RecordingEvidence } from "@/components/RecordingEvidence";
import { KnowledgeGraph } from "@/components/KnowledgeGraph";
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
  const [resuming, setResuming] = useState(false);
  const [continuationError, setContinuationError] = useState("");
  const [reload, setReload] = useState(0);

  async function continueLearning() {
    if (!project || resuming) return;
    setResuming(true);
    setContinuationError("");
    try {
      const next = await resumeProject(project.id);
      setProject((current) => current ? { ...current, ...next, can_resume: false } : current);
      setReload((value) => value + 1);
    } catch (err) {
      setContinuationError(err instanceof Error ? err.message : "Could not continue learning. Please try again.");
    } finally {
      setResuming(false);
    }
  }

  useEffect(() => {
    let timer = 0;
    let cancelled = false;
    const load = () => {
      getProject(params.id)
        .then((next) => {
          if (cancelled) return;
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
    return () => { cancelled = true; window.clearTimeout(timer); };
  }, [params.id, reload]);

  if (!project) {
    return (
      <main className="grid min-h-screen place-items-center">
        <WireCube label={error || "Reading the software"} />
      </main>
    );
  }

  const verified = project.capabilities.filter((item) => item.verification_status === "verified");
  const observed = project.capabilities.filter((item) => item.verification_status === "experimented");
  const recorded = project.capabilities.filter((item) => item.verification_status === "observed");
  const acquired = project.status === "completed" && verified.length > 0;
  const coverageIncomplete = project.status === "completed" && project.outcome.evaluation.verdict === "Incomplete";
  const clicked = project.frames?.some((item) => item.action === "click");
  const matchedDocs =
    project.status === "completed" && !!project.frames?.length && !clicked && verified.length === 0;
  const fromText =
    project.status === "completed" && !project.frames?.length && verified.length === 0 && project.capabilities.length > 0;
  const headline = project.status === "failed"
    ? "Stopped"
    : coverageIncomplete
    ? "Coverage incomplete"
    : acquired
    ? "Capability acquired"
    : matchedDocs
      ? "Matched the documents"
      : fromText
        ? recorded.length ? "Learned from the recording" : "Learned from the documents"
        : project.frames?.length
          ? "Watching and clicking"
          : project.status === "failed"
            ? "Stopped"
            : phaseLabel(project.status);
  const experiment = project.experiments[0];
  const frame = project.frames?.[frameIndex];

  return (
    <main className="review-workspace mx-auto max-w-7xl px-4 pb-10 sm:px-8">
      <WorkspaceHeader context={`${project.software_name} ${project.software_version || ""} / Assessment`} />

      <section className="mt-6 grid grid-cols-1 items-stretch gap-5 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.75fr)]">
        <div className="relative min-w-0 overflow-hidden rounded-2xl border border-white/10 bg-black">
          {frame ? (
            <div className="px-4 pb-4 pt-12">
              <div className="relative w-full">
                <img
                  src={frameUrl(project.id, frame.image)}
                  alt={`What the agent saw at step ${frame.step}`}
                  className="block h-auto max-w-full w-full rounded-xl"
                />
                {frame.action === "click" || frame.action === "double_click" ? (
                  <span
                    className="absolute h-5 w-5 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-signal bg-signal/40"
                    style={{ left: `${(frame.x / frame.image_width) * 100}%`, top: `${(frame.y / frame.image_height) * 100}%` }}
                  />
                ) : null}
              </div>
              {project.status === "failed" ? <p className="mt-3 text-xs leading-5 text-clay">Retained screen capture, not a live view. The latest attempt is stopped; saved imagery does not demonstrate a completed run.</p> : null}
              <div className="mt-3 flex flex-wrap items-start justify-between gap-3">
                <details className="min-w-0 flex-1 text-xs leading-5 text-ink/75"><summary className="cursor-pointer">Saved action: {frame.action}{frame.executed ? "" : " · blocked"}</summary><p className="mt-2">{frame.thought}</p></details>
                <a href={frameUrl(project.id, frame.image)} target="_blank" rel="noopener noreferrer" className="text-xs text-signal underline underline-offset-4">View full-size evidence</a>
              </div>
              <div className="mt-3 flex gap-2 overflow-x-auto pb-1">
                {project.frames.map((item, index) => (
                  <button
                    key={`${item.step}-${item.action}-${index}`}
                    type="button"
                    onClick={() => setFrameIndex(index)}
                    className={`h-16 w-28 shrink-0 overflow-hidden rounded-lg border bg-black ${index === frameIndex ? "border-signal" : "border-white/15"}`}
                  >
                    <img src={frameUrl(project.id, item.image)} alt="" className="h-full w-full object-contain" />
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
              <WireCube label={stageLabel(project)} />
            </div>
          )}
          <div className="absolute left-4 top-4 rounded-full border border-white/15 bg-black/50 px-3 py-1 font-mono text-[11px] uppercase tracking-wider">
            {frame ? `Saved step ${frame.step}` : experiment?.object_name || project.software_name}
          </div>
        </div>

        <div className="flex flex-col justify-between rounded-2xl border border-line bg-white/5 p-6">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-signal">
              {project.status === "failed" ? "Latest attempt stopped · evidence retained" : coverageIncomplete ? "Partial learning result" : acquired ? "Independent test passed" : matchedDocs ? "Live app matches the documents" : fromText ? recorded.length ? "Video source checked" : "Written sources were enough" : observed.length ? "Observed from the screen" : "Learning run"}
            </p>
            <h1 className="mt-3 font-sans text-4xl font-medium leading-tight tracking-tight">{headline}</h1>
            {project.error_message ? <p role="alert" className="mt-3 text-sm leading-6 text-clay">{project.error_message}</p> : null}
            <p className="mt-4 text-sm leading-relaxed text-ink/70">{project.learning_objective}</p>
          </div>
          {(project.can_resume || resuming || project.status === "resuming" || project.status === "exploring") && (
            <div className="mt-5 border-t border-line pt-4">
              <button
                type="button"
                onClick={continueLearning}
                disabled={resuming || !project.can_resume}
                aria-describedby="continuation-help"
                className="rounded-full border border-signal px-4 py-2 text-sm font-medium text-signal transition hover:bg-signal/10 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-signal disabled:cursor-wait disabled:opacity-50"
              >
                {resuming || !project.can_resume ? "Learning in progress…" : "Continue learning"}
              </button>
              <p id="continuation-help" className="mt-2 text-xs leading-relaxed text-ink/55">
                Keep sources, skills, and evidence. Explore up to 12 more controls per round; you can continue again if needed.
              </p>
              {continuationError && <p role="alert" className="mt-2 text-sm text-clay">{continuationError}</p>}
            </div>
          )}
          {project.software_name.toLowerCase().includes("blender") && <div className="mt-5"><p className="mb-3 text-xs leading-5 text-ink/70">{project.status === "failed" ? "Retained checks apply to saved Blender artifacts, not the latest GUI attempt." : "Saved Blender artifact checks. These do not verify GUI coverage."}</p><div className="grid grid-cols-2 gap-2">
            {Object.entries(CHECK_LABELS).map(([key, label]) => {
              const passed = project.checks?.[key];
              return (
                <div key={key} className="rounded-2xl border border-line px-3 py-3">
                  <p className={`font-mono text-[11px] uppercase ${passed ? "text-signal" : "text-ink/40"}`}>
                    {passed === true ? "Pass" : passed === false ? "Fail" : "Not checked"}
                  </p>
                  <p className="mt-1 text-sm">{label}</p>
                </div>
              );
            })}
          </div></div>}
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <p className="font-mono text-xs text-ink/50">
              {verified.length} verified capabilities · {observed.length} live observations · {recorded.length} video observations
            </p>
            {project.package_ready ? (
              <a href={packageUrl(project.id)} className="shrink-0 whitespace-nowrap rounded-lg bg-signal px-4 py-2 text-sm font-medium text-black">
                {project.status === "failed" || project.outcome.evaluation.verdict === "Incomplete" ? "Download partial package" : "Download package"}
              </a>
            ) : (
              <span className="font-mono text-xs uppercase text-ink/40">Packaging</span>
            )}
          </div>
        </div>
      </section>

      <div className="mt-4 flex justify-end"><a href={reportUrl(project.id)} target="_blank" rel="noreferrer" className="rounded-full border border-signal/50 px-4 py-2 text-sm text-signal">Open assessment report</a></div>
      <RecordingEvidence project={project} />

      {error ? <p className="mt-4 text-sm text-clay">{error}</p> : null}

      <p className="mt-6 text-xs leading-5 text-ink/70">{project.status === "failed" ? "Latest attempt stopped. Saved evidence is retained; the stages below are the workflow outline, not acceptance results." : "Workflow stages describe processing progress, not product acceptance."}</p>
      <ol className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
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

      {project.outcome ? (
        <section className="mt-8">
          <KnowledgeGraph outcome={project.outcome} sources={project.sources} />
        </section>
      ) : null}

      <section className="mt-8">
        <h2 className="font-sans text-2xl font-medium">Functional evidence</h2>
        <details className="mt-4 rounded-2xl border border-line p-5"><summary className="cursor-pointer text-sm">Explore all {project.capabilities.length} saved capabilities</summary><div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {project.capabilities.length === 0 ? <p className="text-sm text-ink/45">Capabilities appear after the corpus is read.</p> : null}
          {project.capabilities.map((capability, index) => (
            <article
              key={capability.id}
              className={`min-w-0 rounded-xl border p-4 ${
                capability.verification_status === "verified" ? "border-signal/60 bg-signal/10" : "border-line bg-white/5"
              }`}
            >
              <p className="font-mono text-[11px] uppercase text-ink/45">0{index + 1}</p>
              <h3 className="mt-2 text-lg">{capability.name}</h3>
              <p className="mt-2 text-sm text-ink/65">{capability.description}</p>
              <p className="mt-2 font-mono text-[11px] uppercase text-signal">{capability.verification_status}</p>
            </article>
          ))}
        </div></details>
      </section>

      <section className="mt-8 space-y-6">
        <details className="rounded-2xl border border-line bg-white/[0.02] p-5">
          <summary className="cursor-pointer text-sm font-medium">Full run log · {project.activities.length} retained events</summary>
          <ul className="mt-3 space-y-2 font-mono text-xs leading-relaxed">
            {project.activities.map((item, index) => (
              <li key={`${item.created_at}-${index}`}>
                <span className="text-signal">{item.phase}</span>
                <span className="text-ink/70"> — {item.message}</span>
              </li>
            ))}
          </ul>
        </details>
        <div>
          <h2 className="font-sans text-2xl font-medium">Source register</h2><p className="mt-2 text-xs text-ink/70">{project.sources.filter(source => source.relevant === true).length} matched sources / {project.sources.length} collected. Unknown and different-product sources stay excluded.</p>
          <div className="mt-3 grid gap-3 md:grid-cols-2">
            {project.sources.length === 0 ? (
              <p className="text-sm text-ink/60">No public documentation was found for this application.</p>
            ) : null}
            {project.sources.map((source) => (
              <a
                key={source.id}
                href={sourceUrl(source.url)}
                target="_blank"
                className="block rounded-2xl border border-line px-4 py-3 hover:border-signal"
              >
                <p className="font-mono text-[11px] uppercase text-signal">
                  {source.relevant === false ? "Different product · excluded" : source.relevant ? "Matched product" : "Identity not confirmed · excluded"} · {source.source_type}
                </p>
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

function stageLabel(project: ProjectDetail): string {
  if (project.status === "completed") return "Evidence retained";
  if (project.status === "failed") return "Stopped";
  if (project.status === "researching" || project.status === "understanding") return "Reading the documents";
  if (project.status === "exploring") return "Opening the software";
  if (project.status === "experimenting" || project.status === "verifying") return "Checking the result";
  if (project.status === "packaging") return "Packaging the skills";
  return "Opening the software";
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

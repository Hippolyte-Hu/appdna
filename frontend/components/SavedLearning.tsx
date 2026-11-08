"use client";

import { useRef } from "react";
import { clock, learningAsset, LEARNING_API, VideoKnowledge } from "@/lib/learning";

export function SavedLearning({ id, knowledge }: { id: string; knowledge: VideoKnowledge }) {
  const video = useRef<HTMLVideoElement>(null);
  function seek(seconds: number) { if (video.current) { video.current.currentTime = seconds; video.current.pause(); } }
  return <section className="workspace-panel" data-testid="knowledge-package" data-source-id={id}>
    <div className="panel-heading"><div><p className="eyebrow">Saved learning · Blender</p><h2 className="mt-2 text-xl font-medium">{knowledge.title}</h2></div><span className="run-status" data-status="completed">Source checked</span></div>
    <div className="p-5 sm:p-6">
      <p className="mb-5 text-sm leading-7 text-ink/70">{knowledge.objective}</p>
      <video ref={video} className="showcase-video" controls preload="metadata" src={learningAsset(id, knowledge.source_file)} onLoadedMetadata={() => seek(knowledge.steps[0]?.start ?? 0)} aria-label="Original teaching video" />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-ink/65"><span>{knowledge.steps.length} saved steps · {knowledge.evidence.length} timestamped frames</span>{knowledge.source_url?.startsWith("https://www.youtube.com/") ? <a className="showcase-text-link" href={knowledge.source_url} target="_blank" rel="noreferrer">Original video ↗</a> : null}</div>
      <h3 className="mb-2 mt-7 text-base font-medium">What the Agent learned</h3>
      <p className="mb-4 text-xs leading-6 text-ink/65">Review this workflow before starting. Timestamps jump to the teaching video; evidence expands below each step.</p>
      <ol className="showcase-steps">
        {knowledge.steps.map((step, index) => <li key={step.id} data-testid="learned-step">
          <div className="showcase-step-heading"><span className="panel-index">{String(index+1).padStart(2,"0")}</span><p>{step.instruction}</p><button className="showcase-time" aria-label={`Play step ${index+1}`} onClick={() => seek(step.start)}>{clock(step.start)}–{clock(step.end)}</button></div>
          <details className="mt-3"><summary className="showcase-summary">Expected result & source evidence</summary>
            <p className="my-3 text-sm leading-7 text-ink/70">{step.expected}</p>
            {step.uncertainty ? <p className="mb-3 text-sm text-clay">Uncertainty: {step.uncertainty}</p> : null}
            <div className="showcase-evidence">{step.evidence_ids.map(evidenceId => {
              const evidence = knowledge.evidence.find(item => item.id === evidenceId);
              return evidence ? <figure key={evidence.id}><a href={learningAsset(id,evidence.image)} target="_blank" rel="noreferrer" aria-label={`Open ${evidence.id} at ${clock(evidence.timestamp)}`}><img src={learningAsset(id,evidence.image)} alt={`Tutorial evidence at ${clock(evidence.timestamp)}`} loading="lazy" /></a><figcaption className="mt-2 text-xs leading-6 text-ink/65">{evidence.id} · {clock(evidence.timestamp)}<p>{evidence.observations.join(" · ")}</p></figcaption></figure> : null;
            })}</div>
          </details>
        </li>)}
      </ol>
      <div className="showcase-context"><h3 className="text-sm font-medium">Tutorial prerequisites</h3><p className="mt-2 text-xs leading-6 text-ink/65">The Agent opens a fresh Blender scene; these are the source tutorial’s starting assumptions, not instructions to edit your current scene.</p><ul>{knowledge.prerequisites.map(text => <li key={text}>{text}</li>)}</ul><h3 className="mt-4 text-sm font-medium">Known limits</h3><ul>{knowledge.limitations.map(text => <li key={text}>{text}</li>)}</ul></div>
      <details className="border-t border-line pt-5"><summary className="showcase-summary">How this learning is saved</summary><div className="mt-4 space-y-4 text-sm leading-7 text-ink/70">
        <p>A local knowledge package, not model training or hidden chat memory. Reuse loads this saved package without downloading or learning the video again.</p>
        <dl className="showcase-files"><dt>knowledge.json</dt><dd>Instructions, expected results, timestamps, frame references, source checks and limitations.</dd><dt>plan.json</dt><dd>The reusable GUI workflow. The executor grounds actions against the current app, not tutorial coordinates.</dd><dt>agent_frames/</dt><dd>The saved frames and crops used to check the source.</dd><dt>run/</dt><dd>Each new execution gets its own screenshots, action log and artifact checks. These are not copied from previous runs.</dd></dl>
        <p className="break-all font-mono text-xs">tasks/video-agent/evidence/jobs/{id}/knowledge.json</p>
        <p className="text-xs">Not yet published to Motion2Action’s main skill graph. Source checking does not establish successful app execution.</p>
        <a className="showcase-secondary" href={`${LEARNING_API}/video-sources/${id}`} download>Download knowledge JSON</a>
      </div></details>
    </div>
  </section>;
}

"use client";

import { ACTIVE_RUN, Execution, independentlyVerified, learningAsset, runLabel } from "@/lib/learning";

export function AgentExecution({ run, error, stopping, onStop, onRefresh }: {
  run: Execution | null; error: string; stopping: boolean; onStop: () => void; onRefresh: () => void;
}) {
  const verified = run && independentlyVerified(run);
  const events = run?.run?.events ?? [];
  const lastCapture = [...events].reverse().find(event => event.after)?.after;
  return <section className="workspace-panel" data-testid="execution-receipt" aria-label="Agent execution">
    <div className="panel-heading"><div><p className="eyebrow">Separate execution receipt</p><h2 className="mt-2 text-lg font-medium">{run ? runLabel(run.status) : "Reading run status…"}</h2></div>
      {run && ACTIVE_RUN.has(run.status) ? <button className="showcase-secondary" onClick={onStop} disabled={stopping}>{stopping ? "Stop requested" : "Stop Agent"}</button> : null}</div>
    <div className="space-y-3 p-5 text-sm sm:p-6" aria-live="polite">
      <p className="text-ink/70">{verified ? "The saved artifact passed independent, source-bound checks." : "No independently verified artifact for this run."}</p>
      {run?.id ? <p className="break-all font-mono text-xs text-ink/60">Run {run.id}</p> : null}
      {run?.action_model ? <p className="text-xs text-ink/60">Action model: {run.action_model}</p> : null}
      {run?.error ? <p role="alert" className="text-clay">{run.error}</p> : null}
      {error ? <div role="alert"><p className="text-clay">{error}</p><button onClick={onRefresh} className="showcase-secondary mt-3">Refresh run status</button></div> : null}
      {stopping ? <p className="text-ink/70">The Agent will stop at the next safe boundary. An in-flight request may finish first.</p> : null}
      {lastCapture && run ? <figure><a href={learningAsset(run.id, `run/${lastCapture}`)} target="_blank" rel="noreferrer"><img className="w-full rounded border border-line" src={learningAsset(run.id, `run/${lastCapture}`)} alt="Latest app screenshot saved by this execution" /></a><figcaption className="mt-2 text-xs text-ink/60">Latest captured app state · not artifact verification</figcaption></figure> : null}
      {events.length ? <details><summary className="showcase-summary">Recorded activity · {events.length} events</summary><ol className="mt-3 max-h-64 overflow-auto space-y-3">
        {events.map((event, index) => <li key={index} className="border-l border-line pl-3 text-xs leading-6 text-ink/70">{event.step ? `Step ${event.step} · ` : ""}{event.action?.action ?? event.status ?? "Event"}{event.action?.reason || event.reason ? ` — ${event.action?.reason ?? event.reason}` : ""}</li>)}
      </ol></details> : null}
    </div>
  </section>;
}

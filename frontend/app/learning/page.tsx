"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { WorkspaceHeader } from "@/components/WorkspaceHeader";
import { SavedLearning } from "@/components/SavedLearning";
import { AgentExecution } from "@/components/AgentExecution";
import { ACTIVE_RUN, Execution, LearnedSource, learningRequest, SourceCatalog, VideoKnowledge } from "@/lib/learning";

type SourceDetail = { id: string; knowledge: VideoKnowledge };
const message = (err: unknown) => err instanceof Error ? err.message : "Could not read saved learning";
const validId = (id: string | null) => id && /^[a-f0-9]{32}$/.test(id) ? id : "";

export default function LearningShowcase() {
  const [sources, setSources] = useState<LearnedSource[] | null>(null);
  const [more, setMore] = useState(false);
  const [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<SourceDetail | null>(null);
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const [pending, setPending] = useState(false);
  const [runId, setRunId] = useState("");
  const [run, setRun] = useState<Execution | null>(null);
  const [runError, setRunError] = useState("");
  const [startError, setStartError] = useState("");
  const [stopping, setStopping] = useState(false);

  const load = useCallback(async (offset = 0) => {
    setError("");
    try {
      const catalog = await learningRequest<SourceCatalog>(`video-sources?limit=20&offset=${offset}`);
      setSources(previous => offset ? [...(previous ?? []), ...catalog.items] : catalog.items);
      setMore(catalog.has_more);
      if (!offset) {
        const query = new URLSearchParams(window.location.search);
        setSelected(catalog.items.find(item => item.id === query.get("source"))?.id ?? catalog.items[0]?.id ?? "");
        setRunId(validId(query.get("run")));
      }
    } catch (err) { setError(message(err)); }
  }, []);
  useEffect(() => { void load(); }, [load]);

  useEffect(() => {
    if (!selected) { setDetail(null); return; }
    const controller = new AbortController();
    setDetailError("");
    learningRequest<SourceDetail>(`tutorials/${selected}`, { signal: controller.signal })
      .then(setDetail).catch(err => { if (!controller.signal.aborted) setDetailError(message(err)); });
    return () => controller.abort();
  }, [selected, refresh]);

  useEffect(() => {
    if (!runId || !selected) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const controller = new AbortController();
    async function poll() {
      try {
        const receipt = await learningRequest<Execution>(`tutorials/${runId}`, { signal: controller.signal });
        if (receipt.source_job_id !== selected) throw new Error("This execution belongs to another source. Select its original workflow.");
        if (!cancelled) { setRun(receipt); setRunError(""); if (!ACTIVE_RUN.has(receipt.status)) setStopping(false); }
      } catch (err) { if (!cancelled) setRunError(message(err)); }
      if (!cancelled) timer = setTimeout(poll, 3000);
    }
    void poll();
    return () => { cancelled = true; clearTimeout(timer); controller.abort(); };
  }, [runId, selected, refresh]);

  function select(id: string) {
    setSelected(id); setRunId(""); setRun(null); setRunError(""); setStartError(""); setStopping(false);
    window.history.replaceState(null, "", `/learning?source=${id}`);
  }
  async function start() {
    if (pending || !detail || detail.id !== selected) return;
    setPending(true); setStartError(""); setRunError(""); setStopping(false);
    try {
      const execution = await learningRequest<Execution>(`video-sources/${selected}/executions`, { method: "POST" });
      setRun(execution); setRunId(execution.id);
      window.history.replaceState(null, "", `/learning?source=${selected}&run=${execution.id}`);
      await learningRequest(`tutorials/${execution.id}/run`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ reviewed: true, confirm_scratch: true }) });
      setRun(await learningRequest<Execution>(`tutorials/${execution.id}`));
    } catch (err) { setStartError(message(err)); }
    finally { setPending(false); }
  }
  async function stop() {
    setRunError("");
    try { await learningRequest(`tutorials/${runId}/stop`, { method: "POST" }); setStopping(true); }
    catch (err) { setRunError(message(err)); }
  }
  const busy = pending || Boolean(runId && (!run || ACTIVE_RUN.has(run.status) || runError));
  const current = detail?.id === selected ? detail : null;

  return <main className="review-workspace mx-auto max-w-7xl px-4 pb-12 sm:px-8">
    <WorkspaceHeader context="Learning Showcase" />
    <section className="workspace-intro"><div><p className="eyebrow">Watch → learn → reuse</p><h1 className="mt-2 text-3xl font-medium tracking-tight">Learning Showcase</h1><p className="mt-3 max-w-2xl text-sm leading-7 text-ink/70">The video is the lesson. The saved workflow is what the Agent keeps. Review it here, then watch the Agent use it in the real app.</p></div></section>
    {error ? <div role="alert" className="workspace-panel mb-6 p-5"><p className="text-sm text-clay">{error}</p><button className="showcase-secondary mt-3" onClick={() => void load()}>Retry</button></div> : null}
    {sources === null && !error ? <p role="status" className="p-6 text-sm text-ink/70">Loading saved workflows…</p> : null}
    {sources?.length === 0 && !error ? <section className="workspace-panel p-6"><h2 className="text-lg">No checked workflows yet.</h2><p className="mt-3 text-sm leading-7 text-ink/70">A video must complete source learning before it appears here. Failed or unresolved lessons are not presented as learned skills.</p><Link className="showcase-secondary mt-4" href="/">Back to workspace</Link></section> : null}
    {sources?.length && !error ? <div className="showcase-layout">
      <aside className="showcase-sidebar">
        <section className="workspace-panel"><div className="panel-heading"><h2 className="text-sm font-medium">Saved workflows</h2><span className="text-xs text-ink/60">Video</span></div>
          <div className="p-3">{sources.map(source => <button key={source.id} className="showcase-source" aria-pressed={selected === source.id} disabled={busy} onClick={() => select(source.id)}><span className="eyebrow">Blender</span><strong>{source.title}</strong><span className="text-xs text-ink/65">Source checked · reusable knowledge</span></button>)}</div>
          {more ? <button className="showcase-secondary m-3" onClick={() => void load(sources.length)}>Load more workflows</button> : null}
        </section>
        <section className="workspace-panel p-5 sm:p-6">
          <p className="eyebrow">Put the learning to work</p><h2 className="mt-2 text-lg font-medium">Let the Agent show you.</h2>
          <p className="mt-3 text-sm leading-7 text-ink/70">Opens Blender in an isolated scratch scene using real mouse and keyboard input.</p>
          <button className="workspace-primary mt-5 w-full" onClick={start} disabled={busy || !current || current.knowledge.status !== "source_checked"}>{pending ? "Starting Agent…" : "Run with Agent"}<span aria-hidden="true">↗</span></button>
          <p className="mt-3 text-xs leading-6 text-ink/65">Starting approves the displayed workflow and a new scratch scene. Unlock this Mac and leave the desktop free. Do not start another assessment.</p>
          <p className="mt-3 text-xs leading-6 text-ink/65">Blender only · Source checking is not artifact verification.</p>
          {startError ? <p role="alert" className="mt-4 text-sm leading-6 text-clay">{startError}</p> : null}
        </section>
      </aside>
      <div className="min-w-0 space-y-6">
        {runId ? <AgentExecution run={run} error={runError} stopping={stopping} onStop={stop} onRefresh={() => setRefresh(value => value+1)} /> : null}
        {detailError ? <div role="alert" className="workspace-panel p-6"><p className="text-sm text-clay">{detailError}</p><button className="showcase-secondary mt-3" onClick={() => setRefresh(value => value+1)}>Retry</button></div> : null}
        {current && !detailError ? <SavedLearning key={selected} id={selected} knowledge={current.knowledge} /> : !detailError ? <p role="status" className="p-6 text-sm text-ink/70">Reading saved knowledge…</p> : null}
      </div>
    </div> : null}
    <footer className="mt-8 border-t border-line pt-5 text-xs leading-6 text-ink/60">Local knowledge files · Fresh execution receipts · Independent artifact checks kept separate</footer>
  </main>;
}

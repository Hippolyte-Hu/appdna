"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { createProject, listProjects } from "@/lib/api";
import { WorkspaceHeader } from "@/components/WorkspaceHeader";
import type { ProjectSummary } from "@/lib/types";

export default function HomePage() {
  const router = useRouter();
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);
  const [audio, setAudio] = useState<File | null>(null);

  useEffect(() => {
    listProjects().then(setProjects).catch(() => setProjects([]));
  }, []);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const created = await createProject({
        software_name: String(form.get("software_name") || ""),
        software_version: String(form.get("software_version") || ""),
        learning_objective: String(form.get("learning_objective") || ""),
        audio_url: String(form.get("audio_url") || ""),
        audio,
      });
      router.push(`/projects/${created.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create the project");
      setPending(false);
    }
  }

  return (
    <main className="review-workspace mx-auto max-w-7xl px-4 pb-12 sm:px-8">
      <WorkspaceHeader />
      <section className="workspace-intro">
        <div>
          <p className="eyebrow">Software due diligence</p>
          <h1 className="mt-2 text-2xl font-medium tracking-tight sm:text-3xl">Know what an application can really do.</h1>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-ink/70">Bring documentation, recorded demonstrations and hands-on exploration into one traceable assessment. For procurement decisions and internal pre-UAT reviews.</p>
        </div>
      </section>
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.25fr)_minmax(0,0.85fr)]">
        <section className="workspace-panel min-w-0">
          <div className="panel-heading">
            <div><p className="eyebrow">New assessment</p><h2 className="mt-2 text-xl font-medium">Start with the application.</h2></div>
            <span className="text-xs text-ink/65">Scope first</span>
          </div>
          <form onSubmit={onSubmit} className="space-y-4 p-5 sm:p-6">
            <Field label="Application name or website URL" name="software_name" defaultValue="Blender" placeholder="Blender, VoiceCue, or https://www.canva.com/settings/your-account" />
            <p className="!mt-2 text-xs leading-5 text-ink/60">Web pages open in an isolated browser, not your personal session. Account pages may require authorized sign-in; AppDNA stops at authentication gates.</p>
            <div className="grid gap-3">
              <Field label="Version (optional)" name="software_version" defaultValue="" placeholder="If known" />
              <p className="text-xs leading-5 text-ink/65">App names target an installed Mac application. URLs target an isolated browser page. Only authorized test environments should be assessed.</p>
            </div>
            <label className="block text-sm">
              <span className="font-medium">Assessment objective</span>
              <textarea name="learning_objective" required minLength={8} defaultValue="Evaluate the main workflows and UI for a procurement or pre-UAT review. Record strengths, friction and untested areas." className="workspace-input mt-2 min-h-32 w-full resize-y" />
            </label>
            <details className="border-t border-line pt-4">
              <summary className="cursor-pointer text-sm font-medium text-ink/90">Add audio or video evidence <span className="ml-1 font-normal text-ink/60">optional</span></summary>
              <div className="pt-4">
              <Field label="Authorized audio URL" name="audio_url" defaultValue="" placeholder="https://…" />
              <label className="mt-4 block text-sm">
                <span className="font-medium">Or upload a recording</span>
                <input type="file" accept="audio/*,video/mp4,video/webm" className="workspace-upload mt-2 block w-full min-w-0 text-xs text-ink/70" onChange={(event) => setAudio(event.target.files?.[0] ?? null)} />
              </label>
              <p className="mt-2 text-xs leading-5 text-ink/60">Audio is transcribed; video frames become timestamped observations. A recording is not an independent test.</p>
              </div>
            </details>
            {error ? <p role="alert" className="text-sm text-clay">{error}</p> : null}
            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line pt-5">
              <p className="text-xs text-ink/60">Every finding keeps its evidence trail.</p>
              <button type="submit" disabled={pending} className="workspace-primary">{pending ? "Starting" : "Start assessment"}<span aria-hidden="true">→</span></button>
            </div>
          </form>
        </section>
        <div className="min-w-0 space-y-6">
          <section className="workspace-panel">
            <div className="panel-heading"><div><p className="eyebrow">How the review works</p><h2 className="mt-2 text-lg font-medium">Evidence, not a sales pitch.</h2></div></div>
            <ol className="review-method">
              <li><span>01</span><div><h3>Read the right product</h3><p>Collect relevant sources. Keep unrelated applications out of the knowledge map.</p></div></li>
              <li><span>02</span><div><h3>Observe the actual workflow</h3><p>Connect recorded demos and real interface exploration to specific controls.</p></div></li>
              <li><span>03</span><div><h3>Make the limits explicit</h3><p>Separate documented, observed and independently verified evidence in the assessment.</p></div></li>
            </ol>
          </section>
          <section className="workspace-panel">
            <div className="panel-heading"><h2 className="text-base font-medium">Recent runs</h2><span className="text-xs text-ink/60">Retained evidence</span></div>
            <div className="max-h-80 overflow-y-auto overscroll-contain" tabIndex={0} aria-label="Recent assessments; scroll to earlier runs">
              {projects.length === 0 ? <p className="p-6 text-sm text-ink/65">No projects yet. Start your first assessment above.</p> : null}
              {projects.map((project) => (
                <Link key={project.id} href={`/projects/${project.id}`} className="run-row">
                  <div className="flex min-w-0 items-center justify-between gap-3"><p className="truncate text-sm font-medium">{project.software_name} {project.software_version}</p><span className="run-status" data-status={project.status}>{project.status === "failed" ? "Stopped" : project.status}</span></div>
                  <p className="mt-2 line-clamp-2 text-xs leading-5 text-ink/65">{project.learning_objective}</p><time dateTime={project.created_at} className="mt-2 block text-xs text-ink/65">{new Date(project.created_at).toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" })}</time>
                </Link>
              ))}
            </div>
            <p className="border-t border-line px-6 py-3 text-xs text-ink/65">Scroll to earlier runs ↓ · Technical test runs are retained, not deleted.</p>
          </section>
        </div>
      </div>
      <footer className="mt-8 flex flex-wrap justify-between gap-3 border-t border-line pt-5 text-xs text-ink/60"><span>AppDNA / Application intelligence</span><span>Decision support. Not procurement approval or formal UAT sign-off.</span></footer>
    </main>
  );
}

function Field({ label, name, defaultValue, placeholder }: { label: string; name: string; defaultValue: string; placeholder?: string }) {
  return <label className="block text-sm"><span className="font-medium">{label}</span><input name={name} defaultValue={defaultValue} placeholder={placeholder} className="workspace-input mt-2 w-full" /></label>;
}

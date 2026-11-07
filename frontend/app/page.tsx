"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { createProject, listProjects } from "@/lib/api";
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
    <main className="mx-auto grid max-w-6xl gap-10 px-6 py-10 lg:grid-cols-[1.1fr_0.9fr]">
      <section>
        <p className="font-mono text-xs uppercase tracking-[0.18em] text-signal">AppDNA</p>
        <h1 className="mt-3 font-serif text-5xl leading-tight">Teach AI any software.</h1>
        <p className="mt-4 max-w-xl text-lg leading-relaxed text-ink/80">
          Name any Mac app, including an internal visual tool. The agent opens it, looks at the window, and learns by clicking. A capability is verified only when a separate test can prove it.
        </p>
        <form onSubmit={onSubmit} className="mt-8 space-y-4 rounded-3xl border border-line bg-white/5 p-5 shadow-[0_0_80px_rgba(61,255,176,0.05)]">
          <Field label="Application name" name="software_name" defaultValue="Blender" placeholder="The macOS app name" />
          <Field label="Version" name="software_version" defaultValue="5.2" />
          <label className="block text-sm">
            <span className="font-medium">Learning objective</span>
            <textarea
              name="learning_objective"
              required
              minLength={8}
              defaultValue="Learn the main controls of this application by clicking them"
              className="mt-1 min-h-24 w-full rounded-xl border border-line bg-paper px-3 py-2"
            />
          </label>
          <Field label="Authorized audio URL" name="audio_url" defaultValue="" placeholder="Optional" />
          <label className="block text-sm">
            <span className="font-medium">Or upload a recording</span>
            <input
              type="file"
              accept="audio/*,video/mp4,video/webm"
              className="mt-1 block w-full text-sm"
              onChange={(event) => setAudio(event.target.files?.[0] ?? null)}
            />
          </label>
          {error ? <p className="text-sm text-clay">{error}</p> : null}
          <button
            type="submit"
            disabled={pending}
            className="rounded-full bg-ink px-5 py-2 text-sm text-paper disabled:opacity-60"
          >
            {pending ? "Starting" : "Start learning"}
          </button>
        </form>
      </section>
      <section>
        <h2 className="font-serif text-2xl">Recent runs</h2>
        <div className="mt-4 space-y-3">
          {projects.length === 0 ? <p className="text-sm text-ink/60">No projects yet.</p> : null}
          {projects.map((project) => (
            <Link
              key={project.id}
              href={`/projects/${project.id}`}
              className="block rounded-2xl border border-line bg-white/5 p-4 hover:border-signal"
            >
              <div className="flex items-center justify-between gap-3">
                <p className="font-medium">
                  {project.software_name} {project.software_version}
                </p>
                <span className="font-mono text-xs uppercase text-signal">{project.status}</span>
              </div>
              <p className="mt-2 text-sm text-ink/70">{project.learning_objective}</p>
            </Link>
          ))}
        </div>
      </section>
    </main>
  );
}

function Field({
  label,
  name,
  defaultValue,
  placeholder,
}: {
  label: string;
  name: string;
  defaultValue: string;
  placeholder?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="font-medium">{label}</span>
      <input
        name={name}
        defaultValue={defaultValue}
        placeholder={placeholder}
        className="mt-1 w-full rounded-xl border border-line bg-paper px-3 py-2"
      />
    </label>
  );
}

import type { ProjectDetail, ProjectSummary } from "./types";

export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8787";

export async function createProject(input: {
  software_name: string;
  software_version: string;
  learning_objective: string;
  audio_url: string;
  audio: File | null;
}): Promise<ProjectSummary> {
  const hasFile = input.audio && input.audio.size > 0;
  const response = hasFile
    ? await fetch(`${API_BASE}/api/projects`, { method: "POST", body: formData(input) })
    : await fetch(`${API_BASE}/api/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          software_name: input.software_name,
          software_version: input.software_version || null,
          learning_objective: input.learning_objective,
          audio_url: input.audio_url || null,
        }),
      });
  if (!response.ok) {
    throw new Error(await errorText(response));
  }
  return response.json();
}

export async function listProjects(): Promise<ProjectSummary[]> {
  const response = await fetch(`${API_BASE}/api/projects`, { cache: "no-store" });
  if (!response.ok) throw new Error(await errorText(response));
  return response.json();
}

export async function getProject(id: string): Promise<ProjectDetail> {
  const response = await fetch(`${API_BASE}/api/projects/${id}`, { cache: "no-store" });
  if (!response.ok) throw new Error(await errorText(response));
  return response.json();
}

export async function resumeProject(id: string): Promise<ProjectSummary> {
  const response = await fetch(`${API_BASE}/api/projects/${id}/resume`, { method: "POST" });
  if (!response.ok) throw new Error(await errorText(response));
  return response.json();
}

export function packageUrl(id: string): string {
  return `${API_BASE}/api/projects/${id}/package`;
}

export function frameUrl(id: string, image: string): string {
  return `${API_BASE}/api/projects/${id}/frames/${image}`;
}

export const mediaUrl = (id: string, name: string) => `${API_BASE}/api/projects/${id}/media/${encodeURIComponent(name)}`;
export const reportUrl = (id: string) => `${API_BASE}/api/projects/${id}/report`;

export function previewUrl(id: string, version: string): string {
  return `${API_BASE}/api/projects/${id}/preview?v=${encodeURIComponent(version)}`;
}

function formData(input: {
  software_name: string;
  software_version: string;
  learning_objective: string;
  audio_url: string;
  audio: File | null;
}): FormData {
  const data = new FormData();
  data.set("software_name", input.software_name);
  data.set("software_version", input.software_version);
  data.set("learning_objective", input.learning_objective);
  data.set("audio_url", input.audio_url);
  if (input.audio) data.set("audio", input.audio);
  return data;
}

async function errorText(response: Response): Promise<string> {
  try {
    const body = await response.json();
    if (typeof body.detail === "string") return body.detail;
    return JSON.stringify(body.detail ?? body);
  } catch {
    return `Request failed (${response.status})`;
  }
}

// Uploaded video sources belong to the API origin, not the Next.js origin.
export function sourceUrl(url: string): string {
  if (/^https?:\/\//i.test(url)) return url;
  if (/^\/api\/projects\/[A-Za-z0-9_-]+\/media\/original$/.test(url)) return `${API_BASE}${url}`;
  return "#";
}

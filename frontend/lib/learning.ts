export const LEARNING_API = "/api/learning";
export type LearnedStep = { id: string; instruction: string; expected: string; start: number; end: number; evidence_ids: string[]; uncertainty?: string };
export type VideoEvidence = { id: string; timestamp: number; image: string; observations: string[]; uncertainties: string[] };
export type VideoKnowledge = {
  title: string; objective: string; source_file: string; source_url?: string; source_sha256: string;
  status: string; verification: string; steps: LearnedStep[]; evidence: VideoEvidence[];
  prerequisites: string[]; limitations: string[];
};
export type LearnedSource = { id: string; title: string; objective: string; status: string; source_url?: string };
export type SourceCatalog = { items: LearnedSource[]; has_more: boolean };
export type Execution = {
  id: string; source_job_id?: string; status: string; error?: string; action_model?: string;
  run?: { events?: { step?: string; before?: string; after?: string; action?: { action?: string; reason?: string }; status?: string; reason?: string }[]; reason?: string };
  verification?: { verification?: string; scope?: string; target_binding_sha256?: string; source_sha256?: string; read_only_hash_unchanged?: boolean; artifact?: string };
  artifact_targets?: { binding_sha256?: string; source_sha256?: string };
};
export const ACTIVE_RUN = new Set(["starting_blender", "checking_artifact_targets", "running", "saving_artifact"]);
export async function learningRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${LEARNING_API}/${path}`, { cache: "no-store", ...init });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(typeof body?.detail === "string" ? body.detail : `Learning request failed (${response.status})`);
  }
  return response.json() as Promise<T>;
}
export const learningAsset = (id: string, name: string) => `${LEARNING_API}/assets/${id}/${name.split("/").map(encodeURIComponent).join("/")}`;
export const clock = (seconds: number) => `${Math.floor(seconds / 60)}:${Math.floor(seconds % 60).toString().padStart(2, "0")}`;
export function independentlyVerified(run: Execution): boolean {
  const result = run.verification;
  return run.status === "verified" && result?.verification === "verified" && result.scope === "blender_bevel_v1"
    && result.read_only_hash_unchanged === true && Boolean(result.artifact && result.target_binding_sha256 && result.source_sha256)
    && result.target_binding_sha256 === run.artifact_targets?.binding_sha256
    && result.source_sha256 === run.artifact_targets?.source_sha256;
}
export function runLabel(status: string): string {
  return ({ ready_for_review: "Not started", starting_blender: "Preparing Blender", checking_artifact_targets: "Checking source-bound targets",
    running: "Agent is operating Blender", saving_artifact: "Saving and checking artifact", blocked: "Execution blocked",
    stopped: "Stopped", observed_complete: "GUI steps observed complete", saved_unverified: "Saved · not independently verified",
    artifact_failed: "Artifact check failed", verified: "Artifact check returned" } as Record<string, string>)[status] ?? status.replaceAll("_", " ");
}

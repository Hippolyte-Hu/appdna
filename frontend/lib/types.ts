export type ProjectSummary = {
  id: string;
  software_name: string;
  target_url: string | null;
  target_kind: "website" | "desktop";
  software_version: string | null;
  learning_objective: string;
  status: string;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  package_ready: boolean;
  preview_ready: boolean;
};

export interface ProjectDetail extends ProjectSummary {
  transcripts: { id: string; start: number; end: number; text: string; language: string | null; speaker: string | null }[];
  can_resume: boolean;
  media?: {
    duration: number; has_video: boolean; has_audio: boolean; source_sha256: string;
    frames: { image: string; timestamp: number }[];
    observations: { timestamp: number; result: { same_product?: boolean; product_reason?: string; observations?: { capability: string; control: string; observation: string }[]; limitations?: string[] }; error?: string }[];
  } | null;
  activities: { phase: string; message: string; created_at: string }[];
  sources: {
    id: string;
    title: string;
    url: string;
    source_type: string;
    software_version: string | null;
    reliability: string;
    license: string | null;
    excerpt: string;
    content: string;
    relevant?: boolean | null;
  }[];
  claims: {
    id: string;
    claim: string;
    claim_type: string;
    confidence: number;
    verification_status: string;
    evidence_ids: string[];
  }[];
  capabilities: {
    id: string;
    name: string;
    description: string;
    preconditions: string[];
    inputs: string[];
    expected_outputs: string[];
    verification_status: string;
    confidence: number;
  }[];
  experiments: {
    id: string;
    objective: string;
    result: string;
    verification_status: string;
    object_name: string | null;
    material_name: string | null;
    observations: { attempt: number; status: string; detail: string }[];
  }[];
  evidence: { id: string; origin: string; kind: string; summary: string; created_at: string }[];
  checks: Record<string, boolean> | null;
  frames: {
    step: number;
    action: string;
    x: number;
    y: number;
    text: string;
    thought: string;
    learned: string;
    image: string;
    image_width: number;
    image_height: number;
    executed: boolean;
  }[];
  outcome: {
    evaluation: {
      summary: string;
      verdict: string;
      strengths: string[];
      gaps: string[];
    };
    skills: {
      id: string;
      name: string;
      use_when: string;
      steps: string[];
      tools: string[];
      status: string;
    }[];
    graph: {
      nodes: { id: string; label: string; kind: string }[];
      edges: { source: string; target: string; label: string }[];
    };
  };
};

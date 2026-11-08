export type Criterion = {
  id: string;
  requirement: string;
  team: string | null;
  priority: string;
};
export type Observation = {
  step: number;
  image: string;
  checksum: string;
  image_width: number;
  image_height: number;
  url: string;
  title: string;
};
export type Action = {
  kind: string;
  target: number;
  text: string;
  summary: string;
  target_label: string;
  timestamp: string;
  outcome: string;
  detail?: string;
  observation: Observation;
};
export type Source = {
  id: string;
  url: string;
  title: string;
  finding: string;
  query: string;
  retrieved_at: string;
};
export type Verification = {
  id: string;
  requirement: string;
  expected: { team: string | null; priority: string };
  actual: { team: string | null; priority: string } | null;
  status: string;
  input: { message: string; customer_tier: string };
  checked_at: string;
  conversation_id?: number;
  url?: string;
  detail?: string;
  method: string;
  record?: Record<string, unknown>;
};
export type Run = {
  id: string;
  task_id: string;
  status: string;
  stage: string;
  control: string;
  summary: string;
  max_actions: number;
  timeout_seconds: number;
  reuse_knowledge: boolean;
  created_at: string;
  updated_at: string;
  ended_at: string | null;
  stages: Record<string, string>;
  blockers: string[];
  plan: string[];
  actions: Action[];
  sources: Source[];
  verifications: Verification[];
  knowledge_refs: string[];
  requested_knowledge_ids?: string[] | null;
  environment?: Pick<Environment, "url" | "account_id" | "inbox_id"> & {
    software?: string;
    version?: string;
    model?: string;
    agent_protocol?: string;
  };
  saved_knowledge_id?: string;
  observation?: Observation;
  activities: {
    id: string;
    stage: string;
    message: string;
    kind: string;
    timestamp: string;
    url?: string;
    step?: number;
  }[];
};
export type Task = {
  id: string;
  title: string;
  request: string;
  scenario: "routing" | "vip";
  software: string;
  software_version: string;
  parent_id: string | null;
  criteria: Criterion[];
  created_at: string;
  latest_run: Run | null;
  runs?: Run[];
};
export type Environment = {
  id: string;
  name: string;
  software: string;
  version: string;
  url: string;
  account_id: number;
  inbox_id: number;
  ready: boolean;
  research: string;
  permissions: string[];
  checks: { id: string; label: string; ready: boolean; detail: string }[];
  reachable?: boolean;
  probe_message?: string;
};
export type Knowledge = {
  id: string;
  software: string;
  software_version: string;
  operation: string;
  run_id: string;
  validated_at: string;
  preconditions: string[];
  procedure: string[];
  completion_check: string[];
  unresolved: string[];
  permissions: string[];
  source_refs: string[];
  related_runs: string[];
  applicability: string;
};

export type Connections = {
  model: { provider: string; model: string; api_key_saved: boolean };
  search: { provider: string; api_key_saved: boolean };
  chatwoot: {
    url: string;
    account_id: number;
    inbox_id: number;
    version: string;
    api_token_saved: boolean;
    session_saved: boolean;
    test_environment: boolean;
  };
  browser_installed: boolean;
  ready: boolean;
};
export type LoginState = {
  status: "idle" | "opening" | "waiting" | "connected" | "failed";
  message: string;
};

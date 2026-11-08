import type {
  Connections,
  Environment,
  Knowledge,
  LoginState,
  Run,
  Task,
} from "./task-types";
import type { KnowledgeGraphData } from "./knowledge-graph";

export const TASK_API = process.env.NEXT_PUBLIC_API_BASE ?? "";
export const TERMINAL = new Set([
  "completed",
  "failed",
  "blocked",
  "cancelled",
]);
export const BASE_REQUEST =
  "We receive support messages about refunds, deliveries, and serious complaints. Route refunds to Billing, delivery questions to Logistics, and serious complaints to Customer Care with urgent priority. Leave unrelated messages unassigned.";
export const VIP_REQUEST =
  "VIP customers must receive high priority for ordinary refunds and deliveries. Keep their destination team unchanged. Serious complaints, including VIP complaints, must remain urgent. Preserve all existing non-VIP routing.";

export async function request<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${TASK_API}/api${path}`, {
      ...options,
      headers: { "Content-Type": "application/json", ...options?.headers },
      cache: "no-store",
    });
  } catch {
    throw new Error(
      "AppDNA is unavailable. Try again after the server has started.",
    );
  }
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(
      typeof body?.detail === "string"
        ? body.detail
        : `The request could not be completed (${response.status}). Please retry.`,
    );
  }
  return response.json();
}
export const listTasks = () => request<Task[]>("/tasks");
export const getTask = (id: string) => request<Task>(`/tasks/${id}`);
export const createTask = (input: {
  title: string;
  request: string;
  scenario: string;
  parent_id?: string;
}) => request<Task>("/tasks", { method: "POST", body: JSON.stringify(input) });
export const startRun = (
  id: string,
  input = { max_actions: 80, timeout_seconds: 600, reuse_knowledge: true },
) =>
  request<Run>(`/tasks/${id}/runs`, {
    method: "POST",
    body: JSON.stringify(input),
  });
export const controlRun = (id: string, action: string) =>
  request<Run>(`/task-runs/${id}/control`, {
    method: "POST",
    body: JSON.stringify({ action }),
  });
export const getEnvironment = () => request<Environment>("/environments");
export const probeEnvironment = () =>
  request<Environment>("/environments/probe", { method: "POST" });
export const listKnowledge = () => request<Knowledge[]>("/knowledge");
export const getKnowledgeGraph = () =>
  request<KnowledgeGraphData>("/knowledge/graph");
export const getConnections = () => request<Connections>("/connections");
export const saveModelKey = (api_key: string) =>
  request<Connections>("/connections/model", {
    method: "PUT",
    body: JSON.stringify({ api_key }),
  });
export const saveSearchKey = (api_key: string) =>
  request<Connections>("/connections/search", {
    method: "PUT",
    body: JSON.stringify({ api_key }),
  });
export const saveChatwoot = (input: {
  url: string;
  account_id: number;
  inbox_id: number;
  api_token?: string;
  test_environment: boolean;
}) =>
  request<Connections>("/connections/chatwoot", {
    method: "PUT",
    body: JSON.stringify(input),
  });
export const openChatwootLogin = () =>
  request<LoginState>("/connections/chatwoot/login", { method: "POST" });
export const getLoginState = () =>
  request<LoginState>("/connections/chatwoot/login");
export const cancelChatwootLogin = () =>
  request<LoginState>("/connections/chatwoot/login", { method: "DELETE" });
export const evidenceUrl = (id: string, image: string) =>
  `${TASK_API}/api/task-runs/${id}/evidence/${image}`;
export const reportUrl = (id: string) =>
  `${TASK_API}/api/task-runs/${id}/report`;

export function formatDate(date: string, time = false) {
  return new Intl.DateTimeFormat("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "Europe/Paris",
    ...(time ? { hour: "2-digit", minute: "2-digit" } : {}),
  }).format(new Date(date));
}
export function formatTime(date: string) {
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZone: "Europe/Paris",
  }).format(new Date(date));
}

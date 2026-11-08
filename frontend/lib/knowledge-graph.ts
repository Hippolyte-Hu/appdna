export type NodeKind = "app" | "skill" | "run" | "check" | "source";
export type GraphOutcome = { team: string | null; priority: string };
export type GraphCheck = {
  check_id: string;
  requirement: string;
  expected: GraphOutcome;
  actual: GraphOutcome | null;
  status: string;
  checked_at?: string;
};
export type KnowledgeNode = {
  id: string;
  kind: NodeKind;
  label: string;
  status?: string;
  version?: string;
  software?: string;
  operation?: string;
  title?: string;
  knowledge_id?: string;
  run_id?: string;
  task_id?: string;
  validated_at?: string;
  created_at?: string;
  step_count?: number;
  passed?: number;
  total?: number;
  action_count?: number;
  checks?: GraphCheck[];
  expected?: GraphOutcome;
  outcomes?: Record<string, number>;
  result_url?: string;
  image_url?: string;
  url?: string;
};
export type KnowledgeLink = {
  id: string;
  source: string;
  target: string;
  relation: "contains" | "learned_in" | "reused_in" | "references" | "checked";
  status?: string;
  expected?: GraphOutcome;
  actual?: GraphOutcome | null;
};
export type KnowledgeGraphData = {
  schema_version: number;
  generated_at: string;
  nodes: KnowledgeNode[];
  links: KnowledgeLink[];
  counts: Partial<Record<NodeKind, number>>;
};

export const GRAPH_KINDS: NodeKind[] = [
  "app",
  "skill",
  "check",
  "run",
  "source",
];
export const GRAPH_LABELS: Record<NodeKind, string> = {
  app: "App",
  skill: "Skill",
  check: "Check",
  run: "Run",
  source: "Source",
};
export const GRAPH_COLORS: Record<NodeKind, string> = {
  app: "#246553",
  skill: "#6f946e",
  check: "#b6a075",
  run: "#627d7b",
  source: "#a4ad92",
};
export const RELATION_LABELS: Record<KnowledgeLink["relation"], string> = {
  contains: "Skills",
  learned_in: "Learned in",
  reused_in: "Reused in",
  references: "Sources",
  checked: "Checks",
};

export function outcomeLabel(outcome?: GraphOutcome | null) {
  if (!outcome) return "Not verified";
  const value = outcome.priority === "default" ? "Standard" : outcome.priority;
  return `${outcome.team || "Unassigned"} · ${value.charAt(0).toUpperCase() + value.slice(1)}`;
}

export function nodeCaption(node: KnowledgeNode) {
  if (node.kind === "app") return `${node.label} ${node.version || ""}`.trim();
  if (node.kind === "run") return `Run · ${node.passed}/${node.total}`;
  if (node.kind === "skill") return node.label.split(" · ")[0];
  return node.label;
}

export function relatedNodes(graph: KnowledgeGraphData, id: string) {
  const ids = new Set([id]);
  for (const link of graph.links) {
    if (link.source === id) ids.add(link.target);
    if (link.target === id) ids.add(link.source);
  }
  return ids;
}

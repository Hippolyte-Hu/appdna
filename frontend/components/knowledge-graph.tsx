"use client";

import Link from "next/link";
import dynamic from "next/dynamic";
import {
  Component,
  Fragment,
  useCallback,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  ArrowUpRight,
  BookOpen,
  Box,
  Check,
  CircleX,
  Focus,
  MousePointer2,
  RotateCcw,
  Search,
  Type,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  GRAPH_KINDS,
  GRAPH_LABELS,
  outcomeLabel,
  relatedNodes,
  type KnowledgeGraphData,
  type KnowledgeNode,
  type NodeKind,
} from "@/lib/knowledge-graph";
import { formatDate, TASK_API } from "@/lib/task-api";
import type { Knowledge } from "@/lib/task-types";
import type { GraphCanvasHandle } from "./knowledge-graph-canvas";
import { EmptyState, Status } from "./ui";

const GraphCanvas = dynamic(
  () =>
    import("./knowledge-graph-canvas").then(
      (module) => module.KnowledgeGraphCanvas,
    ),
  {
    ssr: false,
    loading: () => <Skeleton className="knowledge-canvas" />,
  },
);

class GraphBoundary extends Component<
  { children: ReactNode; onUnavailable: () => void; onShowList: () => void },
  { failed: boolean; retry: number }
> {
  state = { failed: false, retry: 0 };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch() {
    this.props.onUnavailable();
  }
  render() {
    if (this.state.failed)
      return (
        <div className="knowledge-canvas graph-unavailable">
          <Box className="size-8 text-muted-foreground" />
          <h3>The 3D view couldn’t open</h3>
          <p>Your saved skills are still available.</p>
          <div className="flex gap-2">
            <Button
              variant="outline"
              onClick={() =>
                this.setState({ failed: false, retry: this.state.retry + 1 })
              }
            >
              Try again
            </Button>
            <Button onClick={this.props.onShowList}>View skills</Button>
          </div>
        </div>
      );
    return <Fragment key={this.state.retry}>{this.props.children}</Fragment>;
  }
}

function KindDot({ kind }: { kind: NodeKind }) {
  return (
    <span className={`graph-kind-dot graph-kind-${kind}`} aria-hidden="true" />
  );
}

export function KnowledgeGraph({
  graph,
  entries,
  onOpenSkill,
  onShowList,
}: {
  graph: KnowledgeGraphData;
  entries: Knowledge[];
  onOpenSkill: (entry: Knowledge) => void;
  onShowList: () => void;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState<NodeKind | "all">("all");
  const [labels, setLabels] = useState(false);
  const [ready, setReady] = useState(false);
  const canvas = useRef<GraphCanvasHandle>(null);
  const onReady = useCallback(() => setReady(true), []);
  const onUnavailable = useCallback(() => setReady(false), []);
  const selected = graph.nodes.find((node) => node.id === selectedId) || null;
  const matches = useMemo(() => {
    const text = query.trim().toLowerCase();
    return graph.nodes.filter(
      (node) =>
        (kind === "all" || node.kind === kind) &&
        (!text ||
          `${node.label} ${node.id} ${node.operation || ""} ${node.version || ""} ${JSON.stringify(node.expected || "")}`
            .toLowerCase()
            .includes(text)),
    );
  }, [graph, query, kind]);
  const highlighted = useMemo(() => {
    if (selectedId) return relatedNodes(graph, selectedId);
    if (!query.trim() && kind === "all") return null;
    const ids = new Set<string>();
    for (const node of matches)
      for (const id of relatedNodes(graph, node.id)) ids.add(id);
    return ids;
  }, [graph, matches, selectedId, query, kind]);
  const select = useCallback((id: string | null) => {
    setSelectedId(id);
    setQuery("");
  }, []);
  const reset = () => {
    setSelectedId(null);
    setKind("all");
    setQuery("");
    canvas.current?.fit();
  };

  if (!graph.nodes.length)
    return (
      <Card>
        <CardContent>
          <EmptyState title="No saved knowledge yet" artwork>
            <Button variant="outline" asChild>
              <Link href="/tasks">Go to tasks</Link>
            </Button>
          </EmptyState>
        </CardContent>
      </Card>
    );

  return (
    <div className="knowledge-graph-layout">
      <Card className="knowledge-map-card">
        <div className="knowledge-map-toolbar">
          <div className="graph-search">
            <Search className="size-4 text-muted-foreground" />
            <Input
              type="search"
              aria-label="Search knowledge"
              placeholder={
                kind === "all"
                  ? "Find a skill, check or run…"
                  : `Search ${GRAPH_LABELS[kind].toLowerCase()}s…`
              }
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setSelectedId(null);
              }}
              onKeyDown={(event) => {
                if (event.key === "Enter" && matches[0]) {
                  event.preventDefault();
                  select(matches[0].id);
                }
                if (event.key === "Escape") setQuery("");
              }}
            />
            {query.trim() ? (
              <div className="graph-search-results">
                <p role="status">
                  {matches.length} {matches.length === 1 ? "match" : "matches"}
                </p>
                <ul aria-label="Knowledge search results">
                  {matches.slice(0, 8).map((node) => (
                    <li key={node.id}>
                      <Button
                        variant="ghost"
                        className="graph-search-result"
                        onClick={() => select(node.id)}
                      >
                        <KindDot kind={node.kind} />
                        <span>{node.label}</span>
                        <span className="text-muted-foreground">
                          {GRAPH_LABELS[node.kind]}
                        </span>
                      </Button>
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </div>
          <Button variant="ghost" size="sm" onClick={reset} disabled={!ready}>
            <RotateCcw />
            Reset view
          </Button>
        </div>
        <div className="graph-filters" aria-label="Highlight node type">
          <Button
            variant={kind === "all" ? "secondary" : "ghost"}
            size="sm"
            aria-pressed={kind === "all"}
            onClick={() => {
              setKind("all");
              setSelectedId(null);
              canvas.current?.fit();
            }}
          >
            Everything
          </Button>
          {GRAPH_KINDS.map((value) => (
            <Button
              key={value}
              variant={kind === value ? "secondary" : "ghost"}
              size="sm"
              aria-pressed={kind === value}
              aria-label={`Highlight ${GRAPH_LABELS[value].toLowerCase()}s`}
              onClick={() => {
                setKind(value);
                setSelectedId(null);
                canvas.current?.fit();
              }}
            >
              <KindDot kind={value} />
              {GRAPH_LABELS[value]}s
              <span className="graph-type-count">
                {graph.counts[value] || 0}
              </span>
            </Button>
          ))}
        </div>
        <div className="graph-stage">
          <GraphBoundary onShowList={onShowList} onUnavailable={onUnavailable}>
            <GraphCanvas
              ref={canvas}
              graph={graph}
              selectedId={selectedId}
              highlighted={highlighted}
              showLabels={labels}
              focusedKind={kind}
              onSelect={select}
              onReady={onReady}
            />
          </GraphBoundary>
          <div className="graph-view-controls">
            {(
              [
                {
                  name: "Zoom in",
                  icon: ZoomIn,
                  action: () => canvas.current?.zoom(1),
                },
                {
                  name: "Zoom out",
                  icon: ZoomOut,
                  action: () => canvas.current?.zoom(-1),
                },
                {
                  name: "Fit graph",
                  icon: Focus,
                  action: () => canvas.current?.fit(),
                },
              ] as const
            ).map(({ name, icon: Icon, action }) => (
              <Tooltip key={name}>
                <TooltipTrigger asChild>
                  <Button
                    variant="outline"
                    size="icon-sm"
                    aria-label={name}
                    onClick={action}
                    disabled={!ready}
                  >
                    <Icon />
                  </Button>
                </TooltipTrigger>
                <TooltipContent>{name}</TooltipContent>
              </Tooltip>
            ))}
          </div>
        </div>
        <div className="graph-map-footer">
          <span>
            <MousePointer2 className="size-3.5" />
            Drag to rotate · Scroll to zoom
          </span>
          <Button
            variant={labels ? "secondary" : "ghost"}
            size="sm"
            aria-pressed={labels}
            aria-label="Show all node labels"
            onClick={() => setLabels(!labels)}
          >
            <Type />
            Labels
          </Button>
        </div>
      </Card>
      <GraphInspector
        graph={graph}
        node={selected}
        select={select}
        entries={entries}
        onOpenSkill={onOpenSkill}
      />
    </div>
  );
}

function GraphInspector({
  graph,
  node,
  select,
  entries,
  onOpenSkill,
}: {
  graph: KnowledgeGraphData;
  node: KnowledgeNode | null;
  select: (id: string | null) => void;
  entries: Knowledge[];
  onOpenSkill: (entry: Knowledge) => void;
}) {
  const connected = node
    ? graph.links.filter(
        (link) => link.source === node.id || link.target === node.id,
      )
    : [];
  const entry = entries.find((item) => item.id === node?.knowledge_id);
  const targets = connected
    .map((link) => ({
      link,
      other: graph.nodes.find(
        (item) =>
          item.id === (link.source === node?.id ? link.target : link.source),
      )!,
    }))
    .filter((item) => item.other);
  const groups = [...new Set(targets.map(({ other }) => other.kind))];
  return (
    <Card className="graph-inspector" aria-label="Knowledge details">
      {!node ? (
        <CardContent>
          <div className="graph-overview-title">
            <BookOpen className="size-5" />
            <h2>Learned by doing</h2>
          </div>
          <div className="graph-overview-count">
            <strong>{graph.counts.skill || 0}</strong>
            <span>saved skills</span>
          </div>
          <dl className="graph-overview-stats">
            <div>
              <dt>Recorded runs</dt>
              <dd>{graph.counts.run || 0}</dd>
            </div>
            <div>
              <dt>Outcome checks</dt>
              <dd>{graph.counts.check || 0}</dd>
            </div>
            <div>
              <dt>Documentation sources</dt>
              <dd>{graph.counts.source || 0}</dd>
            </div>
          </dl>
          <section className="graph-detail-section">
            <h3>Recently learned</h3>
            {graph.nodes
              .filter((item) => item.kind === "skill")
              .slice(0, 4)
              .map((item) => (
                <Button
                  variant="ghost"
                  key={item.id}
                  className="graph-related-node"
                  onClick={() => select(item.id)}
                >
                  <KindDot kind="skill" />
                  <span>{item.label}</span>
                  <ArrowUpRight />
                </Button>
              ))}
          </section>
        </CardContent>
      ) : (
        <CardContent>
          <div className="graph-inspector-heading">
            <Badge variant="secondary">
              <KindDot kind={node.kind} />
              {GRAPH_LABELS[node.kind]}
            </Badge>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Clear node selection"
              onClick={() => select(null)}
            >
              <X />
            </Button>
          </div>
          <h2>{node.kind === "run" ? node.title || node.label : node.label}</h2>
          {node.kind === "skill" ? (
            <>
              <p className="graph-inspector-summary">{node.operation}</p>
              <dl className="graph-detail-list">
                <div>
                  <dt>App</dt>
                  <dd>
                    {node.software} {node.version}
                  </dd>
                </div>
                <div>
                  <dt>Demonstrated steps</dt>
                  <dd>{node.step_count}</dd>
                </div>
                <div>
                  <dt>Last validated</dt>
                  <dd>{formatDate(node.validated_at!, true)}</dd>
                </div>
              </dl>
              <Badge variant="secondary">
                {node.status === "verified" ? (
                  <Check className="size-3" />
                ) : null}
                {node.status === "verified"
                  ? "Independently verified"
                  : "Evidence unavailable"}
              </Badge>
              {entry ? (
                <Button
                  className="w-full mt-4"
                  onClick={() => onOpenSkill(entry)}
                >
                  View skill
                  <ArrowUpRight />
                </Button>
              ) : null}
            </>
          ) : null}
          {node.kind === "run" ? (
            <>
              <div className="graph-run-result">
                <strong>
                  {node.passed}/{node.total}
                </strong>
                <Status value={node.status || "unverified"} />
              </div>
              <dl className="graph-detail-list">
                <div>
                  <dt>Recorded actions</dt>
                  <dd>{node.action_count}</dd>
                </div>
                <div>
                  <dt>Started</dt>
                  <dd>{formatDate(node.created_at!, true)}</dd>
                </div>
              </dl>
              {node.result_url ? (
                <Button asChild className="w-full">
                  <Link href={node.result_url}>
                    View results
                    <ArrowUpRight />
                  </Link>
                </Button>
              ) : null}
              {node.image_url ? (
                <a
                  className="graph-evidence-preview"
                  href={TASK_API + node.image_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  <img
                    src={TASK_API + node.image_url}
                    alt="Recorded Chatwoot screenshot from this run"
                    loading="lazy"
                  />
                </a>
              ) : null}
            </>
          ) : null}
          {node.kind === "check" ? (
            <>
              <div className="graph-check-expected">
                <span>Expected outcome</span>
                <strong>{outcomeLabel(node.expected)}</strong>
              </div>
              <div className="flex flex-wrap gap-2">
                {Object.entries(node.outcomes || {}).map(([status, count]) => (
                  <Badge key={status} variant="secondary">
                    {count} {status}
                  </Badge>
                ))}
              </div>
            </>
          ) : null}
          {node.kind === "app" ? (
            <p className="graph-inspector-summary">Version {node.version}</p>
          ) : null}
          {node.kind === "source" && node.url ? (
            <>
              <p className="graph-inspector-summary break-all">
                {new URL(node.url).hostname}
              </p>
              <Button asChild className="w-full mt-4">
                <a href={node.url} target="_blank" rel="noreferrer">
                  Open documentation
                  <ArrowUpRight />
                </a>
              </Button>
            </>
          ) : null}
          {groups.map((kind) => (
            <section className="graph-detail-section" key={kind}>
              <h3>
                {kind === "run"
                  ? node.kind === "skill"
                    ? "Validation and reuse"
                    : "Checked in"
                  : kind === "skill"
                    ? "Connected skills"
                    : kind === "check"
                      ? "Independent checks"
                      : kind === "source"
                        ? "Sources"
                        : "App"}
              </h3>
              <div className="graph-related-list">
                {targets
                  .filter((item) => item.other.kind === kind)
                  .map(({ link, other }) => (
                    <Button
                      key={link.id}
                      variant="ghost"
                      className="graph-related-node"
                      onClick={() => select(other.id)}
                    >
                      {link.status === "passed" ? (
                        <Check className="size-3.5 text-primary" />
                      ) : link.status === "failed" ? (
                        <CircleX className="size-3.5 text-destructive" />
                      ) : (
                        <KindDot kind={other.kind} />
                      )}
                      <span>
                        {other.kind === "run" ? (
                          <>
                            <strong>
                              {link.relation === "reused_in"
                                ? "Reused"
                                : link.relation === "learned_in"
                                  ? "Learned"
                                  : other.title}
                            </strong>
                            <small>
                              {other.passed}/{other.total} checks ·{" "}
                              {formatDate(other.created_at!, true)}
                            </small>
                          </>
                        ) : (
                          other.label
                        )}
                        {link.relation === "checked" &&
                        link.status === "failed" ? (
                          <small>{outcomeLabel(link.actual)}</small>
                        ) : null}
                      </span>
                      <ArrowUpRight />
                    </Button>
                  ))}
              </div>
            </section>
          ))}
        </CardContent>
      )}
    </Card>
  );
}

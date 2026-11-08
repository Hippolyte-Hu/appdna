"use client";

import { useMemo, useRef, useState } from "react";
import { Background, Controls, MarkerType, MiniMap, Position, ReactFlow, useNodesState, type Edge, type Node, type ReactFlowInstance } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { ProjectDetail } from "@/lib/types";

type Graph = ProjectDetail["outcome"]["graph"];
const COLOR: Record<string, string> = { app: "#a6d8bd", skill: "#e9edf3", tool: "#e8ae8a", concept: "#97acd1" };
const COLUMN: Record<string, number> = { app: 0, skill: 1, tool: 2, concept: 3 };
const START_VIEW = { x: 12, y: 24, zoom: 1 };

function layout(graph: Graph): Node[] {
  const groups = ["app", "skill", "tool", "concept"].map(kind => graph.nodes.filter(node => node.kind === kind));
  return graph.nodes.map(node => {
    const column = COLUMN[node.kind] ?? 3;
    const index = groups[column].findIndex(item => item.id === node.id);
    return {
      id: node.id,
      data: { label: <div data-node-id={node.id}><span className="graph-node-kind">{node.id.startsWith("source:") ? "Source" : node.kind}</span><strong>{node.label}</strong></div> },
      position: { x: column === 0 ? 0 : 300 + (column - 1) * 600 + (index % 2) * 260, y: Math.floor(index / 2) * 115 },
      ariaLabel: `${node.kind}: ${node.label}`,
      sourcePosition: Position.Right, targetPosition: Position.Left,
      style: { borderColor: COLOR[node.kind], width: 220 },
      className: `evidence-node evidence-node-${node.kind}`,
      deletable: false, connectable: false,
    };
  });
}

export function InteractiveGraph({ graph, onSelect }: { graph: Graph; onSelect: (id: string) => void }) {
  // Preserve dragged positions during polling; reset only when graph content changes.
  const signature = JSON.stringify(graph);
  return <GraphCanvas key={signature} graph={graph} onSelect={onSelect} />;
}

function GraphCanvas({ graph, onSelect }: { graph: Graph; onSelect: (id: string) => void }) {
  const [nodes, setNodes, onNodesChange] = useNodesState(layout(graph));
  const [active, setActive] = useState<string | null>(graph.nodes.find(node => node.kind === "skill")?.id ?? "app");
  const [expanded, setExpanded] = useState(false);
  const view = useRef<ReactFlowInstance<Node, Edge> | null>(null);
  const [motion, setMotion] = useState(false);
  const [minimap, setMinimap] = useState(false);
  const edges: Edge[] = useMemo(() => graph.edges.map((edge, i) => {
    const focused = !active || edge.source === active || edge.target === active;
    return {
      ...edge, id: `${edge.source}-${edge.target}-${i}`, label: focused ? edge.label : "",
      // Focus changes presentation, never the retained graph data or node reachability.
      hidden: !focused, animated: motion && focused,
      style: { stroke: COLOR.app, strokeWidth: 1.7, opacity: 0.85 },
      markerEnd: { type: MarkerType.ArrowClosed, color: COLOR.app, width: 15, height: 15 },
      labelStyle: { fill: "#e9edf3", fontSize: 13 }, labelBgStyle: { fill: "#111822", fillOpacity: 0.95 },
      deletable: false,
    };
  }), [graph.edges, active, motion]);
  const displayNodes = nodes.map(node => ({ ...node, selected: node.id === active, style: { ...node.style, borderWidth: node.id === active ? 2 : 1 } }));
  const button = "min-h-11 rounded-lg border border-line px-3 py-2 text-xs text-ink/85 hover:border-signal/50 hover:text-signal";

  return (
    <section className={`min-w-0 overflow-hidden rounded-2xl border border-line bg-[#0c1119] ${expanded ? "fixed inset-4 z-50 overflow-y-auto shadow-2xl" : ""}`} aria-label="Interactive application knowledge graph">
      <header className="flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <div><h2 className="text-2xl font-medium tracking-tight">Living evidence map</h2><p className="mt-2 max-w-xl text-xs leading-5 text-ink/70">Select a node to inspect its evidence. Highlighted lines show only its relationships.</p></div>
        <button type="button" aria-pressed={motion} onClick={() => setMotion(value => !value)} className={button}>{motion ? "Pause flow" : "Animate flow"}</button>
      </header>
      <div className="flex flex-wrap gap-2 border-y border-line px-5 py-3">
        <button type="button" className={button} onClick={() => { void view.current?.setViewport(START_VIEW, { duration: 0 }); }}>Focus app</button>
        <button type="button" className={button} onClick={() => { void view.current?.fitView({ padding: 0.15, duration: 0 }); }}>Fit all</button>
        <button type="button" className={button} onClick={() => setExpanded(value => !value)}>{expanded ? "Close expanded map" : "Expand map"}</button>
        <button type="button" className={button} aria-pressed={minimap} onClick={() => setMinimap(value => !value)}>{minimap ? "Hide minimap" : "Show minimap"}</button>
      </div>
      <div className="graph-canvas" style={{ height: expanded ? "calc(100vh - 300px)" : 560 }}>
        <ReactFlow<Node, Edge> nodes={displayNodes} edges={edges} onNodesChange={onNodesChange}
          onInit={instance => { view.current = instance; onSelect(active ?? "app"); }}
          onNodeClick={(_, node) => { setActive(node.id); onSelect(node.id); }}
          nodesConnectable={false} edgesReconnectable={false} deleteKeyCode={null}
          defaultViewport={START_VIEW} minZoom={0.08} maxZoom={2.5}
          colorMode="dark" proOptions={{ hideAttribution: false }}
          ariaLabelConfig={{ "controls.zoomIn.ariaLabel": "Zoom in", "controls.zoomOut.ariaLabel": "Zoom out", "controls.fitView.ariaLabel": "Fit view" }}>
          <Background gap={24} color="#202c3c" />
          <Controls showInteractive={false} />
          {minimap ? <MiniMap pannable zoomable style={{ width: 110, height: 80 }} nodeColor={node => String(node.style?.borderColor || COLOR.concept)} maskColor="rgba(5,9,14,0.75)" /> : null}
        </ReactFlow>
      </div>
      <footer className="space-y-2 border-t border-line px-5 py-3 text-xs leading-5 text-ink/70">
        <p>Drag nodes · pan empty canvas · scroll to zoom. Type colors are not verification scores.</p>
        <div className="flex flex-wrap items-center justify-between gap-2"><span>{graph.nodes.length} nodes · {graph.edges.length} connections · all evidence retained</span><button type="button" onClick={() => setNodes(layout(graph))} className="min-h-11 px-2 text-signal">Reset layout</button></div>
      </footer>
      <label className="block border-t border-line px-5 py-3 text-xs text-ink/75">Jump to evidence
        <select aria-label="Select graph evidence" className="mt-2 block min-h-11 w-full rounded-lg border border-line bg-paper px-3 py-2 text-sm" defaultValue="" onChange={event => { if (event.target.value) { setActive(event.target.value); onSelect(event.target.value); void view.current?.fitView({ nodes: [{ id: event.target.value }], padding: 0.6, maxZoom: 1, duration: 0 }); } }}>
          <option value="" disabled>Select an app, skill, tool or source</option>
          {graph.nodes.map(node => <option value={node.id} key={node.id}>{node.kind} · {node.label}</option>)}
        </select>
      </label>
    </section>
  );
}

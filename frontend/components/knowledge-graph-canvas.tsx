"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";
import ForceGraph3D, { type ForceGraphMethods } from "react-force-graph-3d";
import SpriteText from "three-spritetext";
import {
  GRAPH_COLORS,
  GRAPH_LABELS,
  nodeCaption,
  type KnowledgeGraphData,
  type KnowledgeLink,
  type KnowledgeNode,
  type NodeKind,
} from "@/lib/knowledge-graph";

type RenderNode = KnowledgeNode & {
  x?: number;
  y?: number;
  z?: number;
  fx?: number;
  fy?: number;
  fz?: number;
};
type RenderLink = Omit<KnowledgeLink, "source" | "target"> & {
  source: string | RenderNode;
  target: string | RenderNode;
};
export type GraphCanvasHandle = {
  fit: () => void;
  zoom: (direction: number) => void;
};
type Props = {
  graph: KnowledgeGraphData;
  selectedId: string | null;
  highlighted: Set<string> | null;
  showLabels: boolean;
  focusedKind: NodeKind | "all";
  onSelect: (id: string | null) => void;
  onReady: () => void;
};
const endpoint = (value: RenderLink["source"]) =>
  typeof value === "string" ? value : value.id;
const escapeLabel = (value: string) =>
  value.replace(
    /[&<>"']/g,
    (char) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        char
      ]!,
  );

export const KnowledgeGraphCanvas = forwardRef<GraphCanvasHandle, Props>(
  function KnowledgeGraphCanvas(
    {
      graph,
      selectedId,
      highlighted,
      showLabels,
      focusedKind,
      onSelect,
      onReady,
    },
    ref,
  ) {
    const host = useRef<HTMLDivElement>(null);
    const engine = useRef<
      ForceGraphMethods<RenderNode, RenderLink> | undefined
    >(undefined);
    const labels = useRef(new Map<string, SpriteText>());
    const [size, setSize] = useState({ width: 0, height: 520 });
    const [hovered, setHovered] = useState<string | null>(null);
    const [settled, setSettled] = useState(false);
    const [lost, setLost] = useState(false);
    const [reducedMotion, setReducedMotion] = useState(false);
    const data = useMemo(() => {
      const kinds = new Map<string, KnowledgeNode[]>();
      for (const node of graph.nodes)
        kinds.set(node.kind, [...(kinds.get(node.kind) || []), node]);
      const nodes: RenderNode[] = graph.nodes.map((node) => {
        const group = kinds.get(node.kind)!;
        const index = group.findIndex((item) => item.id === node.id);
        const angle = (index / group.length) * Math.PI * 2 + 0.4;
        const radius =
          node.kind === "app"
            ? 0
            : node.kind === "skill"
              ? 120
              : node.kind === "run"
                ? 220
                : 270;
        const x = Math.cos(angle) * radius;
        const y = Math.sin(angle) * radius * 0.7;
        const z =
          node.kind === "source"
            ? -130
            : node.kind === "check"
              ? -35
              : node.kind === "run"
                ? -90
                : node.kind === "app"
                  ? 75
                  : 35;
        return {
          ...node,
          x,
          y,
          z,
          fx: x,
          fy: y,
          fz: z,
        };
      });
      return {
        nodes,
        links: graph.links.map((link): RenderLink => ({ ...link })),
      };
    }, [graph]);

    useEffect(() => {
      if (!host.current) return;
      const observer = new ResizeObserver(([entry]) =>
        setSize({
          width: Math.round(entry.contentRect.width),
          height: Math.round(entry.contentRect.height),
        }),
      );
      observer.observe(host.current);
      return () => observer.disconnect();
    }, []);
    useEffect(() => {
      const media = matchMedia("(prefers-reduced-motion: reduce)");
      setReducedMotion(media.matches);
      const change = () => setReducedMotion(media.matches);
      media.addEventListener("change", change);
      return () => media.removeEventListener("change", change);
    }, []);
    useEffect(() => {
      const sprites = labels.current;
      return () => {
        for (const sprite of sprites.values()) {
          sprite.material.map?.dispose();
          sprite.material.dispose();
        }
        sprites.clear();
      };
    }, [data]);

    const fitGraph = useCallback(() => {
      const fg = engine.current;
      if (!fg || !size.width || !size.height) return;
      const xs = data.nodes.map((node) => node.fx || 0);
      const ys = data.nodes.map((node) => node.fy || 0);
      const zs = data.nodes.map((node) => node.fz || 0);
      const left = Math.min(...xs),
        right = Math.max(...xs);
      const bottom = Math.min(...ys),
        top = Math.max(...ys);
      const near = Math.max(...zs),
        far = Math.min(...zs);
      const target = {
        x: (left + right) / 2,
        y: (bottom + top) / 2,
        z: (near + far) / 2,
      };
      const fov =
        (((fg.camera() as { fov?: number }).fov || 50) * Math.PI) / 180;
      const distance =
        Math.max(
          (top - bottom + 60) / (2 * Math.tan(fov / 2)),
          (right - left + 80) /
            ((2 * Math.tan(fov / 2) * size.width) / size.height),
        ) +
        (near - far) / 2;
      fg.cameraPosition(
        { x: target.x, y: target.y, z: target.z + distance },
        target,
        reducedMotion ? 0 : 500,
      );
    }, [data, size, reducedMotion]);

    useEffect(() => {
      if (settled && !selectedId) fitGraph();
    }, [settled, selectedId, fitGraph]);

    const focus = useCallback(
      (id: string) => {
        const node = data.nodes.find((item) => item.id === id);
        const fg = engine.current;
        if (
          !node ||
          !fg ||
          node.x === undefined ||
          node.y === undefined ||
          node.z === undefined
        )
          return;
        const camera = fg.camera().position;
        const dx = camera.x - node.x,
          dy = camera.y - node.y,
          dz = camera.z - node.z;
        const distance = Math.hypot(dx, dy, dz) || 1;
        const ratio = 400 / distance;
        fg.cameraPosition(
          {
            x: node.x + dx * ratio,
            y: node.y + dy * ratio,
            z: node.z + dz * ratio,
          },
          { x: node.x, y: node.y, z: node.z },
          reducedMotion ? 0 : 650,
        );
      },
      [data, reducedMotion],
    );
    useEffect(() => {
      if (selectedId && settled) focus(selectedId);
    }, [selectedId, settled, focus]);

    useImperativeHandle(
      ref,
      () => ({
        fit: fitGraph,
        zoom: (direction) => {
          const fg = engine.current;
          if (!fg) return;
          const camera = fg.camera().position;
          const target = (
            fg.controls() as { target?: { x: number; y: number; z: number } }
          ).target || { x: 0, y: 0, z: 0 };
          const factor = direction > 0 ? 0.78 : 1.28;
          fg.cameraPosition(
            {
              x: target.x + (camera.x - target.x) * factor,
              y: target.y + (camera.y - target.y) * factor,
              z: target.z + (camera.z - target.z) * factor,
            },
            target,
            reducedMotion ? 0 : 250,
          );
        },
      }),
      [reducedMotion, fitGraph],
    );

    useEffect(() => {
      if (!engine.current || !size.width) return;
      const fg = engine.current;
      const canvas = fg.renderer().domElement;
      const contextLost = (event: Event) => {
        event.preventDefault();
        setLost(true);
      };
      canvas.addEventListener("webglcontextlost", contextLost);
      onReady();
      return () => canvas.removeEventListener("webglcontextlost", contextLost);
    }, [size.width, onReady]);

    useEffect(() => {
      for (const node of data.nodes) {
        const label = labels.current.get(node.id);
        if (!label) continue;
        const primary =
          node.kind === "app" ||
          node.kind === "skill" ||
          node.kind === "check" ||
          node.kind === focusedKind;
        label.visible =
          node.id === selectedId ||
          node.id === hovered ||
          ((showLabels || primary) &&
            (!highlighted || highlighted.has(node.id)));
        label.color = node.id === selectedId ? "#174b3c" : "#43564a";
      }
    }, [
      data,
      selectedId,
      hovered,
      highlighted,
      showLabels,
      focusedKind,
      settled,
    ]);

    const labelObject = useCallback((node: RenderNode) => {
      let label = labels.current.get(node.id);
      if (!label) {
        const caption = nodeCaption(node);
        label = new SpriteText(
          caption.length > 26 ? caption.slice(0, 24).trimEnd() + "…" : caption,
          node.kind === "app" ? 15 : node.kind === "skill" ? 12 : 9,
          "#43564a",
        );
        label.fontFace = "Geist, sans-serif";
        label.fontWeight = node.kind === "app" ? "600" : "500";
        label.backgroundColor = "#f5f7f3e8";
        label.padding = [1.2, 2];
        label.borderRadius = 1.5;
        label.position.y = node.kind === "app" ? -16 : -13;
        label.material.depthWrite = false;
        label.visible =
          node.kind === "app" || node.kind === "skill" || node.kind === "check";
        labels.current.set(node.id, label);
      }
      return label;
    }, []);

    if (lost) throw new Error("The 3D context became unavailable.");
    return (
      <div
        ref={host}
        className="knowledge-canvas"
        role="region"
        aria-label="3D knowledge graph"
        aria-busy={!settled}
      >
        {size.width > 0 ? (
          <ForceGraph3D<RenderNode, RenderLink>
            ref={engine}
            graphData={data}
            width={size.width}
            height={size.height}
            controlType="orbit"
            backgroundColor="#f5f7f3"
            showNavInfo={false}
            nodeRelSize={5.2}
            nodeOpacity={1}
            nodeResolution={16}
            nodeVal={(node) =>
              node.kind === "app" ? 8 : node.kind === "skill" ? 3 : 1.2
            }
            nodeColor={(node) =>
              highlighted && !highlighted.has(node.id)
                ? "#d9e0d3"
                : node.status === "failed"
                  ? "#b47b68"
                  : GRAPH_COLORS[node.kind]
            }
            nodeLabel={(node) =>
              `<strong>${escapeLabel(node.label)}</strong><br/>${GRAPH_LABELS[node.kind]}${node.status ? " · " + escapeLabel(node.status) : ""}`
            }
            nodeThreeObject={labelObject}
            nodeThreeObjectExtend
            linkColor={(link) =>
              highlighted &&
              !(
                highlighted.has(endpoint(link.source)) &&
                highlighted.has(endpoint(link.target))
              )
                ? "#e6ebe0"
                : link.status === "failed"
                  ? "#b7836e"
                  : "#a5b7a2"
            }
            linkWidth={(link) =>
              selectedId &&
              (endpoint(link.source) === selectedId ||
                endpoint(link.target) === selectedId)
                ? 1.7
                : 0.7
            }
            linkOpacity={0.4}
            linkDirectionalArrowLength={2.7}
            linkDirectionalArrowRelPos={0.75}
            linkLabel={(link) =>
              link.relation.replaceAll("_", " ") +
              (link.status ? " · " + escapeLabel(link.status) : "")
            }
            enableNodeDrag={false}
            warmupTicks={0}
            cooldownTicks={0}
            onNodeClick={(node) => onSelect(node.id)}
            onBackgroundClick={() => onSelect(null)}
            onNodeHover={(node) => setHovered(node?.id || null)}
            onEngineStop={() => {
              setSettled(true);
            }}
          />
        ) : null}
      </div>
    );
  },
);

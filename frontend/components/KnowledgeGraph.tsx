"use client";

import { useState } from "react";
import { sourceUrl } from "@/lib/api";
import { InteractiveGraph } from "./InteractiveGraph";
import type { ProjectDetail } from "@/lib/types";

type Outcome = ProjectDetail["outcome"];
type Node = Outcome["graph"]["nodes"][number];
type Edge = Outcome["graph"]["edges"][number];

export function KnowledgeGraph({ outcome, sources }: { outcome: Outcome; sources: ProjectDetail["sources"] }) {
  const [selected, setSelected] = useState(outcome.skills[0]?.id ?? "app");
  const skill = outcome.skills.find((item) => item.id === selected);
  const article = outcome.graph.nodes.find((node) => selected === `concept:${node.id}`);
  const source = article?.id.startsWith("source:") ? sources.find((item) => article.id === `source:${item.id}`) : undefined;

  return (
    <div className="grid items-start gap-4 lg:grid-cols-[1.35fr_0.65fr]">
      <InteractiveGraph graph={outcome.graph} onSelect={(id) => {
        const node = outcome.graph.nodes.find(item => item.id === id);
        if (node) setSelected(node.kind === "concept" ? `concept:${id}` : skillIdFor(node, outcome.graph.edges));
      }} />
      <aside className="rounded-2xl border border-line bg-white/5 p-5">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-signal">{outcome.evaluation.verdict}</p>
        <h3 className="mt-2 font-sans text-2xl font-medium">App evaluation</h3>
        <p className="mt-3 text-sm leading-relaxed text-ink/70">{outcome.evaluation.summary}</p>
        <h4 className="mt-5 font-mono text-[11px] uppercase text-ink/45">Candidate strengths · check evidence status</h4>
        <ul className="mt-2 space-y-1 text-sm">
          {outcome.evaluation.strengths.length ? (
            outcome.evaluation.strengths.map((item) => <li key={item}>{item}</li>)
          ) : (
            <li className="text-ink/45">None recorded.</li>
          )}
        </ul>
        <h4 className="mt-4 font-mono text-[11px] uppercase text-ink/45">Gaps</h4>
        <ul tabIndex={0} aria-label="All saved coverage gaps; scroll to read" className="mt-2 max-h-64 space-y-1 overflow-y-auto text-sm leading-6 text-ink/75">
          {outcome.evaluation.gaps.length ? outcome.evaluation.gaps.map((item) => <li key={item}>{item}</li>) : <li>None recorded.</li>}
        </ul>
        {article ? (
          <div className="mt-5 border-t border-line pt-4">
            <p className="font-mono text-[11px] uppercase text-[#8ea0c8]">From the articles</p>
            <p className="mt-2 text-sm leading-relaxed">{article.label}</p>
            {source ? (
              <div className="mt-4 min-w-0">
                <h4 className="text-lg">{source.title}</h4>
                <a href={sourceUrl(source.url)} target="_blank" rel="noopener noreferrer" className="mt-2 inline-block text-sm text-signal underline">Read full article ↗</a>
                <p className="mt-4 font-mono text-[11px] uppercase text-ink/45">Collected source text</p>
                <pre tabIndex={0} data-testid="article-content" className="mt-2 max-h-96 overflow-y-auto whitespace-pre-wrap break-words font-sans text-sm leading-relaxed text-ink/75">{source.content || source.excerpt || "No text was collected. Open the original article above."}</pre>
              </div>
            ) : null}
          </div>
        ) : skill ? (
          <div className="mt-5 border-t border-line pt-4">
            <p className="font-mono text-[11px] uppercase text-clay">{skill.status}</p>
            <h4 className="mt-1 text-xl">{skill.name}</h4>
            <p className="mt-2 text-sm text-ink/70">{skill.use_when}</p>
            <p className="mt-3 font-mono text-[11px] uppercase text-ink/45">Tools</p>
            <p className="mt-1 text-sm">{skill.tools.join(" · ")}</p>
            <ol className="mt-3 list-decimal space-y-1 pl-4 text-sm">
              {skill.steps.map((step, index) => (
                <li key={`${skill.id}-${index}`}>{step}</li>
              ))}
            </ol>
          </div>
        ) : (
          <p className="mt-5 text-sm text-ink/50">Select a skill to see how that tool is used.</p>
        )}
      </aside>
    </div>
  );
}

function skillIdFor(node: Node, edges: Edge[]) {
  if (node.kind === "skill") return node.id.slice("skill:".length);
  if (node.kind === "tool") {
    const edge = edges.find((item) => item.target === node.id && item.label === "uses");
    if (edge?.source.startsWith("skill:")) return edge.source.slice("skill:".length);
  }
  return "app";
}

"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowUpRight,
  List,
  LoaderCircle,
  Network,
  RefreshCw,
  Search,
} from "lucide-react";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  formatDate,
  getKnowledgeGraph,
  listKnowledge,
  request,
} from "@/lib/task-api";
import type { KnowledgeGraphData } from "@/lib/knowledge-graph";
import type { Knowledge } from "@/lib/task-types";
import { AppShell } from "./app-shell";
import { EmptyState, ErrorNotice } from "./ui";
import { KnowledgeGraph } from "./knowledge-graph";

export function KnowledgeLibrary() {
  const router = useRouter();
  const [entries, setEntries] = useState<Knowledge[]>([]);
  const [graph, setGraph] = useState<KnowledgeGraphData | null>(null);
  const [graphError, setGraphError] = useState("");
  const [view, setView] = useState("graph");
  const [query, setQuery] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Knowledge | null>(null);
  const [opening, setOpening] = useState(false);
  const load = useCallback(() => {
    setLoading(true);
    Promise.allSettled([listKnowledge(), getKnowledgeGraph()])
      .then(([skills, graphResult]) => {
        if (skills.status === "fulfilled") {
          setEntries(skills.value);
          setError("");
        } else
          setError(
            skills.reason instanceof Error
              ? skills.reason.message
              : "Saved skills could not be loaded.",
          );
        if (graphResult.status === "fulfilled") {
          setGraph(graphResult.value);
          setGraphError("");
        } else
          setGraphError(
            graphResult.reason instanceof Error
              ? graphResult.reason.message
              : "The graph could not be loaded.",
          );
      })
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);
  async function viewRun(item: Knowledge) {
    setOpening(true);
    try {
      const report = await request<{ task: { id: string } }>(
        `/task-runs/${item.run_id}/report`,
      );
      router.push(`/tasks/${report.task.id}/results?run=${item.run_id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "The run could not be opened.",
      );
    } finally {
      setOpening(false);
    }
  }
  const filtered = entries.filter((item) =>
    `${item.operation} ${item.software}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  );
  return (
    <AppShell section="Knowledge">
      <main className="app-page">
        <div className="page-heading">
          <h1>Knowledge</h1>
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw />
            Refresh
          </Button>
        </div>
        {error ? <ErrorNotice message={error} retry={load} /> : null}
        <Tabs value={view} onValueChange={setView}>
          <TabsList className="knowledge-view-tabs">
            <TabsTrigger value="graph">
              <Network />
              3D graph
            </TabsTrigger>
            <TabsTrigger value="list">
              <List />
              Skills
            </TabsTrigger>
          </TabsList>
          <TabsContent value="graph">
            {loading ? (
              <Skeleton className="h-[600px]" />
            ) : graphError ? (
              <div className="space-y-4">
                <ErrorNotice message={graphError} retry={load} />
                <Button variant="outline" onClick={() => setView("list")}>
                  View skills
                </Button>
              </div>
            ) : graph ? (
              <KnowledgeGraph
                graph={graph}
                entries={entries}
                onOpenSkill={setSelected}
                onShowList={() => setView("list")}
              />
            ) : null}
          </TabsContent>
          <TabsContent value="list">
            <Card>
              <CardContent>
                <div className="table-toolbar">
                  <div className="search-field">
                    <Search />
                    <Input
                      type="search"
                      placeholder="Search skills"
                      aria-label="Search skills"
                      value={query}
                      onChange={(event) => setQuery(event.target.value)}
                    />
                  </div>
                </div>
                {loading ? (
                  <Skeleton className="h-44" />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Skill</TableHead>
                        <TableHead className="hidden md:table-cell">
                          App
                        </TableHead>
                        <TableHead className="hidden sm:table-cell">
                          Last successful run
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filtered.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell>
                            <Button
                              variant="link"
                              className="skill-name"
                              onClick={() => setSelected(item)}
                            >
                              {item.operation}
                              <ArrowUpRight />
                            </Button>
                          </TableCell>
                          <TableCell className="hidden md:table-cell">
                            {item.software} {item.software_version}
                          </TableCell>
                          <TableCell className="hidden sm:table-cell">
                            {formatDate(item.validated_at, true)}
                          </TableCell>
                        </TableRow>
                      ))}
                      {!filtered.length ? (
                        <TableRow>
                          <TableCell colSpan={3}>
                            <EmptyState
                              title={
                                query
                                  ? "No matching skills"
                                  : "No saved skills yet"
                              }
                              artwork
                            >
                              {!query ? (
                                <Button variant="outline" asChild>
                                  <Link href="/tasks">Go to tasks</Link>
                                </Button>
                              ) : null}
                            </EmptyState>
                          </TableCell>
                        </TableRow>
                      ) : null}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
        <Sheet
          open={!!selected}
          onOpenChange={(open) => {
            if (!open) setSelected(null);
          }}
        >
          <SheetContent className="detail-sheet sm:max-w-[640px]">
            <SheetHeader>
              <SheetTitle>{selected?.operation || "Saved skill"}</SheetTitle>
              <SheetDescription className="sr-only">
                Steps and evidence from a successful run.
              </SheetDescription>
            </SheetHeader>
            {selected ? (
              <div className="sheet-body">
                <dl className="detail-list">
                  <dt>App</dt>
                  <dd>
                    {selected.software} {selected.software_version}
                  </dd>
                  <dt>Last worked</dt>
                  <dd>{formatDate(selected.validated_at, true)}</dd>
                  <dt>Access needed</dt>
                  <dd>{selected.permissions.join(", ")}</dd>
                </dl>
                <div>
                  <h3>Steps</h3>
                  <ol className="content-list">
                    {selected.procedure.map((step, index) => (
                      <li key={index}>{step}</li>
                    ))}
                  </ol>
                </div>
                <Accordion type="multiple">
                  <AccordionItem value="when">
                    <AccordionTrigger>
                      When this skill can be reused
                    </AccordionTrigger>
                    <AccordionContent>
                      <p>{selected.applicability}</p>
                      <ul className="content-list">
                        {selected.preconditions.map((value, index) => (
                          <li key={index}>{value}</li>
                        ))}
                      </ul>
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="checks">
                    <AccordionTrigger>How success is checked</AccordionTrigger>
                    <AccordionContent>
                      <ul className="content-list">
                        {selected.completion_check.map((value, index) => (
                          <li key={index}>{value}</li>
                        ))}
                      </ul>
                    </AccordionContent>
                  </AccordionItem>
                  <AccordionItem value="sources">
                    <AccordionTrigger>
                      Sources and open questions
                    </AccordionTrigger>
                    <AccordionContent>
                      <div className="flex flex-wrap gap-2">
                        {selected.source_refs.map((value) => (
                          <Badge key={value} variant="secondary">
                            {value}
                          </Badge>
                        ))}
                      </div>
                      <ul className="content-list">
                        {selected.unresolved.map((value, index) => (
                          <li key={index}>{value}</li>
                        ))}
                      </ul>
                    </AccordionContent>
                  </AccordionItem>
                </Accordion>
                <Button onClick={() => viewRun(selected)} disabled={opening}>
                  {opening ? <LoaderCircle className="animate-spin" /> : null}
                  View successful run
                  <ArrowUpRight />
                </Button>
              </div>
            ) : null}
          </SheetContent>
        </Sheet>
      </main>
    </AppShell>
  );
}

"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  Cable,
  Check,
  Download,
  LoaderCircle,
  Maximize2,
  Pause,
  Play,
  Plus,
  Settings2,
  Square,
} from "lucide-react";
import { toast } from "sonner";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { Alert, AlertTitle, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardAction,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  TASK_API,
  TERMINAL,
  VIP_REQUEST,
  controlRun,
  createTask,
  evidenceUrl,
  formatDate,
  formatTime,
  getTask,
  listKnowledge,
  reportUrl,
  startRun,
} from "@/lib/task-api";
import type {
  Criterion,
  Knowledge,
  Observation,
  Run,
  Task,
} from "@/lib/task-types";
import { cn } from "@/lib/utils";
import { AppShell } from "./app-shell";
import { useConnections } from "./providers";
import { Choice, EmptyState, ErrorNotice, Status } from "./ui";

type Budget = {
  max_actions: number;
  timeout_seconds: number;
  reuse_knowledge: boolean;
};
const DEFAULT_BUDGET: Budget = {
  max_actions: 80,
  timeout_seconds: 600,
  reuse_knowledge: true,
};
const STEPS = ["Learn the app", "Make changes", "Check results"];
function currentStep(run: Run | null) {
  return !run
    ? 0
    : run.status === "completed"
      ? 3
      : ["verify", "save"].includes(run.stage)
        ? 2
        : run.stage === "execute"
          ? 1
          : 0;
}
function priority(value?: string) {
  return !value || value === "default"
    ? "Standard"
    : value[0].toUpperCase() + value.slice(1);
}
function destination(
  value: { team: string | null; priority: string } | null | undefined,
) {
  return value
    ? `${value.team || "Unassigned"} · ${priority(value.priority)}`
    : "—";
}
function readableEvent(value: Run["activities"][number]) {
  if (value.message.startsWith("Checking the designated sandbox"))
    return "Checking connections";
  if (value.message.startsWith("Connect the test environment"))
    return "Connection setup required";
  if (value.message.startsWith("Confirmed the API inbox"))
    return "Connected to Chatwoot";
  return value.message;
}
function runNotice(run: Run) {
  if (
    run.stage === "understand" &&
    run.summary.includes("(ReadTimeout)") &&
    run.activities.some((item) =>
      item.message.startsWith("Confirmed the API inbox"),
    )
  ) {
    return "The AI model did not respond in time. Run the task again.";
  }
  return run.summary || "The task needs attention";
}

export function TaskWorkspace({
  id,
  results = false,
}: {
  id: string;
  results?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const selectedRun = params.get("run") || "";
  const runQuery = selectedRun ? `?run=${encodeURIComponent(selectedRun)}` : "";
  const { connections } = useConnections();
  const [task, setTask] = useState<Task | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState("");
  const [streamError, setStreamError] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [budget, setBudget] = useState(DEFAULT_BUDGET);
  const load = useCallback(() => {
    getTask(id)
      .then((value) => {
        setTask(value);
        setError("");
      })
      .catch((err) => setError(err.message));
  }, [id]);
  useEffect(load, [load]);
  const latestId = task?.latest_run?.id;
  const terminal = !task?.latest_run || TERMINAL.has(task.latest_run.status);
  useEffect(() => {
    if (!latestId || terminal) return;
    const stream = new EventSource(
      `${TASK_API}/api/task-runs/${latestId}/events`,
    );
    stream.onmessage = (event) => {
      const next: Run = JSON.parse(event.data);
      setStreamError(false);
      setTask((value) =>
        value
          ? {
              ...value,
              latest_run: next,
              runs: (value.runs || []).map((run) =>
                run.id === next.id ? next : run,
              ),
            }
          : value,
      );
      if (TERMINAL.has(next.status)) stream.close();
    };
    stream.onerror = () => setStreamError(true);
    return () => stream.close();
  }, [latestId, terminal]);
  const run =
    (task?.runs?.find((value) => value.id === selectedRun) ||
      task?.latest_run) ??
    null;
  const historical = !!run && run.id !== latestId;
  const active = !!task?.latest_run && !TERMINAL.has(task.latest_run.status);
  const ready = !!connections?.ready;
  const step = currentStep(run);
  async function begin() {
    setPending("run");
    setError("");
    try {
      const next = await startRun(id, budget);
      setTask((value) =>
        value
          ? { ...value, latest_run: next, runs: [next, ...(value.runs || [])] }
          : value,
      );
      router.push(`/tasks/${id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "The task could not be started.",
      );
    } finally {
      setPending("");
    }
  }
  async function control(action: string) {
    if (!task?.latest_run) return;
    setPending(action);
    setError("");
    try {
      const next = await controlRun(task.latest_run.id, action);
      setTask((value) =>
        value
          ? {
              ...value,
              latest_run: next,
              runs: (value.runs || []).map((item) =>
                item.id === next.id ? next : item,
              ),
            }
          : value,
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "The run could not be updated.",
      );
    } finally {
      setPending("");
    }
  }
  function chooseRun(value: string) {
    router.replace(
      value === latestId
        ? pathname
        : `${pathname}?run=${encodeURIComponent(value)}`,
      { scroll: false },
    );
  }
  function applyBudget(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setBudget({
      max_actions: Number(form.get("max_actions")),
      timeout_seconds: Number(form.get("timeout_seconds")),
      reuse_knowledge: form.get("reuse_knowledge") === "on",
    });
    setSettingsOpen(false);
  }
  return (
    <AppShell detail={task?.title || "Task"}>
      <main className="app-page">
        {!task ? (
          <>
            {error ? (
              <ErrorNotice message={error} retry={load} />
            ) : (
              <Skeleton className="h-80" />
            )}
            <Button variant="outline" asChild className="mt-4">
              <Link href="/tasks">
                <ArrowLeft />
                Back to tasks
              </Link>
            </Button>
          </>
        ) : (
          <>
            <div className="page-heading">
              <div className="heading-title">
                <h1>{task.title}</h1>
                <Status value={run?.status || "draft"} />
              </div>
              <div className="heading-actions">
                {active && !historical ? (
                  <>
                    <Button
                      variant="outline"
                      disabled={!!pending}
                      onClick={() =>
                        control(
                          task.latest_run?.control === "pause"
                            ? "resume"
                            : "pause",
                        )
                      }
                    >
                      {pending === "pause" || pending === "resume" ? (
                        <LoaderCircle className="animate-spin" />
                      ) : task.latest_run?.control === "pause" ? (
                        <Play />
                      ) : (
                        <Pause />
                      )}
                      {task.latest_run?.control === "pause"
                        ? "Resume"
                        : "Pause"}
                    </Button>
                    <Button
                      variant="outline"
                      className="text-destructive"
                      disabled={
                        !!pending || task.latest_run?.control === "stop"
                      }
                      onClick={() => control("stop")}
                    >
                      <Square />
                      Stop
                    </Button>
                  </>
                ) : historical && active ? (
                  <Button onClick={() => router.replace(pathname)}>
                    View current run
                  </Button>
                ) : (
                  <Button
                    disabled={!!pending}
                    onClick={ready ? begin : () => router.push("/settings")}
                  >
                    {pending === "run" ? (
                      <LoaderCircle className="animate-spin" />
                    ) : ready ? (
                      <Play />
                    ) : (
                      <Cable />
                    )}
                    {ready
                      ? run
                        ? "Run again"
                        : "Run task"
                      : "Set up connections"}
                  </Button>
                )}
                <Tooltip>
                  <TooltipTrigger asChild>
                    <Button
                      variant="outline"
                      size="icon"
                      aria-label="Run settings"
                      onClick={() => setSettingsOpen(true)}
                    >
                      <Settings2 />
                    </Button>
                  </TooltipTrigger>
                  <TooltipContent>Run settings</TooltipContent>
                </Tooltip>
              </div>
            </div>
            {error ? <ErrorNotice message={error} retry={load} /> : null}
            {streamError ? (
              <Alert>
                <AlertTitle>Live updates disconnected</AlertTitle>
                <AlertDescription>
                  <Button variant="link" onClick={load}>
                    Reconnect
                  </Button>
                </AlertDescription>
              </Alert>
            ) : null}
            <Tabs
              value={results ? "results" : "workspace"}
              onValueChange={(key) =>
                router.push(
                  `/tasks/${id}${key === "results" ? "/results" : ""}${runQuery}`,
                )
              }
            >
              <div className="workspace-navigation">
                <TabsList className="workspace-tabs">
                  <TabsTrigger value="workspace">Workspace</TabsTrigger>
                  <TabsTrigger value="results">Results</TabsTrigger>
                </TabsList>
                {task.runs?.length ? (
                  <Choice
                    label="Run history"
                    value={run?.id || ""}
                    onChange={chooseRun}
                    className="run-history"
                    options={task.runs.map((item, index) => ({
                      value: item.id,
                      label: `${formatDate(item.created_at, true)}${index === 0 ? " · latest" : ""}`,
                    }))}
                  />
                ) : null}
              </div>
              {historical ? (
                <Alert className="mb-6">
                  <AlertTitle>Viewing an earlier run</AlertTitle>
                  <AlertDescription>
                    <Button
                      variant="link"
                      onClick={() => router.replace(pathname)}
                    >
                      View latest
                    </Button>
                  </AlertDescription>
                </Alert>
              ) : null}
              <TabsContent value="workspace">
                <div className="workflow-steps" aria-label="Run progress">
                  {STEPS.map((title, index) => (
                    <div
                      key={title}
                      className={cn(
                        "workflow-step",
                        run && index === step && "current",
                        index < step && "complete",
                        run &&
                          ["failed", "blocked"].includes(run.status) &&
                          index === step &&
                          "blocked",
                      )}
                    >
                      <Badge variant={index < step ? "default" : "outline"}>
                        {index < step ? (
                          <Check className="size-3.5" />
                        ) : (
                          index + 1
                        )}
                      </Badge>
                      <span>{title}</span>
                    </div>
                  ))}
                </div>
                {run &&
                ["failed", "blocked"].includes(run.status) &&
                (ready || run.actions.length > 0) ? (
                  <Alert
                    variant={
                      run.status === "failed" ? "destructive" : "default"
                    }
                    className="mb-6"
                  >
                    <AlertTitle className="line-clamp-none">
                      {runNotice(run)}
                    </AlertTitle>
                    <AlertDescription>
                      <Button
                        variant="link"
                        onClick={() => setDetailsOpen(true)}
                      >
                        View details
                      </Button>
                    </AlertDescription>
                  </Alert>
                ) : null}
                <div className="workspace-grid">
                  <div className="workspace-main">
                    <SoftwareView run={run} />
                    <Card>
                      <CardHeader>
                        <CardTitle>Task</CardTitle>
                      </CardHeader>
                      <CardContent>
                        <p className="leading-relaxed">{task.request}</p>
                        <Accordion type="single" collapsible className="mt-3">
                          <AccordionItem value="checks" className="border-0">
                            <AccordionTrigger>
                              Checks ({task.criteria.length})
                            </AccordionTrigger>
                            <AccordionContent>
                              <ul className="content-list">
                                {task.criteria.map((item) => (
                                  <li key={item.id}>
                                    {item.requirement} → {destination(item)}
                                  </li>
                                ))}
                              </ul>
                            </AccordionContent>
                          </AccordionItem>
                        </Accordion>
                      </CardContent>
                    </Card>
                  </div>
                  <ActivityPanel run={run} />
                </div>
              </TabsContent>
              <TabsContent value="results">
                <TaskResults task={task} run={run} />
              </TabsContent>
            </Tabs>
          </>
        )}
        <Dialog open={settingsOpen} onOpenChange={setSettingsOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Run settings</DialogTitle>
              <DialogDescription className="sr-only">
                Limit actions and time for the next run.
              </DialogDescription>
            </DialogHeader>
            <form className="form-stack" onSubmit={applyBudget}>
              <div className="field">
                <Label htmlFor="max-actions">Maximum actions</Label>
                <Input
                  id="max-actions"
                  name="max_actions"
                  type="number"
                  min={5}
                  max={150}
                  defaultValue={budget.max_actions}
                  required
                />
              </div>
              <div className="field">
                <Label htmlFor="time-limit">Time limit</Label>
                <BudgetTime value={budget.timeout_seconds} />
              </div>
              <div className="flex items-center gap-2">
                <Checkbox
                  id="reuse-skills"
                  name="reuse_knowledge"
                  defaultChecked={budget.reuse_knowledge}
                />
                <Label htmlFor="reuse-skills">Use saved skills</Label>
              </div>
              <DialogFooter>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setSettingsOpen(false)}
                >
                  Cancel
                </Button>
                <Button type="submit">Apply</Button>
              </DialogFooter>
            </form>
          </DialogContent>
        </Dialog>
        <Sheet open={detailsOpen} onOpenChange={setDetailsOpen}>
          <SheetContent className="detail-sheet sm:max-w-[680px]">
            <SheetHeader>
              <SheetTitle>Run details</SheetTitle>
              <SheetDescription className="sr-only">
                Recorded run status and connection blockers.
              </SheetDescription>
            </SheetHeader>
            {run ? (
              <div className="sheet-body">
                <div>
                  <Status value={run.status} />
                </div>
                <p>{run.summary}</p>
                {run.blockers.map((item) => (
                  <Alert key={item}>
                    <AlertTitle>{item}</AlertTitle>
                  </Alert>
                ))}
                <dl className="detail-list">
                  <dt>Started</dt>
                  <dd>{formatDate(run.created_at, true)}</dd>
                  <dt>Actions</dt>
                  <dd>{run.actions.length}</dd>
                  <dt>Time limit</dt>
                  <dd>{run.timeout_seconds / 60} minutes</dd>
                </dl>
                <Button variant="outline" asChild>
                  <Link href="/settings">Open connections</Link>
                </Button>
              </div>
            ) : null}
          </SheetContent>
        </Sheet>
      </main>
    </AppShell>
  );
}

function BudgetTime({ value }: { value: number }) {
  const [time, setTime] = useState(String(value));
  return (
    <>
      <input type="hidden" name="timeout_seconds" value={time} />
      <Choice
        label="Time limit"
        value={time}
        onChange={setTime}
        options={[
          { value: "300", label: "5 minutes" },
          { value: "600", label: "10 minutes" },
          { value: "1200", label: "20 minutes" },
        ]}
      />
    </>
  );
}

function SoftwareView({ run }: { run: Run | null }) {
  const { connections } = useConnections();
  const [selected, setSelected] = useState("latest");
  const [expanded, setExpanded] = useState(false);
  useEffect(() => setSelected("latest"), [run?.id]);
  const snapshots = [
    ...new Map(
      [
        ...(run?.actions.map((action) => action.observation) || []),
        ...(run?.observation ? [run.observation] : []),
      ].map((item) => [item.image, item]),
    ).values(),
  ];
  const observation: Observation | undefined =
    selected === "latest"
      ? run?.observation
      : snapshots.find((item) => item.image === selected);
  const missingModel = connections && !connections.model.api_key_saved;
  const appUrl = run?.environment?.url
    ? `${run.environment.url.replace(/\/$/, "")}/app/accounts/${run.environment.account_id}`
    : connections?.chatwoot.url;
  const missingApp =
    connections &&
    (!connections.chatwoot.session_saved ||
      !connections.chatwoot.api_token_saved);
  const emptyLabel = missingApp
    ? "Connect Chatwoot to begin"
    : missingModel
      ? "Add an AI model to begin"
      : run && TERMINAL.has(run.status)
        ? "No screenshot was captured"
        : "Run the task to see Chatwoot here";
  return (
    <Card className="software-card">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <span className="app-indicator" />
          Chatwoot
        </CardTitle>
        <CardAction>
          {appUrl ? (
            <Button variant="ghost" size="icon-sm" asChild>
              <a
                href={appUrl}
                target="_blank"
                rel="noreferrer"
                aria-label="Open Chatwoot"
              >
                <ArrowUpRight />
              </a>
            </Button>
          ) : null}
        </CardAction>
      </CardHeader>
      <CardContent>
        <div
          className={cn("software-view", !observation && "software-view-empty")}
        >
          {observation && run ? (
            <Button
              variant="ghost"
              className="h-auto w-full rounded-none p-0"
              aria-label="Expand screenshot"
              onClick={() => setExpanded(true)}
            >
              <img
                src={evidenceUrl(run.id, observation.image)}
                alt={`Chatwoot screenshot ${observation.step}`}
                className="w-full object-contain"
              />
            </Button>
          ) : (
            <EmptyState title={emptyLabel} artwork />
          )}
        </div>
        {observation && run ? (
          <div className="software-footer">
            <span className="truncate">{observation.title || "Chatwoot"}</span>
            <Choice
              label="Screenshot history"
              value={selected}
              onChange={setSelected}
              options={[
                { value: "latest", label: "Latest screenshot" },
                ...snapshots.map((item) => ({
                  value: item.image,
                  label: `Screenshot ${item.step}`,
                })),
              ]}
            />
          </div>
        ) : null}
      </CardContent>
      <Dialog open={expanded} onOpenChange={setExpanded}>
        <DialogContent className="sm:max-w-[1100px]">
          <DialogHeader>
            <DialogTitle>Chatwoot screenshot</DialogTitle>
            <DialogDescription className="sr-only">
              Actual capture from this run.
            </DialogDescription>
          </DialogHeader>
          {observation && run ? (
            <img
              src={evidenceUrl(run.id, observation.image)}
              alt={`Chatwoot screenshot ${observation.step}`}
              className="max-h-[75vh] w-full object-contain"
            />
          ) : null}
        </DialogContent>
      </Dialog>
    </Card>
  );
}

function ActivityPanel({ run }: { run: Run | null }) {
  const [skills, setSkills] = useState<Knowledge[]>([]);
  useEffect(() => {
    if (run?.knowledge_refs.length)
      void listKnowledge()
        .then(setSkills)
        .catch(() => {});
  }, [run?.id, run?.knowledge_refs.length]);
  const reused = skills.filter((item) => run?.knowledge_refs.includes(item.id));
  return (
    <Card className="activity-card">
      <CardContent>
        <Tabs defaultValue="activity">
          <TabsList className="activity-tabs">
            <TabsTrigger value="activity">Activity</TabsTrigger>
            <TabsTrigger value="skills">Skills used</TabsTrigger>
          </TabsList>
          <TabsContent value="activity">
            {run?.activities.length ? (
              <ol className="activity-log">
                {run.activities.map((item) => (
                  <li key={item.id}>
                    <time>{formatTime(item.timestamp)}</time>
                    <p>{readableEvent(item)}</p>
                    {item.url ? (
                      <a
                        className="text-primary underline underline-offset-4"
                        href={item.url}
                        target="_blank"
                        rel="noreferrer"
                      >
                        Open source
                      </a>
                    ) : null}
                  </li>
                ))}
              </ol>
            ) : (
              <EmptyState title="No activity yet" />
            )}
          </TabsContent>
          <TabsContent value="skills">
            {reused.length ? (
              <div className="space-y-3">
                {reused.map((item) => (
                  <Button
                    key={item.id}
                    variant="link"
                    className="skill-name"
                    asChild
                  >
                    <Link href="/knowledge">{item.operation}</Link>
                  </Button>
                ))}
              </div>
            ) : (
              <EmptyState title="No saved skills used" />
            )}
          </TabsContent>
        </Tabs>
        {run?.saved_knowledge_id ? (
          <Button variant="outline" asChild className="w-full">
            <Link href="/knowledge">View saved skill</Link>
          </Button>
        ) : null}
      </CardContent>
    </Card>
  );
}

function TaskResults({ task, run }: { task: Task; run: Run | null }) {
  const router = useRouter();
  const [selected, setSelected] = useState<Criterion | null>(null);
  const [followUp, setFollowUp] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  const checks = run?.verifications || [];
  const passed = checks.filter((item) => item.status === "passed").length;
  const record = checks.find((item) => item.id === selected?.id);
  async function download() {
    if (!run) return;
    try {
      const response = await fetch(reportUrl(run.id));
      if (!response.ok) throw new Error("The report could not be downloaded.");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${run.id}-report.json`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Download failed.");
    }
  }
  async function addRequirement(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const next = await createTask({
        title: "Add VIP priority to support routing",
        request: `${task.request}\n\nAdditional requirement: ${String(form.get("request")).trim()}`,
        scenario: "vip",
        parent_id: task.id,
      });
      setFollowUp(false);
      router.push(`/tasks/${next.id}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "The requirement could not be added.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <>
      <div className="results-actions">
        <h2>
          {checks.length
            ? `${passed} of ${task.criteria.length} checks passed`
            : "Routing checks"}
        </h2>
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" disabled={!run} onClick={download}>
            <Download />
            Export report
          </Button>
          <Button onClick={() => setFollowUp(true)}>
            <Plus />
            Add requirement
          </Button>
        </div>
      </div>
      <Card>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Check</TableHead>
                <TableHead className="hidden sm:table-cell">Expected</TableHead>
                <TableHead className="hidden md:table-cell">Actual</TableHead>
                <TableHead className="w-[120px]">Result</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {task.criteria.map((item) => (
                <TableRow key={item.id}>
                  <TableCell>
                    <Button
                      variant="link"
                      className="skill-name"
                      onClick={() => setSelected(item)}
                    >
                      {item.requirement}
                    </Button>
                  </TableCell>
                  <TableCell className="hidden sm:table-cell">
                    {destination(item)}
                  </TableCell>
                  <TableCell className="hidden md:table-cell">
                    {destination(
                      checks.find((value) => value.id === item.id)?.actual,
                    )}
                  </TableCell>
                  <TableCell>
                    <Status
                      value={
                        checks.find((value) => value.id === item.id)?.status ||
                        "unverified"
                      }
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
      <Sheet
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <SheetContent className="detail-sheet sm:max-w-[720px]">
          <SheetHeader>
            <SheetTitle>{selected?.requirement || "Check result"}</SheetTitle>
            <SheetDescription className="sr-only">
              Expected and actual routing with recorded evidence.
            </SheetDescription>
          </SheetHeader>
          <div className="sheet-body">
            <div>
              <Status value={record?.status || "unverified"} />
            </div>
            <dl className="detail-list">
              <dt>Expected</dt>
              <dd>{destination(selected)}</dd>
              <dt>Actual</dt>
              <dd>{destination(record?.actual)}</dd>
            </dl>
            {record ? (
              <>
                <dl className="detail-list">
                  <dt>Test message</dt>
                  <dd>{record.input.message}</dd>
                  <dt>Customer</dt>
                  <dd>{record.input.customer_tier}</dd>
                  <dt>Checked</dt>
                  <dd>{formatDate(record.checked_at, true)}</dd>
                </dl>
                {record.url ? (
                  <Button variant="outline" asChild>
                    <a href={record.url} target="_blank" rel="noreferrer">
                      Open test conversation
                      <ArrowUpRight />
                    </a>
                  </Button>
                ) : null}
                {record.detail ? (
                  <Alert>
                    <AlertTitle>{record.detail}</AlertTitle>
                  </Alert>
                ) : null}
              </>
            ) : (
              <EmptyState title="This check has not run yet" />
            )}
            {run?.observation ? (
              <div>
                <h3>Last screenshot</h3>
                <img
                  className="mt-3 w-full rounded-lg border"
                  src={evidenceUrl(run.id, run.observation.image)}
                  alt="Last actual Chatwoot screenshot"
                />
              </div>
            ) : null}
            {record?.record || run?.actions.length ? (
              <Accordion type="multiple">
                {record?.record ? (
                  <AccordionItem value="record">
                    <AccordionTrigger>Raw result</AccordionTrigger>
                    <AccordionContent>
                      <pre className="evidence-json">
                        {JSON.stringify(record.record, null, 2)}
                      </pre>
                    </AccordionContent>
                  </AccordionItem>
                ) : null}
                {run?.actions.length ? (
                  <AccordionItem value="actions">
                    <AccordionTrigger>
                      Actions ({run.actions.length})
                    </AccordionTrigger>
                    <AccordionContent>
                      <ol className="content-list">
                        {run.actions.map((action, index) => (
                          <li key={index}>
                            <p>{action.summary}</p>
                            <p className="text-muted-foreground">
                              {action.outcome} · {action.target_label}
                            </p>
                            {action.detail ? <p>{action.detail}</p> : null}
                          </li>
                        ))}
                      </ol>
                    </AccordionContent>
                  </AccordionItem>
                ) : null}
              </Accordion>
            ) : null}
          </div>
        </SheetContent>
      </Sheet>
      <Dialog
        open={followUp}
        onOpenChange={(value) => {
          if (!pending) setFollowUp(value);
        }}
      >
        <DialogContent className="sm:max-w-[600px]">
          <DialogHeader>
            <DialogTitle>Add requirement</DialogTitle>
            <DialogDescription className="sr-only">
              Create a follow-up task while retaining the original routing
              checks.
            </DialogDescription>
          </DialogHeader>
          <form className="form-stack" onSubmit={addRequirement}>
            {error ? <ErrorNotice message={error} /> : null}
            <div className="field">
              <Label htmlFor="follow-up">What should change?</Label>
              <Textarea
                id="follow-up"
                name="request"
                rows={5}
                defaultValue={VIP_REQUEST}
                required
                minLength={8}
                maxLength={Math.max(8, 3900 - task.request.length)}
              />
            </div>
            <div className="flex flex-wrap gap-2">
              <Badge variant="secondary">VIP priority</Badge>
              <Badge variant="outline">Keep the original routing checks</Badge>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                disabled={pending}
                onClick={() => setFollowUp(false)}
              >
                Cancel
              </Button>
              <Button type="submit" disabled={pending}>
                {pending ? <LoaderCircle className="animate-spin" /> : null}
                Create follow-up task
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </>
  );
}

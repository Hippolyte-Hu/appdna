"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { LoaderCircle, MessagesSquare, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
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
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  BASE_REQUEST,
  createTask,
  formatDate,
  listTasks,
} from "@/lib/task-api";
import type { Task } from "@/lib/task-types";
import { AppShell } from "./app-shell";
import { Choice, EmptyState, ErrorNotice, Status } from "./ui";

export function TasksList() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState("All");
  const [newTask, setNewTask] = useState(false);
  const load = useCallback(() => {
    setLoading(true);
    listTasks()
      .then((value) => {
        setTasks(value);
        setError("");
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);
  useEffect(load, [load]);
  const filtered = tasks.filter(
    (task) =>
      `${task.title} ${task.request}`
        .toLowerCase()
        .includes(query.toLowerCase()) &&
      (filter === "All" ||
        (filter === "Needs attention"
          ? ["failed", "blocked"].includes(task.latest_run?.status || "")
          : filter === "Completed"
            ? task.latest_run?.status === "completed"
            : task.latest_run &&
              !["completed", "failed", "blocked", "cancelled"].includes(
                task.latest_run.status,
              ))),
  );
  return (
    <AppShell>
      <main className="app-page">
        <div className="page-heading">
          <h1>Tasks</h1>
          <Button onClick={() => setNewTask(true)}>
            <Plus />
            New task
          </Button>
        </div>
        {error ? <ErrorNotice message={error} retry={load} /> : null}
        <Card>
          <CardContent>
            <div className="table-toolbar">
              <Choice
                value={filter}
                onChange={setFilter}
                label="Filter tasks"
                className="task-filter"
                options={[
                  { value: "All", label: "All tasks" },
                  { value: "Running", label: "Running" },
                  { value: "Needs attention", label: "Needs attention" },
                  { value: "Completed", label: "Completed" },
                ]}
              />
              <div className="search-field">
                <Search />
                <Input
                  type="search"
                  aria-label="Search tasks"
                  placeholder="Search tasks"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
            </div>
            {loading ? (
              <div className="space-y-4 py-4">
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
                <Skeleton className="h-12" />
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Task</TableHead>
                    <TableHead className="hidden lg:table-cell w-36">
                      App
                    </TableHead>
                    <TableHead className="w-[150px]">Status</TableHead>
                    <TableHead className="hidden md:table-cell w-40">
                      Last updated
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.map((task) => (
                    <TableRow key={task.id}>
                      <TableCell>
                        <Link
                          className="task-name-link"
                          href={`/tasks/${task.id}`}
                        >
                          <span
                            className={
                              task.scenario === "vip"
                                ? "task-glyph vip"
                                : "task-glyph"
                            }
                          >
                            <MessagesSquare />
                          </span>
                          <span>{task.title}</span>
                        </Link>
                      </TableCell>
                      <TableCell className="hidden lg:table-cell text-muted-foreground">
                        {task.software}
                      </TableCell>
                      <TableCell>
                        <Status value={task.latest_run?.status || "draft"} />
                      </TableCell>
                      <TableCell className="hidden md:table-cell text-muted-foreground">
                        {formatDate(
                          task.latest_run?.updated_at || task.created_at,
                          true,
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                  {!filtered.length ? (
                    <TableRow>
                      <TableCell colSpan={4}>
                        <EmptyState
                          title={
                            query || filter !== "All"
                              ? "No matching tasks"
                              : "No tasks yet"
                          }
                        >
                          {!query && filter === "All" ? (
                            <Button onClick={() => setNewTask(true)}>
                              Create a task
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
        <NewTask open={newTask} close={() => setNewTask(false)} />
      </main>
    </AppShell>
  );
}

function NewTask({ open, close }: { open: boolean; close: () => void }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    setPending(true);
    setError("");
    try {
      const task = await createTask({
        title: String(form.get("title")).trim(),
        request: String(form.get("request")).trim(),
        scenario: "routing",
      });
      close();
      router.push(`/tasks/${task.id}`);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "The task could not be created.",
      );
    } finally {
      setPending(false);
    }
  }
  return (
    <Dialog
      open={open}
      onOpenChange={(value) => {
        if (!value && !pending) close();
      }}
    >
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>New task</DialogTitle>
          <DialogDescription className="sr-only">
            Create a task for the Chatwoot test account.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={create} className="form-stack">
          {error ? <ErrorNotice message={error} /> : null}
          <div className="field">
            <Label htmlFor="task-app">App</Label>
            <Input id="task-app" value="Chatwoot · Northstar Goods" readOnly />
          </div>
          <div className="field">
            <Label htmlFor="task-title">Task name</Label>
            <Input
              id="task-title"
              autoFocus
              name="title"
              defaultValue="Configure support routing"
              required
              minLength={3}
              maxLength={160}
              pattern=".*\S.*"
            />
          </div>
          <div className="field">
            <Label htmlFor="task-request">What should the agent do?</Label>
            <Textarea
              id="task-request"
              name="request"
              defaultValue={BASE_REQUEST}
              rows={5}
              required
              minLength={20}
              maxLength={4000}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={close}
              disabled={pending}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={pending}>
              {pending ? <LoaderCircle className="animate-spin" /> : null}Create
              task
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

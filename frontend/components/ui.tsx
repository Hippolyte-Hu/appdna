"use client";

import type { ReactNode } from "react";
import {
  AlertCircle,
  Check,
  CircleDashed,
  Clock3,
  Dna,
  LoaderCircle,
  Pause,
  X,
} from "lucide-react";
import { Alert, AlertTitle } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Empty,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
  EmptyContent,
} from "@/components/ui/empty";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

export function AppMark() {
  return (
    <span className="app-mark" aria-hidden="true">
      <Dna size={23} strokeWidth={1.7} />
    </span>
  );
}

// Decorative brand artwork, never presented as a screenshot or task evidence.
export function StrandArt({ compact = false }: { compact?: boolean }) {
  return (
    <svg
      className={compact ? "strand-art compact" : "strand-art"}
      viewBox="0 0 200 148"
      fill="none"
      aria-hidden="true"
    >
      <g stroke="currentColor" opacity=".13">
        <path d="M24 32h152M24 74h152M24 116h152M48 12v124M100 12v124M152 12v124" />
        <circle cx="100" cy="74" r="60" />
      </g>
      <g stroke="currentColor" strokeWidth="1.5" opacity=".35">
        <path d="M70 26h60M84 42h32M84 58h32M68 74h64M84 90h32M84 106h32M70 122h60" />
      </g>
      <path
        d="M68 22C68 48 132 48 132 74S68 100 68 126"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <path
        d="M132 22C132 48 68 48 68 74S132 100 132 126"
        stroke="#91AA8D"
        strokeWidth="3"
        strokeLinecap="round"
      />
      <circle cx="68" cy="22" r="4" fill="currentColor" />
      <circle cx="132" cy="126" r="4" fill="#B99656" />
    </svg>
  );
}

const LABELS: Record<string, string> = {
  draft: "Draft",
  created: "Queued",
  planning: "Planning",
  researching: "Learning",
  exploring: "Learning",
  executing: "Running",
  verifying: "Testing",
  saving: "Saving",
  running: "Running",
  completed: "Completed",
  passed: "Passed",
  failed: "Failed",
  blocked: "Needs attention",
  cancelled: "Stopped",
  paused: "Paused",
  unverified: "Not tested",
  pending: "Not started",
};
export function Status({ value }: { value: string }) {
  const success = ["completed", "passed"].includes(value);
  const active = [
    "created",
    "planning",
    "researching",
    "exploring",
    "executing",
    "verifying",
    "saving",
    "running",
  ].includes(value);
  const Icon = success
    ? Check
    : value === "failed"
      ? X
      : value === "blocked"
        ? Clock3
        : value === "paused"
          ? Pause
          : active
            ? LoaderCircle
            : CircleDashed;
  return (
    <Badge
      variant="outline"
      className={cn(
        "status-badge",
        success
          ? "status-success"
          : value === "failed"
            ? "status-error"
            : ["blocked", "paused"].includes(value)
              ? "status-warning"
              : active
                ? "status-active"
                : "status-neutral",
      )}
    >
      <Icon className={cn("size-3", active && "animate-spin")} />
      {LABELS[value] || value}
    </Badge>
  );
}
export function ErrorNotice({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <Alert variant="destructive" className="error-notice">
      <AlertCircle />
      <AlertTitle>{message}</AlertTitle>
      {retry ? (
        <Button variant="outline" size="sm" onClick={retry}>
          Retry
        </Button>
      ) : null}
    </Alert>
  );
}
export function EmptyState({
  title,
  children,
  artwork = false,
}: {
  title: string;
  children?: ReactNode;
  artwork?: boolean;
}) {
  return (
    <Empty>
      <EmptyHeader>
        {artwork ? (
          <StrandArt />
        ) : (
          <EmptyMedia variant="icon">
            <Dna />
          </EmptyMedia>
        )}
        <EmptyTitle className="text-sm font-medium text-muted-foreground">
          {title}
        </EmptyTitle>
      </EmptyHeader>
      {children ? <EmptyContent>{children}</EmptyContent> : null}
    </Empty>
  );
}
export function Choice({
  value,
  onChange,
  options,
  label,
  className,
}: {
  value: string;
  onChange: (value: string) => void;
  options: { value: string; label: string }[];
  label: string;
  className?: string;
}) {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger aria-label={label} className={className}>
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((item) => (
          <SelectItem key={item.value} value={item.value}>
            {item.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

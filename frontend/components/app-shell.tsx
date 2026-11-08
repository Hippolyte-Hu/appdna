"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";
import {
  BookOpen,
  Cable,
  ChevronRight,
  LayoutList,
  Menu,
  Monitor,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { AppMark } from "./ui";
import { useConnections } from "./providers";

const NAV = [
  { path: "/tasks", label: "Tasks", icon: LayoutList },
  { path: "/knowledge", label: "Saved skills", icon: BookOpen },
  { path: "/settings", label: "Connections", icon: Cable },
];

export function AppShell({
  children,
  section = "Tasks",
  detail,
}: {
  children: ReactNode;
  section?: string;
  detail?: string;
}) {
  const path = usePathname();
  const [menuOpen, setMenuOpen] = useState(false);
  const { connections } = useConnections();
  const selected = path.startsWith("/knowledge")
    ? "/knowledge"
    : path.startsWith("/settings")
      ? "/settings"
      : "/tasks";
  const label =
    section === "Knowledge"
      ? "Saved skills"
      : section === "Settings"
        ? "Connections"
        : section;
  const nav = (
    <nav className="sidebar-nav" aria-label="Main navigation">
      {NAV.map((item) => (
        <Button
          key={item.path}
          variant="ghost"
          asChild
          className={selected === item.path ? "nav-item selected" : "nav-item"}
        >
          <Link
            href={item.path}
            aria-current={selected === item.path ? "page" : undefined}
            onClick={() => setMenuOpen(false)}
          >
            <item.icon />
            {item.label}
          </Link>
        </Button>
      ))}
    </nav>
  );
  return (
    <div className="app-layout">
      <aside className="desktop-sidebar">
        <Link href="/tasks" className="app-brand">
          <AppMark />
          <span>AppDNA</span>
        </Link>
        {nav}
        <div className="sidebar-strand" aria-hidden="true">
          <span />
          <span />
          <span />
          <span />
          <span />
        </div>
        <div className="sidebar-secondary">
          <Button variant="ghost" size="sm" asChild>
            <Link href="/explore">
              <Monitor />
              Native app explorer
            </Link>
          </Button>
        </div>
      </aside>
      <div className="main-layout">
        <header className="app-header">
          <div className="header-location">
            <Button
              variant="ghost"
              size="icon"
              aria-label="Open navigation"
              className="mobile-menu"
              onClick={() => setMenuOpen(true)}
            >
              <Menu />
            </Button>
            <Link href={selected}>{label}</Link>
            {detail ? (
              <>
                <ChevronRight className="size-3.5 shrink-0" />
                <span className="breadcrumb-detail">{detail}</span>
              </>
            ) : null}
          </div>
          {connections &&
          !connections.ready &&
          selected !== "/settings" &&
          !detail ? (
            <Button variant="outline" asChild className="header-connect">
              <Link href="/settings">
                <Cable />
                Set up connections
              </Link>
            </Button>
          ) : null}
        </header>
        {children}
      </div>
      <Sheet open={menuOpen} onOpenChange={setMenuOpen}>
        <SheetContent side="left" className="w-[280px]">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <AppMark />
              AppDNA
            </SheetTitle>
            <SheetDescription className="sr-only">
              Navigate between tasks, saved skills and connections.
            </SheetDescription>
          </SheetHeader>
          {nav}
        </SheetContent>
      </Sheet>
    </div>
  );
}

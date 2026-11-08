import Link from "next/link";

export function WorkspaceHeader({ context = "Review workspace" }: { context?: string }) {
  return (
    <header className="workspace-header">
      <Link href="/" aria-label="AppDNA workspace" className="workspace-brand">
        <svg width="28" height="28" viewBox="0 0 28 28" fill="none" aria-hidden="true">
          <path d="M7 5v18M14 9v10M21 5v18M7 9l14 10M7 19L21 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <span>AppDNA</span>
      </Link>
      <span className="workspace-divider" aria-hidden="true" />
      <p className="min-w-0 truncate text-sm text-ink/65">{context}</p>
      <nav className="ml-auto flex items-center gap-4" aria-label="Workspace navigation">
        <Link href="/learning" className="showcase-nav" aria-current={context === "Learning Showcase" ? "page" : undefined}>Learning Showcase</Link>
        <p className="hidden text-xs tracking-wide text-ink/60 lg:block">Evidence before commitment.</p>
      </nav>
    </header>
  );
}

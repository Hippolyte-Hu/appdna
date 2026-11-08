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
      <nav className="ml-auto flex gap-4 text-xs text-ink/70" aria-label="Workspace">
        <a href="/video/">Video learning</a>
        <Link href="/assessments">Projects & skills</Link>
      </nav>
    </header>
  );
}

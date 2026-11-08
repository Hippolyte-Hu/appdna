import Link from "next/link";

export default function ExplorerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="legacy-view">
      <Link href="/tasks" className="legacy-back">
        ← AppDNA tasks
      </Link>
      {children}
    </div>
  );
}

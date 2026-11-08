import { TaskWorkspace } from "@/components/task-workspace";

export default async function ResultsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <TaskWorkspace id={id} results />;
}

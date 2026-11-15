import { CheckCircle2 } from "lucide-react";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { CodeBlock } from "@/components/ui/code-block";
import { EmptyState } from "@/components/ui/empty-state";
import { useJobErrors } from "../../api/jobs";

export function ErrorsTab({ runId }: { runId: string }) {
  const errors = useJobErrors(runId);
  return (
    <QueryBoundary query={errors} errorTitle="Couldn't load errors">
      {(data) => {
        const tasks = Object.entries(data.tasks);
        if (!data.run && tasks.length === 0) {
          return <EmptyState icon={<CheckCircle2 className="size-6" aria-hidden />} title="No errors" description="Valkyrie has not reported any run or task errors." />;
        }
        return (
          <div className="space-y-6">
            {data.run ? (
              <section className="space-y-2">
                <h3 className="text-[13px] font-medium text-danger">Run error</h3>
                <CodeBlock code={data.run} wrap />
              </section>
            ) : null}
            {tasks.map(([task, message]) => (
              <section key={task} className="space-y-2">
                <h3 className="font-mono text-[13px] font-medium">{task}</h3>
                <CodeBlock code={message} wrap />
              </section>
            ))}
          </div>
        );
      }}
    </QueryBoundary>
  );
}

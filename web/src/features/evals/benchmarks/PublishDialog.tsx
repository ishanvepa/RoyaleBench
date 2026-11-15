import { useState } from "react";
import { toast } from "sonner";
import { ApiError, fieldErrors } from "@/api/client";
import type { BenchmarkDetail } from "@/api/types";
import { Banner } from "@/components/ui/banner";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogFooter } from "@/components/ui/dialog";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { plural } from "@/lib/format";
import { usePublishBenchmark } from "../api/benchmarks";

const parseTags = (text: string) => text.split(/[\s,]+/).filter(Boolean);

interface ProblemDetail {
  task?: string;
  problems?: string[];
}

export function PublishDialog({ detail, open, onOpenChange }: { detail: BenchmarkDetail; open: boolean; onOpenChange: (open: boolean) => void }) {
  const name = detail.benchmark.name;
  const publish = usePublishBenchmark(name);
  const [tags, setTags] = useState("");
  const [allowProblems, setAllowProblems] = useState(false);

  const changed = detail.tasks.filter((t) => t.local && (t.sync === "modified" || t.sync === "not published")).length;
  const withProblems = detail.tasks.filter((t) => t.problems.length > 0);
  const error = publish.error instanceof ApiError ? publish.error : null;
  const problemDetail = error?.code === "has_problems" && Array.isArray(error.detail) ? (error.detail as ProblemDetail[]) : null;
  const tagError = error?.code === "validation_error" ? (fieldErrors(error).tags ?? error.message) : undefined;
  const needsOverride = withProblems.length > 0 || problemDetail !== null;

  function submit() {
    publish.mutate(
      { tags: parseTags(tags), allow_problems: allowProblems },
      {
        onSuccess: (result) => {
          toast.success(
            result.changed ? `Published ${detail.dataset_ref} as revision ${result.version.revision}` : `Nothing changed: revision ${result.version.revision} is already up to date`,
          );
          onOpenChange(false);
        },
      },
    );
  }

  return (
    <Dialog open={open} onOpenChange={(next) => (publish.isPending ? undefined : onOpenChange(next))}>
      <DialogContent
        title={`Publish ${detail.benchmark.title}`}
        description={`Uploads the local folder to Valkyrie as a new immutable version of ${detail.dataset_ref}. Unchanged tasks are not uploaded again.`}
      >
        <div className="space-y-4">
          <p className="text-[13px] text-subtle">
            {changed > 0 ? `${plural(changed, "task")} changed or new since the last published version.` : "Nothing has changed since the latest published version, so this will not create a new revision."}
          </p>
          <Field label="Tags (optional)" error={tagError} hint="For example v2. Separate several with commas. Tags cannot be only digits, and “latest” is automatic.">
            {(c) => (
              <Input id={c.id} value={tags} placeholder="v2" onChange={(e) => setTags(e.target.value)} aria-invalid={c.invalid} aria-describedby={c.describedBy} />
            )}
          </Field>
          {needsOverride ? (
            <Banner tone="warning" title="Some tasks have problems">
              <ul className="mt-1 list-disc space-y-1 pl-4">
                {(problemDetail
                  ? problemDetail.map((p) => ({ id: p.task || "benchmark", problems: p.problems ?? [] }))
                  : withProblems.map((t) => ({ id: t.id, problems: t.problems }))
                ).map((p) => (
                  <li key={p.id}>
                    <span className="font-mono">{p.id}</span>: {p.problems.join("; ")}
                  </li>
                ))}
              </ul>
              <label className="mt-3 flex items-start gap-2.5">
                <Checkbox checked={allowProblems} onCheckedChange={(v) => setAllowProblems(v === true)} className="mt-0.5" />
                <span>Publish anyway</span>
              </label>
            </Banner>
          ) : null}
          {error && !tagError && error.code !== "has_problems" ? (
            <Banner tone="danger" title="Couldn't publish">
              {error.message}
            </Banner>
          ) : null}
        </div>
        <DialogFooter>
          <Button variant="secondary" onClick={() => onOpenChange(false)} disabled={publish.isPending}>
            Cancel
          </Button>
          <Button variant="primary" onClick={submit} loading={publish.isPending} disabled={needsOverride && !allowProblems}>
            Publish
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

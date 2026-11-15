import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect, useMemo, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { z } from "zod";
import { ApiError } from "@/api/client";
import type { BenchmarkRow, Environment, JobSpecIn } from "@/api/types";
import { QueryBoundary } from "@/components/domain/QueryBoundary";
import { Banner } from "@/components/ui/banner";
import { Breadcrumbs } from "@/components/ui/breadcrumbs";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { CodeBlock } from "@/components/ui/code-block";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Select } from "@/components/ui/select";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { harnessName, plural } from "@/lib/format";
import { useBenchmark, useBenchmarks } from "../api/benchmarks";
import { useEnvironment } from "../api/environment";
import { useJobPreview, useStartJob } from "../api/jobs";
import { useCanStart } from "../useCanStart";
import { CUSTOM_MODEL, defaultLabel, defaultSecret, providerOf } from "./defaults";
import { TaskChecklist } from "./TaskChecklist";

function makeSchema(maxConcurrency: number) {
  return z
    .object({
      dataset: z.string().min(1, "Choose a benchmark"),
      revision: z.string().min(1, "Choose a revision"),
      scope: z.enum(["all", "subset"]),
      taskIds: z.array(z.string()),
      agent: z.string().min(1, "Choose a harness"),
      modelChoice: z.string().min(1, "Choose a model"),
      customModel: z.string(),
      secretName: z.string().min(1, "Choose the Valkyrie secret that holds the API key"),
      concurrency: z
        .number({ error: "Enter a whole number" })
        .int("Enter a whole number")
        .min(1, "At least 1")
        .max(maxConcurrency, `At most ${maxConcurrency}`),
      label: z.string().trim().min(1, "Give the job a name").max(120, "At most 120 characters"),
    })
    .superRefine((v, ctx) => {
      if (v.modelChoice === CUSTOM_MODEL && !/^[^/\s]+\/[^/\s]+$/.test(v.customModel.trim())) {
        ctx.addIssue({ code: "custom", path: ["customModel"], message: "Use a Valkyrie model key such as anthropic/claude-sonnet-4-6" });
      }
      if (v.scope === "subset" && v.taskIds.length === 0) {
        ctx.addIssue({ code: "custom", path: ["taskIds"], message: "Select at least one task, or run the whole benchmark" });
      }
    });
}

type FormValues = z.infer<ReturnType<typeof makeSchema>>;

const modelOf = (v: Pick<FormValues, "modelChoice" | "customModel">) => (v.modelChoice === CUSTOM_MODEL ? v.customModel.trim() : v.modelChoice);

export function Component() {
  const env = useEnvironment();
  const benchmarks = useBenchmarks();
  return (
    <div>
      <Breadcrumbs items={[{ label: "Jobs", to: "/evals/jobs" }, { label: "New job" }]} />
      <PageHeader title="New job" description="Run one model on a benchmark, or a handful of its tasks, through Valkyrie. Sandboxes run on Modal." />
      <QueryBoundary query={env} errorTitle="Couldn't load the Valkyrie connection">
        {(environment) => (
          <QueryBoundary query={benchmarks} errorTitle="Couldn't load benchmarks">
            {(list) => <NewJobForm environment={environment} benchmarks={list.benchmarks} />}
          </QueryBoundary>
        )}
      </QueryBoundary>
    </div>
  );
}

function NewJobForm({ environment, benchmarks }: { environment: Environment; benchmarks: BenchmarkRow[] }) {
  const navigate = useNavigate();
  const [search] = useSearchParams();
  const canStart = useCanStart();
  const startJob = useStartJob();
  const settings = environment.settings;

  const published = benchmarks.filter((b) => b.versions > 0);
  const requested = search.get("benchmark");
  const initialDataset =
    published.find((b) => b.name === requested)?.name ?? published.find((b) => b.kind !== "smoke")?.name ?? published[0]?.name ?? "";
  const initialModel = settings.models[0]?.id ?? CUSTOM_MODEL;
  const initialAgent = environment.agents.includes(settings.default_agent) ? settings.default_agent : (environment.agents[0] ?? "");

  const schema = useMemo(() => makeSchema(settings.max_concurrency), [settings.max_concurrency]);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    mode: "onChange",
    defaultValues: {
      dataset: initialDataset,
      revision: "latest",
      scope: "all",
      taskIds: [],
      agent: initialAgent,
      modelChoice: initialModel,
      customModel: "",
      secretName: defaultSecret(environment.secrets, providerOf(initialModel), environment.identity),
      concurrency: Math.min(settings.default_concurrency, settings.max_concurrency),
      label: defaultLabel(initialDataset, initialModel),
    },
  });
  const { control, register, setValue, trigger, watch, formState } = form;
  // Read validity unconditionally: react-hook-form only tracks it once it has been read in a render, and a read hidden
  // behind a short-circuit would leave a form the user never touched permanently "invalid".
  const { errors, isValid } = formState;
  const values = watch();
  const model = modelOf(values);

  // Defaults that follow the user's choices until they type their own value.
  const [labelTouched, setLabelTouched] = useState(false);
  const [secretTouched, setSecretTouched] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  const benchmark = useBenchmark(values.dataset || "_");
  const revisions = benchmark.data?.versions ?? [];

  const body: JobSpecIn = {
    dataset: values.dataset,
    revision: values.revision,
    agent: values.agent,
    model,
    secret_name: values.secretName,
    concurrency: Number.isFinite(values.concurrency) ? values.concurrency : 1,
    label: values.label,
    task_ids: values.scope === "all" ? null : values.taskIds,
    confirm: false,
  };
  // Compare by value: a fresh object every render would restart the debounce forever.
  const bodyKey = JSON.stringify(body);
  const debouncedKey = useDebouncedValue(bodyKey, 300);
  const debouncedBody = useMemo(() => JSON.parse(debouncedKey) as JobSpecIn, [debouncedKey]);
  const preview = useJobPreview(debouncedBody, debouncedBody.dataset !== "");
  const result = preview.data;
  const settled = bodyKey === debouncedKey && !preview.isFetching && !preview.isPlaceholderData;

  const knownTasks = useMemo(() => result?.known_tasks ?? [], [result?.known_tasks]);
  useEffect(() => {
    // Switching revision can drop tasks; never submit one the revision does not have.
    if (knownTasks.length === 0) return;
    const kept = values.taskIds.filter((t) => knownTasks.includes(t));
    if (kept.length !== values.taskIds.length) setValue("taskIds", kept, { shouldValidate: true });
  }, [knownTasks, values.taskIds, setValue]);

  function onDatasetChange(dataset: string) {
    setValue("dataset", dataset, { shouldValidate: true });
    setValue("revision", "latest");
    setValue("taskIds", []);
    setValue("scope", "all");
    setConfirmed(false);
    if (!labelTouched) setValue("label", defaultLabel(dataset, model));
  }

  function onModelChange(choice: string, custom: string) {
    const next = choice === CUSTOM_MODEL ? custom.trim() : choice;
    if (!secretTouched) setValue("secretName", defaultSecret(environment.secrets, providerOf(next), environment.identity), { shouldValidate: true });
    if (!labelTouched) setValue("label", defaultLabel(values.dataset, next));
  }

  const needsConfirm = Boolean(result?.needs_confirmation);
  const startError = startJob.error instanceof ApiError ? startJob.error : null;
  const ready = canStart.allowed && settled && Boolean(result?.valid) && isValid && (!needsConfirm || confirmed);

  function submit() {
    startJob.mutate(
      { ...body, confirm: confirmed },
      {
        onSuccess: (started) => {
          toast.success(`Job started: ${plural(started.task_count, "task")} on Modal`);
          void navigate(`/evals/jobs/${started.run_id}`);
        },
      },
    );
  }

  const secretOptions = environment.secrets.filter((s) => !/modal/i.test(s));

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (ready) submit();
      }}
      className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_400px]"
      noValidate
    >
      <div className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>What to run</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {published.length === 0 ? (
              <Banner tone="warning" title="No published benchmarks">
                Jobs run published dataset versions. Publish a benchmark from the{" "}
                <Link className="underline" to="/evals/benchmarks">
                  Benchmarks page
                </Link>{" "}
                first.
              </Banner>
            ) : null}
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Benchmark" error={errors.dataset?.message} hint="Only published benchmarks can run.">
                {(c) => (
                  <Select
                    id={c.id}
                    value={values.dataset}
                    onValueChange={onDatasetChange}
                    aria-describedby={c.describedBy}
                    aria-invalid={c.invalid}
                    placeholder="Choose a benchmark"
                    options={benchmarks.map((b) => ({
                      value: b.name,
                      label: b.title,
                      disabled: b.versions === 0,
                      hint: b.versions === 0 ? "Publish it first" : `${plural(b.task_count, "task")} · r${b.latest_revision ?? "?"}`,
                    }))}
                  />
                )}
              </Field>
              <Field label="Revision" hint="Jobs pin an exact published revision, so results stay comparable.">
                {(c) => (
                  <Select
                    id={c.id}
                    value={values.revision}
                    onValueChange={(v) => setValue("revision", v, { shouldValidate: true })}
                    options={[
                      { value: "latest", label: "Latest", hint: revisions[0] ? `currently r${revisions[0].revision}` : undefined },
                      ...revisions.map((v) => ({
                        value: String(v.revision),
                        label: `r${v.revision}`,
                        hint: `${plural(v.task_count, "task")}${v.tags.length ? ` · ${v.tags.join(", ")}` : ""}`,
                      })),
                    ]}
                  />
                )}
              </Field>
            </div>
            <div className="space-y-2">
              <span id="scope-label" className="text-[13px] font-medium text-subtle">
                Tasks
              </span>
              <div>
                <SegmentedControl
                  aria-label="Which tasks to run"
                  value={values.scope}
                  onValueChange={(scope) => {
                    setValue("scope", scope, { shouldValidate: true });
                    // The "pick at least one task" rule belongs to the task list, so check it now rather than on the first click.
                    void trigger("taskIds");
                  }}
                  options={[
                    { value: "all", label: knownTasks.length ? `Whole benchmark (${knownTasks.length})` : "Whole benchmark" },
                    { value: "subset", label: "Select tasks" },
                  ]}
                />
              </div>
              {values.scope === "subset" ? (
                <>
                  <TaskChecklist tasks={knownTasks} selected={values.taskIds} onChange={(ids) => setValue("taskIds", ids, { shouldValidate: true })} />
                  {errors.taskIds?.message ? (
                    <p role="alert" className="text-xs text-danger">
                      {errors.taskIds.message}
                    </p>
                  ) : null}
                </>
              ) : null}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Who runs it</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Harness" error={errors.agent?.message} hint="The agent that drives the model inside the sandbox.">
                {(c) => (
                  <Controller
                    control={control}
                    name="agent"
                    render={({ field }) => (
                      <Select
                        id={c.id}
                        value={field.value}
                        onValueChange={field.onChange}
                        aria-invalid={c.invalid}
                        options={environment.agents.map((a) => ({ value: a, label: harnessName(a), hint: a }))}
                        placeholder="Choose a harness"
                      />
                    )}
                  />
                )}
              </Field>
              <Field label="Model" error={errors.modelChoice?.message}>
                {(c) => (
                  <Select
                    id={c.id}
                    value={values.modelChoice}
                    onValueChange={(choice) => {
                      setValue("modelChoice", choice, { shouldValidate: true });
                      onModelChange(choice, values.customModel);
                    }}
                    options={[
                      ...settings.models.map((m) => ({ value: m.id, label: m.id })),
                      { value: CUSTOM_MODEL, label: "Other model key…" },
                    ]}
                  />
                )}
              </Field>
            </div>
            {values.modelChoice === CUSTOM_MODEL ? (
              <Field label="Model key" error={errors.customModel?.message} hint="Exactly as Valkyrie expects it. Unverified models should start with a one-task job.">
                {(c) => (
                  <Input
                    id={c.id}
                    placeholder="provider/model-name"
                    aria-invalid={c.invalid}
                    aria-describedby={c.describedBy}
                    {...register("customModel", { onChange: (e) => onModelChange(CUSTOM_MODEL, e.target.value) })}
                  />
                )}
              </Field>
            ) : null}
            <Field
              label="API key secret"
              error={errors.secretName?.message}
              hint="A Valkyrie secret shared by your organization. Model usage is charged to the account that owns the key."
            >
              {(c) => (
                <Select
                  id={c.id}
                  value={values.secretName}
                  onValueChange={(v) => {
                    setSecretTouched(true);
                    setValue("secretName", v, { shouldValidate: true });
                  }}
                  aria-invalid={c.invalid}
                  placeholder={secretOptions.length ? "Choose a secret" : "No secrets stored in Valkyrie"}
                  options={secretOptions.map((s) => ({ value: s, label: s }))}
                />
              )}
            </Field>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>How it runs</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 sm:grid-cols-2">
            <Field label="Concurrency" error={errors.concurrency?.message} hint={`Tasks running at once (1 to ${settings.max_concurrency}). Start small.`}>
              {(c) => (
                <Input
                  id={c.id}
                  type="number"
                  min={1}
                  max={settings.max_concurrency}
                  inputMode="numeric"
                  aria-invalid={c.invalid}
                  aria-describedby={c.describedBy}
                  {...register("concurrency", { valueAsNumber: true })}
                />
              )}
            </Field>
            <Field label="Sandbox provider" hint="Every job runs its sandboxes on Modal.">
              {(c) => <Input id={c.id} value="Modal" readOnly disabled />}
            </Field>
            <Field label="Job name" error={errors.label?.message} className="sm:col-span-2" hint="Shown in the jobs list. Sent to Valkyrie as the run label.">
              {(c) => (
                <Input
                  id={c.id}
                  aria-invalid={c.invalid}
                  aria-describedby={c.describedBy}
                  {...register("label", { onChange: () => setLabelTouched(true) })}
                />
              )}
            </Field>
          </CardContent>
        </Card>
      </div>

      <aside className="lg:sticky lg:top-6" aria-label="Review">
        <Card>
          <CardHeader>
            <CardTitle>Review</CardTitle>
            <span className="text-xs text-muted" aria-live="polite">
              {!settled ? "Checking…" : result?.valid ? "Ready" : "Needs attention"}
            </span>
          </CardHeader>
          <CardContent className="space-y-4">
            {result ? (
              <>
                <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-1.5 text-[13px]">
                  <dt className="text-muted">Benchmark</dt>
                  <dd>{result.dataset_ref ?? "–"}</dd>
                  <dt className="text-muted">Tasks</dt>
                  <dd>{result.task_count ? plural(result.task_count, "task") : "–"}</dd>
                  <dt className="text-muted">Harness</dt>
                  <dd>{harnessName(values.agent) || "–"}</dd>
                  <dt className="text-muted">Model</dt>
                  <dd className="break-all">{model || "–"}</dd>
                  <dt className="text-muted">Key</dt>
                  <dd className="break-all">{values.secretName ? `${values.secretName} → ${result.secret_env ?? "?"}` : "–"}</dd>
                  <dt className="text-muted">Concurrency</dt>
                  <dd>{values.concurrency || "–"}</dd>
                  <dt className="text-muted">Sandboxes</dt>
                  <dd>Modal</dd>
                </dl>
                {result.errors.length > 0 ? (
                  <ul role="alert" className="list-disc space-y-1 pl-4 text-[13px] text-danger">
                    {result.errors.map((e) => (
                      <li key={e}>{e}</li>
                    ))}
                  </ul>
                ) : null}
                {result.warnings.length > 0 ? (
                  <ul className="list-disc space-y-1 pl-4 text-[13px] text-warning">
                    {result.warnings.map((w) => (
                      <li key={w}>{w}</li>
                    ))}
                  </ul>
                ) : null}
                {result.cli_command ? <CodeBlock label="Equivalent command" code={result.cli_command} wrap /> : null}
                {needsConfirm ? (
                  <label className="flex items-start gap-2.5 rounded-lg border border-warning/30 bg-warning/10 p-3 text-[13px]">
                    <Checkbox checked={confirmed} onCheckedChange={(v) => setConfirmed(v === true)} className="mt-0.5" />
                    <span>
                      This runs <strong>{plural(result.task_count, "task")}</strong>, more than {settings.confirm_over_tasks}. It uses model API credits and Modal compute. I want to run it.
                    </span>
                  </label>
                ) : null}
              </>
            ) : preview.isError ? (
              <p role="alert" className="text-[13px] text-danger">
                {preview.error.message}
              </p>
            ) : (
              <p className="text-[13px] text-muted">Choose a benchmark to see what this job will do.</p>
            )}
            {startError && startError.code !== "confirmation_required" ? (
              <Banner tone="danger" title="Couldn't start the job">
                {startError.message}
              </Banner>
            ) : null}
            {!canStart.allowed && !canStart.loading ? (
              <Banner tone="warning" title="Starting is unavailable">
                {canStart.reason}
              </Banner>
            ) : null}
            <div className="flex gap-2 pt-1">
              <Button type="submit" variant="primary" className="flex-1" disabled={!ready} loading={startJob.isPending}>
                Start job
              </Button>
              <Button asChild variant="secondary">
                <Link to="/evals/jobs">Cancel</Link>
              </Button>
            </div>
          </CardContent>
        </Card>
      </aside>
    </form>
  );
}

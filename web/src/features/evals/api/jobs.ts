import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api, unwrap } from "@/api/client";
import { qk } from "@/api/queryKeys";
import { isActiveRun, type JobSpecIn } from "@/api/types";

export interface JobFilters {
  status: string[];
  dataset: string;
  model: string;
  mine: boolean;
}

const POLL_ACTIVE_MS = 3_000;

export function useJobs(filters: JobFilters) {
  return useQuery({
    queryKey: qk.evals.jobs(filters),
    queryFn: () =>
      unwrap(
        api.GET("/api/evals/jobs", {
          params: {
            query: {
              status: filters.status.length ? filters.status : undefined,
              dataset: filters.dataset || undefined,
              model: filters.model || undefined,
              mine: filters.mine || undefined,
            },
          },
        }),
      ),
    // Quick while anything is running, lazy otherwise. Background tabs do not poll at all.
    refetchInterval: (query) => (query.state.data?.jobs.some((j) => isActiveRun(j.status)) ? 5_000 : 30_000),
  });
}

export function useJob(runId: string) {
  return useQuery({
    queryKey: qk.evals.job(runId),
    queryFn: () => unwrap(api.GET("/api/evals/jobs/{run_id}", { params: { path: { run_id: runId } } })),
    refetchInterval: (query) => (query.state.data?.active ? POLL_ACTIVE_MS : false),
  });
}

const TERMINAL_TASK_STATUSES = ["FINISHED", "ERROR", "STOPPED"];

/**
 * Keeps polling while the run is active, and also until the table itself shows every task in a final state:
 * the run can flip to "finished" a moment before the last task poll lands, which would otherwise freeze the
 * table on a task that is still "running".
 */
export function useJobTasks(runId: string, active: boolean) {
  return useQuery({
    queryKey: qk.evals.jobTasks(runId),
    queryFn: () => unwrap(api.GET("/api/evals/jobs/{run_id}/tasks", { params: { path: { run_id: runId } } })),
    refetchInterval: (query) =>
      active || query.state.data?.tasks.some((t) => !TERMINAL_TASK_STATUSES.includes(t.status)) ? POLL_ACTIVE_MS : false,
  });
}

export function useTaskDetail(runId: string, taskId: string | null) {
  return useQuery({
    queryKey: qk.evals.jobTask(runId, taskId ?? ""),
    queryFn: () =>
      unwrap(api.GET("/api/evals/jobs/{run_id}/tasks/{task_id}", { params: { path: { run_id: runId, task_id: taskId ?? "" } } })),
    enabled: taskId !== null,
  });
}

/** Loaded on demand: the first request downloads the agent's output from Valkyrie. */
export function useTaskTrace(runId: string, taskId: string | null, enabled: boolean) {
  return useQuery({
    queryKey: qk.evals.jobTrace(runId, taskId ?? ""),
    queryFn: () =>
      unwrap(api.GET("/api/evals/jobs/{run_id}/tasks/{task_id}/trace", { params: { path: { run_id: runId, task_id: taskId ?? "" } } })),
    enabled: enabled && taskId !== null,
    staleTime: 60_000,
  });
}

export interface LogParams {
  taskId: string;
  q: string;
}

export function useJobLogs(runId: string, params: LogParams, live: boolean) {
  return useQuery({
    queryKey: qk.evals.jobLogs(runId, params),
    queryFn: () =>
      unwrap(
        api.GET("/api/evals/jobs/{run_id}/logs", {
          params: { path: { run_id: runId }, query: { task_id: params.taskId || undefined, q: params.q || undefined, limit: 500 } },
        }),
      ),
    refetchInterval: live ? 5_000 : false,
    placeholderData: keepPreviousData,
  });
}

export function useJobErrors(runId: string) {
  return useQuery({
    queryKey: qk.evals.jobErrors(runId),
    queryFn: () => unwrap(api.GET("/api/evals/jobs/{run_id}/errors", { params: { path: { run_id: runId } } })),
  });
}

/** Validate the form against Valkyrie as it is filled in. A POST, but read-only on the server. */
export function useJobPreview(body: JobSpecIn, enabled: boolean) {
  return useQuery({
    queryKey: qk.evals.preview(body),
    queryFn: () => unwrap(api.POST("/api/evals/jobs/preview", { body })),
    enabled,
    placeholderData: keepPreviousData,
    staleTime: 10_000,
    retry: false,
  });
}

export function useStartJob() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: JobSpecIn) => unwrap(api.POST("/api/evals/jobs", { body })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.evals.jobsAll() }),
  });
}

export type JobAction = "stop" | "resume" | "retry";

const ACTION_LABEL: Record<JobAction, string> = { stop: "Stopping the job", resume: "Resuming the job", retry: "Retrying failed tasks" };

/** Stop, resume or retry a run. Refreshes the run and its tasks, and says what happened. */
export function useJobAction(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ action, force }: { action: JobAction; force?: boolean }) => {
      const path = { run_id: runId };
      if (action === "stop") return unwrap(api.POST("/api/evals/jobs/{run_id}/stop", { params: { path, query: { force: force ?? false } } }));
      if (action === "resume") return unwrap(api.POST("/api/evals/jobs/{run_id}/resume", { params: { path } }));
      return unwrap(api.POST("/api/evals/jobs/{run_id}/retry", { params: { path } }));
    },
    onSuccess: (_data, { action }) => {
      toast.success(ACTION_LABEL[action]);
      void queryClient.invalidateQueries({ queryKey: qk.evals.job(runId) });
      void queryClient.invalidateQueries({ queryKey: qk.evals.jobsAll() });
    },
    onError: (error) => toast.error(error.message),
  });
}

export function useSetConcurrency(runId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (concurrency: number) =>
      unwrap(api.PATCH("/api/evals/jobs/{run_id}", { params: { path: { run_id: runId } }, body: { concurrency } })),
    onSuccess: ({ concurrency }) => {
      toast.success(`Concurrency set to ${concurrency}`);
      void queryClient.invalidateQueries({ queryKey: qk.evals.job(runId) });
    },
    onError: (error) => toast.error(error.message),
  });
}

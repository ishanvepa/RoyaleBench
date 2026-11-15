import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import { qk } from "@/api/queryKeys";

export function useBenchmarks() {
  return useQuery({
    queryKey: qk.evals.benchmarks(),
    queryFn: () => unwrap(api.GET("/api/evals/benchmarks")),
    staleTime: 15_000,
  });
}

export function useBenchmark(name: string) {
  return useQuery({
    queryKey: qk.evals.benchmark(name),
    queryFn: () => unwrap(api.GET("/api/evals/benchmarks/{name}", { params: { path: { name } } })),
    staleTime: 15_000,
  });
}

export function useTaskRanking(name: string) {
  return useQuery({
    queryKey: qk.evals.taskRanking(name),
    queryFn: () => unwrap(api.GET("/api/evals/benchmarks/{name}/ranking", { params: { path: { name } } })),
    staleTime: 10_000,
    refetchInterval: 30_000,
  });
}

export function useBenchmarkTask(name: string, taskId: string) {
  return useQuery({
    queryKey: qk.evals.benchmarkTask(name, taskId),
    queryFn: () =>
      unwrap(api.GET("/api/evals/benchmarks/{name}/tasks/{task_id}", { params: { path: { name, task_id: taskId } } })),
  });
}

export function useTaskResolution(name: string, taskId: string) {
  return useQuery({
    queryKey: qk.evals.taskResolution(name, taskId),
    queryFn: () =>
      unwrap(api.GET("/api/evals/benchmarks/{name}/tasks/{task_id}/resolution", { params: { path: { name, task_id: taskId } } })),
  });
}

export function useTaskResults(name: string, taskId: string) {
  return useQuery({
    queryKey: qk.evals.taskResults(name, taskId),
    queryFn: () =>
      unwrap(api.GET("/api/evals/benchmarks/{name}/tasks/{task_id}/results", { params: { path: { name, task_id: taskId } } })),
    staleTime: 15_000,
  });
}

export function usePublishBenchmark(name: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { tags: string[]; allow_problems: boolean }) =>
      unwrap(api.POST("/api/evals/benchmarks/{name}/publish", { params: { path: { name } }, body })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: qk.evals.benchmarks() });
      void queryClient.invalidateQueries({ queryKey: qk.evals.benchmark(name) });
    },
  });
}

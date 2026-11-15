import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { api, unwrap } from "@/api/client";
import { qk } from "@/api/queryKeys";

export function useModels() {
  return useQuery({ queryKey: qk.legacy.models(), queryFn: () => unwrap(api.GET("/api/legacy/models")), staleTime: 15_000 });
}

/** Status of the background model check; polls while it runs and refreshes the table when it ends. */
export function useModelCheck() {
  const queryClient = useQueryClient();
  const status = useQuery({
    queryKey: qk.legacy.modelCheck(),
    queryFn: () => unwrap(api.GET("/api/legacy/models/check")),
    refetchInterval: (query) => (query.state.data?.state === "running" ? 1_500 : false),
  });
  const start = useMutation({
    mutationFn: () => unwrap(api.POST("/api/legacy/models/check")),
    onSuccess: (data) => queryClient.setQueryData(qk.legacy.modelCheck(), data),
    onError: (error) => toast.error(error.message),
  });

  // When a check finishes, the table's "last check" column has new values: fetch them now rather than at the next refresh.
  const state = status.data?.state;
  const previous = useRef(state);
  useEffect(() => {
    if (previous.current === "running" && state !== undefined && state !== "running") {
      void queryClient.invalidateQueries({ queryKey: qk.legacy.models() });
    }
    previous.current = state;
  }, [state, queryClient]);

  return { status: status.data, start };
}

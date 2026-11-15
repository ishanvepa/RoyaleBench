import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import { qk } from "@/api/queryKeys";
import type { BattleRequest, PlayState } from "@/api/types";

export function usePlayOptions() {
  return useQuery({ queryKey: qk.legacy.playOptions(), queryFn: () => unwrap(api.GET("/api/legacy/play/options")), staleTime: 60_000 });
}

export interface StartGameInput {
  opponent: string;
  deck: string;
  opponent_deck: string | null;
  seed: number;
  ticks: number;
}

/** The game lives on the server; the query cache holds its latest board, and a reload restores it from the id in the URL. */
export function useGame(id: string) {
  return useQuery({
    queryKey: qk.legacy.game(id),
    queryFn: () => unwrap(api.GET("/api/legacy/play/games/{game_id}", { params: { path: { game_id: id } } })),
    enabled: id !== "",
    staleTime: Infinity,
    retry: false,
  });
}

export function useStartGame() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: StartGameInput) => unwrap(api.POST("/api/legacy/play/games", { body })),
    onSuccess: (state) => queryClient.setQueryData(qk.legacy.game(state.id), state),
  });
}

export function usePlayMove(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (index: number) => unwrap(api.POST("/api/legacy/play/games/{game_id}/move", { params: { path: { game_id: id } }, body: { index } })),
    onSuccess: (state: PlayState) => {
      queryClient.setQueryData(qk.legacy.game(id), state);
      if (state.over) void queryClient.invalidateQueries({ queryKey: qk.legacy.all, predicate: (q) => q.queryKey[1] !== "play" });
    },
  });
}

export function useAbandonGame() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/legacy/play/games/{game_id}", { params: { path: { game_id: id } } })),
    onSuccess: (_data, id) => queryClient.removeQueries({ queryKey: qk.legacy.game(id) }),
  });
}

// ------------------------------------------------------------------------------------------------ battles
export function useBattleOptions() {
  return useQuery({ queryKey: qk.legacy.battleOptions(), queryFn: () => unwrap(api.GET("/api/legacy/battles/options")), staleTime: 60_000 });
}

export function useBattlePreview(body: BattleRequest, enabled: boolean) {
  return useQuery({
    queryKey: qk.legacy.battlePreview(body),
    queryFn: () => unwrap(api.POST("/api/legacy/battles/preview", { body })),
    enabled,
    placeholderData: keepPreviousData,
    retry: false,
  });
}

export function useBattles() {
  return useQuery({
    queryKey: qk.legacy.battles(),
    queryFn: () => unwrap(api.GET("/api/legacy/battles")),
    refetchInterval: (query) => (query.state.data?.battles.some((b) => b.state === "running") ? 5_000 : false),
  });
}

export function useBattle(name: string) {
  return useQuery({
    queryKey: qk.legacy.battle(name),
    queryFn: () => unwrap(api.GET("/api/legacy/battles/{name}", { params: { path: { name } } })),
    enabled: name !== "",
    refetchInterval: (query) => (query.state.data?.state === "running" ? 3_000 : false),
  });
}

export function useStartBattle() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: BattleRequest) => unwrap(api.POST("/api/legacy/battles", { body })),
    onSuccess: (status) => {
      queryClient.setQueryData(qk.legacy.battle(status.name), status);
      void queryClient.invalidateQueries({ queryKey: qk.legacy.battles() });
      void queryClient.invalidateQueries({ queryKey: qk.legacy.jobs() });
    },
  });
}

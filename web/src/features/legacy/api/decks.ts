import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import { qk } from "@/api/queryKeys";

export function useDecks() {
  return useQuery({ queryKey: qk.legacy.decks(), queryFn: () => unwrap(api.GET("/api/legacy/decks")), staleTime: 30_000 });
}

export function useSaveDeck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name, cards }: { id: string | null; name: string; cards: string[] }) =>
      id === null
        ? unwrap(api.POST("/api/legacy/decks", { body: { name, cards } }))
        : unwrap(api.PUT("/api/legacy/decks/{deck_id}", { params: { path: { deck_id: id } }, body: { name, cards } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.legacy.decks() }),
  });
}

export function useDeleteDeck() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => unwrap(api.DELETE("/api/legacy/decks/{deck_id}", { params: { path: { deck_id: id } } })),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: qk.legacy.decks() }),
  });
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import { Money } from "@/components/domain/values";
import { Button } from "@/components/ui/button";

const key = ["evals", "modal-billing"];

export function ModalBilling() {
  const client = useQueryClient();
  const billing = useQuery({
    queryKey: key,
    queryFn: () => unwrap(api.GET("/api/evals/modal-billing")),
    refetchInterval: (q) => q.state.data?.syncing ? 2_000 : 30_000,
  });
  const sync = useMutation({
    mutationFn: () => unwrap(api.POST("/api/evals/modal-billing/sync")),
    onSuccess: () => { void client.invalidateQueries({ queryKey: key }); },
  });
  const data = billing.data;
  return (
    <section aria-labelledby="modal-billing" className="space-y-3 rounded-lg border border-line p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 id="modal-billing" className="text-base">Modal endpoint spend</h2>
        <Button variant="secondary" size="sm" disabled={sync.isPending || data?.syncing} onClick={() => sync.mutate()}>
          {data?.syncing ? "Syncing billing…" : "Sync billing"}
        </Button>
      </div>
      <p className="text-[13px] text-subtle">
        Actual metered charges from Modal, before credits and discounts. Includes inference tokens, serving compute and all traffic
        to these Apps; shared endpoint costs are counted once in the total. Includes inference costs also shown in task API spend; do not add the totals together.
      </p>
      {billing.isError || sync.isError ? <p role="alert">Couldn’t reach billing data. Try syncing again.</p> : null}
      {data?.error && <p role="alert" className="text-[13px] text-subtle">{data.error}{data.updated_at && " Last successful data is retained below."}</p>}
      <p className="text-[13px] text-subtle">
        {data?.workspace && `Workspace: ${data.workspace}. `}
        {data?.start && data?.end ? `Report: ${data.start} to ${data.end} (exclusive). ` : "No billing report downloaded yet. "}
        {data?.updated_at && `Last synced: ${data.updated_at}. `}
        Reports include the latest completed UTC hour. Recent charges are provisional; later syncs pick up billing corrections.
      </p>
      <table className="w-full text-left text-[13px]">
        <caption className="sr-only">Modal endpoint costs by model</caption>
        <thead><tr><th className="py-2">Model / App</th><th className="text-right">Metered spend</th></tr></thead>
        <tbody>
          {data?.models.map((model) => (
            <tr key={model.model}>
              <td className="py-2">{model.model}<span className="block text-muted">{model.app}</span>{model.error && <span className="block text-muted">{model.error}</span>}
                {Object.keys(model.cost_by_resource ?? {}).length > 0 && <details className="text-muted">
                  <summary>Resource breakdown</summary>
                  <ul>{Object.entries(model.cost_by_resource).map(([resource, cost]) => <li key={resource}>{resource}: <Money usd={cost} /></li>)}</ul>
                </details>}
              </td>
              <td className="text-right"><Money usd={model.cost_usd} /></td>
            </tr>
          ))}
        </tbody>
        <tfoot><tr><th className="py-2">Endpoint total</th><td className="text-right"><Money usd={data?.cost_usd} /></td></tr></tfoot>
      </table>
    </section>
  );
}

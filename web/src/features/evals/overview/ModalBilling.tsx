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
        <h2 id="modal-billing" className="text-base">Modal endpoint compute</h2>
        <Button variant="secondary" size="sm" disabled={sync.isPending || data?.syncing} onClick={() => sync.mutate()}>
          {data?.syncing ? "Syncing billing…" : "Sync billing"}
        </Button>
      </div>
      <p className="text-[13px] text-subtle">
        Actual metered serving charges from Modal, before credits and discounts. Includes idle compute and all traffic
        to these Apps; shared endpoint costs are counted once in the total. Task API spend is shown separately.
      </p>
      {billing.isError || sync.isError ? <p role="alert">Couldn’t reach billing data. Try syncing again.</p> : null}
      {data?.error && <p role="alert" className="text-[13px] text-subtle">{data.error}{data.updated_at && " Last successful data is retained below."}</p>}
      <p className="text-[13px] text-subtle">
        {data?.workspace && `Workspace: ${data.workspace}. `}
        {data?.start && data?.end ? `Report: ${data.start} to ${data.end} (exclusive). ` : "No billing report downloaded yet. "}
        {data?.updated_at && `Last synced: ${data.updated_at}. `}
        Reports use complete UTC hours with a one-hour delay; later syncs pick up billing corrections.
      </p>
      <table className="w-full text-left text-[13px]">
        <caption className="sr-only">Modal endpoint compute costs by model</caption>
        <thead><tr><th className="py-2">Model / App</th><th className="text-right">Metered compute</th></tr></thead>
        <tbody>
          {data?.models.map((model) => (
            <tr key={model.model}>
              <td className="py-2">{model.model}<span className="block text-muted">{model.app}</span>{model.error && <span className="block text-muted">{model.error}</span>}</td>
              <td className="text-right"><Money usd={model.cost_usd} /></td>
            </tr>
          ))}
        </tbody>
        <tfoot><tr><th className="py-2">Endpoint total</th><td className="text-right"><Money usd={data?.cost_usd} /></td></tr></tfoot>
      </table>
    </section>
  );
}

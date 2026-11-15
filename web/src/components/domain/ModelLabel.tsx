import { cn } from "@/lib/cn";
import { initialOf, modelName } from "@/lib/format";
import { ProviderLogo } from "./ProviderLogo";

interface ModelLabelProps {
  /** The full model key, such as anthropic/claude-sonnet-4-6. */
  model: string;
  /** Provider logo from the API (null for providers without one). */
  logoUrl?: string | null;
  className?: string;
}

/** The provider logo and the model name; the full key is the tooltip. */
export function ModelLabel({ model, logoUrl, className }: ModelLabelProps) {
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-2", className)} title={model}>
      <ProviderLogo logoUrl={logoUrl} fallback={initialOf(modelName(model))} />
      <span className="truncate">{modelName(model) || "–"}</span>
    </span>
  );
}

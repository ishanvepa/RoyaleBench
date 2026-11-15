import { useState } from "react";
import { cn } from "@/lib/cn";
import { modelName } from "@/lib/format";

interface ModelLabelProps {
  /** The full model key, such as anthropic/claude-sonnet-4-6. */
  model: string;
  /** Provider logo from the API (null for providers without one). */
  logoUrl?: string | null;
  className?: string;
}

/** The provider logo on a light tile (logos are dark artwork) and the model name; the full key is the tooltip. */
export function ModelLabel({ model, logoUrl, className }: ModelLabelProps) {
  const [failed, setFailed] = useState(false);
  const initial = (modelName(model).match(/[a-z0-9]/i)?.[0] ?? "?").toUpperCase();
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-2", className)} title={model}>
      <span aria-hidden className="grid size-5 shrink-0 place-items-center overflow-hidden rounded-md bg-white text-[10px] font-semibold text-neutral-700">
        {logoUrl && !failed ? <img src={logoUrl} alt="" width={14} height={14} className="size-3.5 object-contain" onError={() => setFailed(true)} /> : initial}
      </span>
      <span className="truncate">{modelName(model) || "–"}</span>
    </span>
  );
}

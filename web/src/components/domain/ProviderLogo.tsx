import { useState } from "react";
import { cn } from "@/lib/cn";

interface ProviderLogoProps {
  /** Provider logo from the API (null for providers without one). */
  logoUrl?: string | null;
  /** Shown instead when there is no logo, or it fails to load: one letter. */
  fallback: string;
  className?: string;
}

/** A provider logo on a light tile (logos are dark artwork). Decorative: the name beside it is what is read out. */
export function ProviderLogo({ logoUrl, fallback, className }: ProviderLogoProps) {
  const [failed, setFailed] = useState(false);
  return (
    <span aria-hidden className={cn("grid size-5 shrink-0 place-items-center overflow-hidden rounded-md bg-white text-[10px] font-semibold text-neutral-700", className)}>
      {logoUrl && !failed ? <img src={logoUrl} alt="" width={14} height={14} className="size-3.5 object-contain" onError={() => setFailed(true)} /> : fallback}
    </span>
  );
}

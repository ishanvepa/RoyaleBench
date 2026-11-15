import { cn } from "@/lib/cn";
import { familyLabel } from "@/lib/family";
import { initialOf } from "@/lib/format";
import { ProviderLogo } from "./ProviderLogo";

interface FamilyLabelProps {
  /** The family key the API sends, such as "claude" or "gpt". */
  family: string;
  /** Logo for that family from the API (null for families without one). */
  logoUrl?: string | null;
  className?: string;
}

/** A model family's logo and its readable name ("Claude", "GPT"). */
export function FamilyLabel({ family, logoUrl, className }: FamilyLabelProps) {
  const label = familyLabel(family);
  return (
    <span className={cn("inline-flex min-w-0 items-center gap-2", className)}>
      <ProviderLogo logoUrl={logoUrl} fallback={initialOf(label)} />
      <span className="truncate">{label}</span>
    </span>
  );
}

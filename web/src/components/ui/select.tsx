import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface SelectOption {
  value: string;
  label: ReactNode;
  disabled?: boolean;
  /** Secondary text shown under the label in the open list. */
  hint?: string;
}

/** Radix cannot represent "no selection" as an empty string, so filters use this sentinel for "All". */
export const ALL = "__all__";

export interface SelectProps {
  value: string;
  onValueChange: (value: string) => void;
  options: readonly SelectOption[];
  placeholder?: string;
  id?: string;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
}

export function Select({ value, onValueChange, options, placeholder = "Select…", className, ...rest }: SelectProps) {
  return (
    // An empty string is a controlled "nothing chosen" (the placeholder shows). Passing undefined instead would flip Radix
    // between controlled and uncontrolled whenever the value is cleared, and it warns about that.
    <SelectPrimitive.Root value={value} onValueChange={onValueChange} disabled={rest.disabled}>
      <SelectPrimitive.Trigger
        id={rest.id}
        aria-label={rest["aria-label"]}
        aria-describedby={rest["aria-describedby"]}
        aria-invalid={rest["aria-invalid"]}
        className={cn(
          "inline-flex h-9 w-full items-center justify-between gap-2 rounded-md border border-line bg-surface px-3 text-left text-sm text-ink",
          "transition-colors hover:border-focus disabled:cursor-not-allowed disabled:opacity-50 aria-[invalid=true]:border-danger",
          "data-[placeholder]:text-muted",
          className,
        )}
      >
        <span className="truncate">
          <SelectPrimitive.Value placeholder={placeholder} />
        </span>
        <SelectPrimitive.Icon>
          <ChevronDown className="size-4 text-muted" aria-hidden />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={4}
          className="z-50 max-h-80 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-md border border-line bg-surface text-ink shadow-lg"
        >
          <SelectPrimitive.Viewport className="p-1">
            {options.map((o) => (
              <SelectPrimitive.Item
                key={o.value}
                value={o.value}
                disabled={o.disabled}
                className="relative flex cursor-pointer select-none items-center gap-2 rounded px-2 py-1.5 pr-8 text-sm outline-none data-[disabled]:cursor-not-allowed data-[disabled]:opacity-50 data-[highlighted]:bg-selected"
              >
                <span className="flex min-w-0 flex-col">
                  <SelectPrimitive.ItemText>{o.label}</SelectPrimitive.ItemText>
                  {o.hint ? <span className="truncate text-xs text-muted">{o.hint}</span> : null}
                </span>
                <SelectPrimitive.ItemIndicator className="absolute right-2">
                  <Check className="size-4" aria-hidden />
                </SelectPrimitive.ItemIndicator>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}

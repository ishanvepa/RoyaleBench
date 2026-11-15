import { useId, type ReactNode } from "react";
import { cn } from "@/lib/cn";

interface SegmentedControlProps<V extends string> {
  value: V;
  onValueChange: (value: V) => void;
  options: readonly { value: V; label: ReactNode }[];
  "aria-label": string;
  className?: string;
}

/** A small radio group drawn as joined buttons. Arrow keys move between options. */
export function SegmentedControl<V extends string>({ value, onValueChange, options, className, ...rest }: SegmentedControlProps<V>) {
  const name = useId();
  return (
    <div role="radiogroup" aria-label={rest["aria-label"]} className={cn("inline-flex rounded-md border border-line bg-surface p-0.5", className)}>
      {options.map((option) => {
        const checked = option.value === value;
        return (
          <label
            key={option.value}
            className={cn(
              "cursor-pointer rounded px-3 py-1.5 text-[13px] transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-focus",
              checked ? "bg-ink text-background" : "text-subtle hover:text-ink",
            )}
          >
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={checked}
              onChange={() => onValueChange(option.value)}
              className="sr-only"
            />
            {option.label}
          </label>
        );
      })}
    </div>
  );
}

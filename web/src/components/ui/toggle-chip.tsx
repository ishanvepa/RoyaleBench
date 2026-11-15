import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface ToggleChipProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "onChange"> {
  pressed: boolean;
  onPressedChange: (pressed: boolean) => void;
}

/** A filter that is either on or off. Uses aria-pressed, so screen readers announce its state. */
export function ToggleChip({ pressed, onPressedChange, className, children, ...props }: ToggleChipProps) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={() => onPressedChange(!pressed)}
      className={cn(
        "h-8 rounded-full border px-3 text-[13px] transition-colors",
        pressed ? "border-ink bg-ink text-background" : "border-line bg-surface text-subtle hover:border-focus hover:text-ink",
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

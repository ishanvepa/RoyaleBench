import { useId, type ReactNode } from "react";
import { cn } from "@/lib/cn";

interface FieldProps {
  label: ReactNode;
  /** Receives the id to put on the control, and the ids that describe it (hint and error). */
  children: (control: { id: string; describedBy: string | undefined; invalid: boolean }) => ReactNode;
  hint?: ReactNode;
  error?: string | undefined;
  className?: string;
}

/** A label, a control, a hint and an error, wired together for screen readers. */
export function Field({ label, children, hint, error, className }: FieldProps) {
  const id = useId();
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  return (
    <div className={cn("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-[13px] font-medium text-subtle">
        {label}
      </label>
      {children({ id, describedBy, invalid: Boolean(error) })}
      {hint ? (
        <p id={hintId} className="text-xs text-muted">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}

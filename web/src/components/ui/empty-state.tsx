import type { ReactNode } from "react";
import { cn } from "@/lib/cn";

interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, icon, action, className }: EmptyStateProps) {
  return (
    <div className={cn("flex flex-col items-center gap-2 rounded-xl border border-dashed border-line px-6 py-12 text-center", className)}>
      {icon ? <div className="text-muted">{icon}</div> : null}
      <h3 className="text-[15px] font-medium">{title}</h3>
      {description ? <p className="max-w-md text-[13px] text-muted">{description}</p> : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}

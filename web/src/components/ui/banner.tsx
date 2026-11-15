import { AlertTriangle, Info, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import type { Tone } from "./badge";

const STYLES: Record<"info" | "warning" | "danger" | "neutral", string> = {
  info: "border-info/30 bg-info/10",
  warning: "border-warning/30 bg-warning/10",
  danger: "border-danger/30 bg-danger/10",
  neutral: "border-line bg-selected/50",
};

const ICON_COLOR: Record<keyof typeof STYLES, string> = {
  info: "text-info",
  warning: "text-warning",
  danger: "text-danger",
  neutral: "text-muted",
};

export function Banner({
  tone = "info",
  title,
  children,
  className,
}: {
  tone?: Extract<Tone, keyof typeof STYLES>;
  title: string;
  children?: ReactNode;
  className?: string;
}) {
  const Icon = tone === "danger" ? ShieldAlert : tone === "warning" ? AlertTriangle : Info;
  return (
    <div role={tone === "danger" ? "alert" : "status"} className={cn("flex gap-3 rounded-lg border px-4 py-3 text-[13px]", STYLES[tone], className)}>
      <Icon className={cn("mt-0.5 size-4 shrink-0", ICON_COLOR[tone])} aria-hidden />
      <div className="min-w-0">
        <p className="font-medium">{title}</p>
        {children ? <div className="mt-0.5 text-subtle">{children}</div> : null}
      </div>
    </div>
  );
}

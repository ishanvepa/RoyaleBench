import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

export const badgeVariants = cva(
  "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-xs font-medium leading-4",
  {
    variants: {
      tone: {
        neutral: "border-line bg-selected/60 text-subtle",
        success: "border-success/30 bg-success/12 text-success",
        danger: "border-danger/30 bg-danger/12 text-danger",
        warning: "border-warning/30 bg-warning/12 text-warning",
        info: "border-info/30 bg-info/12 text-info",
        outline: "border-line bg-transparent text-subtle",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export type Tone = NonNullable<VariantProps<typeof badgeVariants>["tone"]>;

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}

import { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: "default" | "success" | "warning" | "danger" | "muted";
}

const tones: Record<BadgeProps["tone"], string> = {
  default: "bg-surfaceAlt text-white border border-border",
  success: "bg-success/15 text-success border border-success/40",
  warning: "bg-warning/15 text-warning border border-warning/50",
  danger: "bg-danger/15 text-danger border border-danger/50",
  muted: "bg-surfaceAlt text-muted border border-border",
};

export function Badge({ className, tone = "default", children, ...props }: BadgeProps) {
  return (
    <span
      className={cn("rounded-full px-2 py-0.5 text-[11px] font-medium", tones[tone], className)}
      {...props}
    >
      {children}
    </span>
  );
}

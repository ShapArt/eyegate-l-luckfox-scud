import { LabelHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export function Label({ className, children, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label className={cn("text-[11px] uppercase tracking-[0.12em] text-muted", className)} {...props}>
      {children}
    </label>
  );
}

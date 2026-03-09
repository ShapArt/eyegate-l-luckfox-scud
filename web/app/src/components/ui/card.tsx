import { HTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export function Card({ className, children, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("panel relative overflow-hidden p-5", className)} {...props}>
      {children}
    </div>
  );
}

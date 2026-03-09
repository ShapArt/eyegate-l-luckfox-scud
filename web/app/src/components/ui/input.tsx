import { forwardRef, InputHTMLAttributes } from "react";
import { cn } from "../../lib/utils";

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {}

export const Input = forwardRef<HTMLInputElement, InputProps>(({ className, ...props }, ref) => {
  return (
    <input
      ref={ref}
      className={cn(
        "focus-ring w-full rounded-lg border border-border bg-surfaceAlt px-3 py-2 text-sm text-white placeholder:text-muted outline-none transition",
        "hover:border-accent/60",
        className,
      )}
      {...props}
    />
  );
});

Input.displayName = "Input";

import { ButtonHTMLAttributes, forwardRef } from "react";
import { motion } from "framer-motion";
import { cn } from "../../lib/utils";

type Variant = "primary" | "ghost" | "outline" | "danger" | "subtle";
type Size = "sm" | "md" | "lg";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
}

const variantClasses: Record<Variant, string> = {
  primary:
    "bg-accent text-surface font-semibold shadow-soft hover:bg-[#48c6ee] active:translate-y-[1px]",
  ghost: "text-white hover:text-accent border border-transparent hover:border-border/80",
  outline: "border border-border text-white hover:border-accent hover:text-accent",
  danger: "bg-danger text-surface font-semibold shadow-soft hover:bg-[#ff7f7f] active:translate-y-[1px]",
  subtle: "bg-surfaceAlt text-white border border-border hover:border-accent/60",
};

const sizeClasses: Record<Size, string> = {
  sm: "px-3 py-1.5 text-[12px]",
  md: "px-4 py-2 text-sm",
  lg: "px-5 py-3 text-base",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, children, variant = "primary", size = "md", loading = false, ...props }, ref) => {
    return (
      <motion.button
        whileTap={{ scale: 0.99 }}
        whileHover={{ y: -1 }}
        ref={ref}
        className={cn(
          "focus-ring relative inline-flex items-center justify-center rounded-lg transition-all disabled:opacity-60 disabled:cursor-not-allowed",
          sizeClasses[size],
          variantClasses[variant],
          className,
        )}
        {...props}
      >
        {loading && <span className="mr-2 h-3 w-3 animate-spin rounded-full border border-white/20 border-t-white" />}
        {children}
      </motion.button>
    );
  },
);

Button.displayName = "Button";

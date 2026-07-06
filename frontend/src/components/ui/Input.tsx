import { InputHTMLAttributes, forwardRef } from "react";
import { cn } from "../../lib/utils";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  error?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, className, ...props }, ref) => (
    <label className="block space-y-2">
      <span className="text-sm font-medium text-slate-300">{label}</span>
      <input
        ref={ref}
        className={cn(
          "h-12 w-full rounded-md border border-line bg-white/[0.07] px-4 text-sm text-white placeholder:text-slate-500 transition focus:outline-none focus:ring-2 focus:ring-electric/30",
          error && "border-rose-400/70",
          className
        )}
        {...props}
      />
      {error && <span className="text-xs text-rose-300">{error}</span>}
    </label>
  )
);

Input.displayName = "Input";

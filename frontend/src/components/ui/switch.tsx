"use client";

import { cn } from "@/lib/utils";

/** An on/off switch. Announced to screen readers as a switch with its state. */
export function Switch({
  checked,
  onCheckedChange,
  disabled,
  label,
  className,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  label: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onCheckedChange(!checked)}
      className={cn(
        "relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors outline-none",
        "focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50",
        checked ? "bg-brand" : "bg-input",
        className,
      )}
    >
      <span
        aria-hidden
        className={cn(
          "inline-block size-4 rounded-full bg-background shadow-sm transition-transform",
          checked ? "translate-x-[18px]" : "translate-x-0.5",
        )}
      />
    </button>
  );
}

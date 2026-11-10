import { cn } from "@/lib/utils";

/**
 * The NEXUS mark: one hub with three systems joined to it.
 * Drawn in currentColor so it follows the theme.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
      className={cn("size-6", className)}
    >
      <path
        d="M12 12 12 4.5M12 12l6.5 3.75M12 12l-6.5 3.75"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
      <circle cx="12" cy="4.5" r="2" fill="currentColor" />
      <circle cx="18.5" cy="15.75" r="2" fill="currentColor" />
      <circle cx="5.5" cy="15.75" r="2" fill="currentColor" />
      <circle cx="12" cy="12" r="3.1" fill="var(--background)" stroke="currentColor" strokeWidth="1.6" />
    </svg>
  );
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn("flex items-center gap-2", className)}>
      <span className="flex size-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <LogoMark className="size-[18px] [--background:var(--primary)]" />
      </span>
      <span className="text-[15px] font-semibold tracking-tight">
        NEXUS<span className="ml-1 font-normal text-muted-foreground">AI</span>
      </span>
    </span>
  );
}

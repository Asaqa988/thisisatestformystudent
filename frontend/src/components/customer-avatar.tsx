import { hueFor, initials } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Initials on a tint that is stable for each name and readable in both themes. */
export function CustomerAvatar({
  name,
  className,
}: {
  name: string;
  className?: string;
}) {
  const hue = hueFor(name);
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-8 shrink-0 select-none items-center justify-center rounded-full text-[11px] font-semibold",
        className,
      )}
      style={{
        backgroundColor: `light-dark(oklch(0.93 0.045 ${hue}), oklch(0.33 0.05 ${hue}))`,
        color: `light-dark(oklch(0.4 0.1 ${hue}), oklch(0.88 0.07 ${hue}))`,
      }}
    >
      {initials(name)}
    </span>
  );
}

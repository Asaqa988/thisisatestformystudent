import { cn } from "@/lib/utils";

export function PageHeader({
  title,
  description,
  actions,
  className,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-h-14 shrink-0 items-center justify-between gap-4 border-b px-4 py-2.5 sm:px-6",
        className,
      )}
    >
      <div className="min-w-0">
        <h1 className="truncate text-[15px] font-semibold tracking-tight">{title}</h1>
        {description && (
          <p className="truncate text-[13px] text-muted-foreground">{description}</p>
        )}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

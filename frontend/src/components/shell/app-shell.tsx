"use client";

import { Menu, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

import { Sidebar } from "./sidebar";

/**
 * The frame every page sits in.
 * Desktop: a fixed sidebar beside the page.
 * Phone and tablet: a top bar, with the same sidebar sliding in as a drawer.
 */
export function AppShell({ children }: { children: React.ReactNode }) {
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  return (
    <div className="flex h-dvh overflow-hidden bg-background">
      <aside className="hidden w-60 shrink-0 border-r border-sidebar-border lg:block">
        <Sidebar />
      </aside>

      {/* Drawer for small screens */}
      <div
        className={cn("fixed inset-0 z-40 lg:hidden", drawerOpen ? "pointer-events-auto" : "pointer-events-none")}
        aria-hidden={!drawerOpen}
      >
        <button
          type="button"
          tabIndex={-1}
          aria-label="Close navigation"
          onClick={() => setDrawerOpen(false)}
          className={cn(
            "absolute inset-0 bg-foreground/30 backdrop-blur-[2px] transition-opacity duration-200",
            drawerOpen ? "opacity-100" : "opacity-0",
          )}
        />
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Navigation"
          className={cn(
            "absolute inset-y-0 left-0 w-[17rem] max-w-[85vw] border-r border-sidebar-border shadow-xl transition-transform duration-200 ease-out",
            drawerOpen ? "translate-x-0" : "-translate-x-full",
          )}
        >
          {drawerOpen && <Sidebar onNavigate={() => setDrawerOpen(false)} />}
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Close navigation"
            onClick={() => setDrawerOpen(false)}
            className="absolute right-2 top-3.5"
          >
            <X />
          </Button>
        </div>
      </div>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b px-3 lg:hidden">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label="Open navigation"
            aria-expanded={drawerOpen}
            onClick={() => setDrawerOpen(true)}
          >
            <Menu />
          </Button>
          <Logo />
        </header>
        <main className="min-h-0 flex-1">{children}</main>
      </div>
    </div>
  );
}

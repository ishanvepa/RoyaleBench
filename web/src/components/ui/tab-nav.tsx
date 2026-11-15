import { NavLink, useLocation } from "react-router";
import { cn } from "@/lib/cn";

export interface TabNavItem {
  to: string;
  label: string;
  /** Match only this exact path (for an index route). */
  end?: boolean;
  /** Path prefixes of other pages that belong under this tab, so it stays highlighted on them. */
  alsoActiveFor?: string[];
}

/** Route-based tabs: each tab is a real link, so it can be bookmarked, opened in a new tab and reloaded. */
export function TabNav({ items, label, className }: { items: TabNavItem[]; label: string; className?: string }) {
  const { pathname } = useLocation();
  return (
    <nav aria-label={label} className={cn("flex gap-7 border-b border-line", className)}>
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={({ isActive }) =>
            cn(
              "-mb-px whitespace-nowrap border-b-2 px-0.5 pb-3 pt-2 text-sm transition-colors",
              isActive || item.alsoActiveFor?.some((prefix) => pathname.startsWith(prefix))
                ? "border-muted font-semibold text-ink"
                : "border-transparent text-muted hover:text-ink",
            )
          }
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

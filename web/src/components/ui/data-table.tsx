import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type OnChangeFn,
  type SortingState,
} from "@tanstack/react-table";
import { ArrowDown, ArrowUp, ArrowUpDown } from "lucide-react";
import { useState, type KeyboardEvent, type MouseEvent, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Skeleton } from "./skeleton";

export interface DataTableProps<T> {
  // TanStack's column type is invariant in the cell value, so a list of differently typed columns needs `any` here.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  columns: ColumnDef<T, any>[];
  data: readonly T[];
  getRowId: (row: T) => string;
  /** Controlled sorting (for example kept in the URL). Omit to let the table manage it. */
  sorting?: SortingState;
  onSortingChange?: OnChangeFn<SortingState>;
  initialSorting?: SortingState;
  /** Called when a row (not a link or button inside it) is clicked or activated with the keyboard. */
  onRowClick?: (row: T) => void;
  selectedRowId?: string | null;
  loading?: boolean;
  /** Shown instead of the body when there are no rows. */
  empty?: ReactNode;
  /** Accessible name for the table. */
  caption: string;
  className?: string;
}

const INTERACTIVE = "a, button, input, select, textarea, label, [role='checkbox'], [role='switch']";

export function DataTable<T>({
  columns,
  data,
  getRowId,
  sorting,
  onSortingChange,
  initialSorting,
  onRowClick,
  selectedRowId,
  loading = false,
  empty,
  caption,
  className,
}: DataTableProps<T>) {
  const [internal, setInternal] = useState<SortingState>(initialSorting ?? []);
  const table = useReactTable({
    data: data as T[],
    columns,
    getRowId,
    state: { sorting: sorting ?? internal },
    onSortingChange: onSortingChange ?? setInternal,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    enableSortingRemoval: false,
  });
  const rows = table.getRowModel().rows;
  const columnCount = table.getVisibleLeafColumns().length;

  function activate(event: MouseEvent | KeyboardEvent, row: T) {
    if (!onRowClick) return;
    if ((event.target as HTMLElement).closest(INTERACTIVE)) return;
    if ("key" in event && event.key !== "Enter" && event.key !== " ") return;
    if ("key" in event) event.preventDefault();
    onRowClick(row);
  }

  return (
    <div className={cn("overflow-x-auto rounded-xl border border-line bg-surface", className)}>
      <table className="w-full border-collapse text-[13px]">
        <caption className="sr-only">{caption}</caption>
        <thead>
          {table.getHeaderGroups().map((group) => (
            <tr key={group.id} className="border-b border-line">
              {group.headers.map((header) => {
                const align = header.column.columnDef.meta?.align ?? "left";
                const sorted = header.column.getIsSorted();
                const sortable = header.column.getCanSort();
                return (
                  <th
                    key={header.id}
                    scope="col"
                    aria-sort={sorted === "asc" ? "ascending" : sorted === "desc" ? "descending" : sortable ? "none" : undefined}
                    className={cn(
                      "whitespace-nowrap px-3 py-2.5 text-[11px] font-medium uppercase tracking-wider text-muted",
                      align === "right" && "text-right",
                      align === "center" && "text-center",
                      sorted && "text-ink",
                    )}
                  >
                    {header.isPlaceholder ? null : sortable ? (
                      <button
                        type="button"
                        onClick={header.column.getToggleSortingHandler()}
                        className={cn(
                          "inline-flex items-center gap-1 uppercase tracking-wider hover:text-ink",
                          align === "right" && "flex-row-reverse",
                        )}
                      >
                        {flexRender(header.column.columnDef.header, header.getContext())}
                        {sorted === "asc" ? (
                          <ArrowUp className="size-3" aria-hidden />
                        ) : sorted === "desc" ? (
                          <ArrowDown className="size-3" aria-hidden />
                        ) : (
                          <ArrowUpDown className="size-3 opacity-40" aria-hidden />
                        )}
                      </button>
                    ) : (
                      flexRender(header.column.columnDef.header, header.getContext())
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {loading ? (
            Array.from({ length: 5 }, (_, i) => (
              <tr key={i} className="border-b border-line last:border-0">
                <td colSpan={columnCount} className="px-3 py-2.5">
                  <Skeleton className="h-5 w-full" />
                </td>
              </tr>
            ))
          ) : rows.length === 0 ? (
            <tr>
              <td colSpan={columnCount} className="px-3 py-10 text-center text-muted">
                {empty ?? "Nothing to show."}
              </td>
            </tr>
          ) : (
            rows.map((row) => {
              const selected = selectedRowId === row.id;
              return (
                <tr
                  key={row.id}
                  aria-selected={onRowClick ? selected : undefined}
                  tabIndex={onRowClick ? 0 : undefined}
                  onClick={onRowClick ? (e) => activate(e, row.original) : undefined}
                  onKeyDown={onRowClick ? (e) => activate(e, row.original) : undefined}
                  className={cn(
                    "border-b border-line last:border-0",
                    onRowClick && "cursor-pointer hover:bg-selected/60",
                    selected && "bg-selected",
                  )}
                >
                  {row.getVisibleCells().map((cell) => {
                    const meta = cell.column.columnDef.meta;
                    return (
                      <td
                        key={cell.id}
                        className={cn(
                          "px-3 py-2.5 align-middle",
                          meta?.align === "right" && "text-right tabular-nums",
                          meta?.align === "center" && "text-center",
                          meta?.className,
                        )}
                      >
                        {flexRender(cell.column.columnDef.cell, cell.getContext())}
                      </td>
                    );
                  })}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
}

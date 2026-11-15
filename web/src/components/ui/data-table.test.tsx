import { createColumnHelper, type SortingState } from "@tanstack/react-table";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DataTable } from "./data-table";

interface Row {
  id: string;
  name: string;
  count: number | null;
}

const col = createColumnHelper<Row>();
const columns = [
  col.accessor("name", { header: "Name", cell: (c) => <a href={`#${c.row.original.id}`}>{c.getValue()}</a> }),
  col.accessor((r) => r.count ?? undefined, {
    id: "count",
    header: "Count",
    sortUndefined: "last",
    sortDescFirst: true,
    meta: { align: "right" },
    cell: (c) => String(c.row.original.count ?? "–"),
  }),
];
const rows: Row[] = [
  { id: "a", name: "alpha", count: 2 },
  { id: "b", name: "bravo", count: null },
  { id: "c", name: "charlie", count: 9 },
];

const bodyRows = () => within(screen.getByRole("table")).getAllByRole("row").slice(1);
const names = () => bodyRows().map((r) => within(r).getAllByRole("cell")[0]?.textContent);

describe("DataTable", () => {
  it("renders the rows with an accessible caption", () => {
    render(<DataTable caption="Things" columns={columns} data={rows} getRowId={(r) => r.id} />);
    expect(screen.getByRole("table", { name: "Things" })).toBeInTheDocument();
    expect(names()).toEqual(["alpha", "bravo", "charlie"]);
  });

  it("sorts by a header: biggest first for numbers, empty values always last, then reverses", async () => {
    const user = userEvent.setup();
    render(<DataTable caption="Things" columns={columns} data={rows} getRowId={(r) => r.id} />);
    const header = screen.getByRole("columnheader", { name: /count/i });
    expect(header).toHaveAttribute("aria-sort", "none");

    await user.click(within(header).getByRole("button"));
    expect(header).toHaveAttribute("aria-sort", "descending");
    expect(names()).toEqual(["charlie", "alpha", "bravo"]);

    await user.click(within(header).getByRole("button"));
    expect(header).toHaveAttribute("aria-sort", "ascending");
    expect(names()).toEqual(["alpha", "charlie", "bravo"]);
  });

  it("supports controlled sorting, reporting changes instead of applying them itself", async () => {
    const user = userEvent.setup();
    const onSortingChange = vi.fn();
    const sorting: SortingState = [{ id: "name", desc: true }];
    render(<DataTable caption="Things" columns={columns} data={rows} getRowId={(r) => r.id} sorting={sorting} onSortingChange={onSortingChange} />);
    expect(names()).toEqual(["charlie", "bravo", "alpha"]);
    await user.click(within(screen.getByRole("columnheader", { name: /count/i })).getByRole("button"));
    expect(onSortingChange).toHaveBeenCalledTimes(1);
    expect(names()).toEqual(["charlie", "bravo", "alpha"]); // unchanged until the parent updates `sorting`
  });

  it("activates a row on click and Enter, but not when the click lands on a link inside it", async () => {
    const user = userEvent.setup();
    const onRowClick = vi.fn();
    render(<DataTable caption="Things" columns={columns} data={rows} getRowId={(r) => r.id} onRowClick={onRowClick} selectedRowId="c" />);
    await user.click(screen.getByRole("link", { name: "alpha" }));
    expect(onRowClick).not.toHaveBeenCalled();

    await user.click(bodyRows()[1]!);
    expect(onRowClick).toHaveBeenLastCalledWith(rows[1]);

    bodyRows()[2]!.focus();
    await user.keyboard("{Enter}");
    expect(onRowClick).toHaveBeenLastCalledWith(rows[2]);
    expect(bodyRows()[2]).toHaveAttribute("aria-selected", "true");
    expect(bodyRows()[0]).toHaveAttribute("aria-selected", "false");
  });

  it("shows the empty message, and skeleton rows while loading", () => {
    const { rerender } = render(<DataTable caption="Things" columns={columns} data={[]} getRowId={(r) => r.id} empty="Nothing here yet." />);
    expect(screen.getByText("Nothing here yet.")).toBeInTheDocument();
    rerender(<DataTable caption="Things" columns={columns} data={rows} getRowId={(r) => r.id} loading />);
    expect(screen.queryByText("alpha")).not.toBeInTheDocument();
  });
});

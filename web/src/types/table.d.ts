import type { RowData } from "@tanstack/react-table";

declare module "@tanstack/react-table" {
  // The type parameters must match the library's declaration even though this augmentation does not use them.
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  interface ColumnMeta<TData extends RowData, TValue> {
    /** Horizontal alignment of the header and cells; numbers should be "right". */
    align?: "left" | "right" | "center";
    /** Extra classes for every cell in the column. */
    className?: string;
  }
}

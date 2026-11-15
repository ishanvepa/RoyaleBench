import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { statusMeta } from "@/lib/status";
import { SegmentedProgress } from "./SegmentedProgress";
import { StatusPill } from "./StatusPill";

describe("StatusPill", () => {
  it.each([
    ["run", "IN_PROGRESS", "Running"],
    ["run", "FINISHED", "Finished"],
    ["run", "ERROR", "Failed"],
    ["task", "PENDING", "Queued"],
    ["task", "EVALUATING", "Grading"],
    ["task", "ERROR", "Error"],
  ] as const)("%s %s reads %s", (kind, status, label) => {
    render(<StatusPill kind={kind} status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("still renders a status Valkyrie adds later, with its raw name", () => {
    render(<StatusPill kind="run" status="ARCHIVED" />);
    expect(screen.getByText("ARCHIVED")).toBeInTheDocument();
    expect(statusMeta("task", "WEIRD").tone).toBe("outline");
  });
});

describe("SegmentedProgress", () => {
  it("describes the counts for screen readers and lists them in the legend", () => {
    render(<SegmentedProgress counts={{ FINISHED: 3, IN_PROGRESS: 1, PENDING: 2 }} total={6} legend />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Tasks: 3 done, 1 running, 2 queued");
    expect(screen.getByText("done", { exact: false })).toBeInTheDocument();
  });

  it("copes with no tasks and with statuses it does not know", () => {
    const { rerender } = render(<SegmentedProgress counts={{}} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Tasks: no tasks");
    rerender(<SegmentedProgress counts={{ MYSTERY: 2 }} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("Tasks: 2 mystery");
  });
});

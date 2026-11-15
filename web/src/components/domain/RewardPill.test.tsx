import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RewardPill } from "./RewardPill";

describe("RewardPill", () => {
  it.each([
    [1, "Pass"],
    [0, "Fail"],
  ])("renders binary reward %s as %s", (reward, label) => {
    render(<RewardPill reward={reward} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("keeps partial rewards numeric", () => {
    render(<RewardPill reward={0.5} />);
    expect(screen.getByText("0.5")).toBeInTheDocument();
  });
});

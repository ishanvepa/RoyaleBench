import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "@/api/client";
import { QueryBoundary } from "./QueryBoundary";

function Probe({ fn }: { fn: () => Promise<string> }) {
  const query = useQuery({ queryKey: ["probe"], queryFn: fn, retry: false });
  return <QueryBoundary query={query}>{(data) => <p>data: {data}</p>}</QueryBoundary>;
}

function renderProbe(fn: () => Promise<string>) {
  const client = new QueryClient();
  return { client, ...render(<QueryClientProvider client={client}><Probe fn={fn} /></QueryClientProvider>) };
}

describe("QueryBoundary", () => {
  it("shows a loading skeleton, then the data", async () => {
    renderProbe(() => Promise.resolve("hello"));
    expect(screen.getByRole("status", { name: "Loading" })).toBeInTheDocument();
    expect(await screen.findByText("data: hello")).toBeInTheDocument();
  });

  it("shows the error with a retry button, and recovers when the retry works", async () => {
    const user = userEvent.setup();
    const fn = vi.fn<() => Promise<string>>().mockRejectedValueOnce(new ApiError(503, "valkyrie_network", "Cannot reach Valkyrie")).mockResolvedValue("back");
    renderProbe(fn);
    expect(await screen.findByRole("alert")).toHaveTextContent("Cannot reach Valkyrie");
    expect(screen.getByText(/check your connection/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("data: back")).toBeInTheDocument();
  });

  it("tells the user to sign in when Valkyrie rejects the login", async () => {
    renderProbe(() => Promise.reject(new ApiError(401, "valkyrie_auth", "Not signed in")));
    expect(await screen.findByText(/valkyrie login/)).toBeInTheDocument();
  });

  it("keeps the old data on screen, under a warning, when a background refresh fails", async () => {
    const fn = vi.fn<() => Promise<string>>().mockResolvedValueOnce("first").mockRejectedValue(new Error("boom"));
    const { client } = renderProbe(fn);
    expect(await screen.findByText("data: first")).toBeInTheDocument();
    void client.refetchQueries({ queryKey: ["probe"] });
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/couldn't refresh/i));
    expect(screen.getByText("data: first")).toBeInTheDocument();
  });
});

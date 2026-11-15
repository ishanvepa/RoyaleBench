import { act, renderHook } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter, useLocation } from "react-router";
import { describe, expect, it } from "vitest";
import { z } from "zod";
import { boolParam, enumParam, listParam, stringParam, useSearchState } from "./useSearchState";

const schema = z.object({
  q: stringParam(),
  sort: stringParam("rank"),
  dir: enumParam(["asc", "desc"] as const, "asc"),
  mine: boolParam(),
  status: listParam(),
});

function setup(initial: string) {
  const wrapper = ({ children }: { children: ReactNode }) => <MemoryRouter initialEntries={[initial]}>{children}</MemoryRouter>;
  return renderHook(
    () => {
      const [state, update] = useSearchState(schema);
      return { state, update, search: useLocation().search };
    },
    { wrapper },
  );
}

describe("useSearchState", () => {
  it("falls back to defaults for an empty URL", () => {
    const { result } = setup("/page");
    expect(result.current.state).toEqual({ q: "", sort: "rank", dir: "asc", mine: false, status: [] });
  });

  it("reads typed values from the URL and ignores invalid ones", () => {
    const { result } = setup("/page?q=hi&sort=score&dir=sideways&mine=true&status=A,B");
    expect(result.current.state).toEqual({ q: "hi", sort: "score", dir: "asc", mine: true, status: ["A", "B"] });
  });

  it("writes changes to the URL and drops values that equal their default, so links stay short", () => {
    const { result } = setup("/page");
    act(() => result.current.update({ sort: "score", dir: "desc", mine: true, status: ["A", "B"] }));
    expect(new URLSearchParams(result.current.search).toString()).toBe("sort=score&dir=desc&mine=true&status=A%2CB");
    expect(result.current.state.status).toEqual(["A", "B"]);

    act(() => result.current.update({ sort: "rank", status: [], mine: false }));
    expect(result.current.search).toBe("?dir=desc");
  });

  it("keeps parameters it was not asked to change", () => {
    const { result } = setup("/page?other=1&sort=score");
    act(() => result.current.update({ q: "x" }));
    expect(new URLSearchParams(result.current.search).get("other")).toBe("1");
    expect(result.current.state).toMatchObject({ q: "x", sort: "score" });
  });
});

import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { cloneElement, type ReactElement } from "react";
import type * as Recharts from "recharts";
import { afterAll, afterEach, beforeAll, vi } from "vitest";
import { server } from "./server";

// jsdom does no layout, so Recharts' ResponsiveContainer measures 0 x 0, draws nothing and warns. Give charts a fixed size.
vi.mock("recharts", async (importOriginal) => {
  const actual = await importOriginal<typeof Recharts>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactElement<{ width?: number; height?: number }> }) => cloneElement(children, { width: 600, height: 300 }),
  };
});

// The first test to open a lazily loaded page waits for Vite to transform that page's modules; allow for it.
configure({ asyncUtilTimeout: 4_000 });

// jsdom lacks a few browser APIs that Radix UI and layout code touch.
class ResizeObserverStub {
  observe() {}
  unobserve() {}
  disconnect() {}
}
globalThis.ResizeObserver ??= ResizeObserverStub as unknown as typeof ResizeObserver;
Element.prototype.scrollIntoView ??= () => {};
Element.prototype.hasPointerCapture ??= () => false;
Element.prototype.releasePointerCapture ??= () => {};
window.matchMedia ??= ((query: string) => ({
  matches: false,
  media: query,
  onchange: null,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {},
  dispatchEvent: () => false,
})) as typeof window.matchMedia;

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => {
  cleanup();
  server.resetHandlers();
});
afterAll(() => server.close());

import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server, apiError } from "@/test/server";
import { api, ApiError, fieldErrors, unwrap } from "./client";

describe("unwrap", () => {
  it("returns the data of a successful call", async () => {
    server.use(http.get("*/api/evals/environment", () => HttpResponse.json({ valkyrie_ok: true })));
    const data = await unwrap(api.GET("/api/evals/environment"));
    expect(data).toMatchObject({ valkyrie_ok: true });
  });

  it("turns the server's error envelope into an ApiError with its code, status and message", async () => {
    server.use(http.get("*/api/evals/environment", () => apiError(401, "valkyrie_auth", "Not signed in to Valkyrie.")));
    const error = await unwrap(api.GET("/api/evals/environment")).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 401, code: "valkyrie_auth", message: "Not signed in to Valkyrie." });
    expect((error as ApiError).transient).toBe(false);
  });

  it("marks server-side failures as transient so they are retried", async () => {
    server.use(http.get("*/api/evals/environment", () => apiError(503, "valkyrie_network", "down")));
    const error = (await unwrap(api.GET("/api/evals/environment")).catch((e: unknown) => e)) as ApiError;
    expect(error.transient).toBe(true);
  });

  it("copes with an error that is not in the envelope shape", async () => {
    server.use(http.get("*/api/evals/environment", () => new HttpResponse("upstream exploded", { status: 502, statusText: "Bad Gateway" })));
    const error = (await unwrap(api.GET("/api/evals/environment")).catch((e: unknown) => e)) as ApiError;
    expect(error).toBeInstanceOf(ApiError);
    expect(error.status).toBe(502);
    expect(error.code).toBe("unknown");
  });

  it("reports an unreachable server as a network error", async () => {
    server.use(http.get("*/api/evals/environment", () => HttpResponse.error()));
    const error = (await unwrap(api.GET("/api/evals/environment")).catch((e: unknown) => e)) as ApiError;
    expect(error).toMatchObject({ status: 0, code: "network" });
    expect(error.transient).toBe(true);
  });

  it("sends the client header on every request", async () => {
    let header: string | null = null;
    server.use(
      http.post("*/api/evals/jobs/:id/stop", ({ request }) => {
        header = request.headers.get("x-rb-client");
        return HttpResponse.json({ status: "stopping" });
      }),
    );
    await unwrap(api.POST("/api/evals/jobs/{run_id}/stop", { params: { path: { run_id: "r1" }, query: { force: false } } }));
    expect(header).toBe("web");
  });
});

describe("fieldErrors", () => {
  it("maps validation details to field messages", () => {
    const error = new ApiError(422, "validation_error", "bad", [
      { field: "tags", message: "Invalid tag" },
      { field: "", message: "Form level" },
    ]);
    expect(fieldErrors(error)).toEqual({ tags: "Invalid tag", "": "Form level" });
    expect(fieldErrors(new Error("x"))).toEqual({});
    expect(fieldErrors(new ApiError(500, "internal", "x"))).toEqual({});
  });
});

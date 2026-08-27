import { ApiError, createApiClient } from "./client";

describe("API client", () => {
  it("sends credentialed JSON requests with CSRF and idempotency headers", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    const client = createApiClient({ fetchImpl: fetchMock, baseUrl: "/api/v1" });

    await client.request("/resource", {
      method: "POST",
      body: { value: "safe" },
      csrfToken: "csrf-safe",
      idempotencyKey: "idem-safe",
    });

    const [url, init] = fetchMock.mock.calls[0] ?? [];
    const headers = new Headers(init?.headers);
    expect(url).toBe("/api/v1/resource");
    expect(init?.method).toBe("POST");
    expect(init?.credentials).toBe("include");
    expect(init?.body).toBe(JSON.stringify({ value: "safe" }));
    expect(headers.get("Content-Type")).toBe("application/json");
    expect(headers.get("X-CSRF-Token")).toBe("csrf-safe");
    expect(headers.get("Idempotency-Key")).toBe("idem-safe");
  });

  it("preserves the backend error envelope", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          code: "VALIDATION_ERROR",
          message: "Перевірте поля.",
          field_errors: [{ field: "email", code: "INVALID_EMAIL", message: "Некоректно." }],
          request_id: "request-safe",
        }),
        { status: 422, headers: { "Content-Type": "application/json" } },
      ),
    );
    const client = createApiClient({ fetchImpl: fetchMock });

    const error: unknown = await client.request("/resource").catch((reason: unknown) => reason);
    expect(error).toBeInstanceOf(ApiError);
    if (!(error instanceof ApiError)) throw new Error("Expected ApiError");
    expect(error.code).toBe("VALIDATION_ERROR");
    expect(error.fieldErrors).toEqual([
      { field: "email", code: "INVALID_EMAIL", message: "Некоректно." },
    ]);
    expect(error.requestId).toBe("request-safe");
  });
});

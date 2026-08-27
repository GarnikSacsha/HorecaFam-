import type { ErrorEnvelope, FieldError, SessionResponse } from "./contracts";

interface ClientOptions {
  baseUrl?: string;
  fetchImpl?: typeof fetch;
}

export interface RequestOptions extends Omit<RequestInit, "body" | "headers"> {
  body?: unknown;
  csrfToken?: string;
  headers?: Record<string, string>;
  idempotencyKey?: string;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fieldErrors: FieldError[];
  readonly requestId: string | null;

  constructor(status: number, envelope?: Partial<ErrorEnvelope>) {
    super(envelope?.message ?? "Не вдалося виконати запит.");
    this.name = "ApiError";
    this.status = status;
    this.code = envelope?.code ?? "NETWORK_OR_HTTP_ERROR";
    this.fieldErrors = envelope?.field_errors ?? [];
    this.requestId = envelope?.request_id ?? null;
  }
}

export interface ApiClient {
  request<T>(path: string, options?: RequestOptions): Promise<T>;
  getSession(): Promise<SessionResponse>;
}

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<ErrorEnvelope>;
  return (
    typeof candidate.code === "string" &&
    typeof candidate.message === "string" &&
    Array.isArray(candidate.field_errors) &&
    typeof candidate.request_id === "string"
  );
}

export function createApiClient(options: ClientOptions = {}): ApiClient {
  const baseUrl = (options.baseUrl ?? "/api/v1").replace(/\/$/, "");
  const fetchImpl = options.fetchImpl ?? fetch;

  const request = async <T>(path: string, requestOptions: RequestOptions = {}): Promise<T> => {
    const { body, csrfToken, headers: customHeaders, idempotencyKey, ...init } = requestOptions;
    const headers: Record<string, string> = { Accept: "application/json", ...customHeaders };

    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (csrfToken) headers["X-CSRF-Token"] = csrfToken;
    if (idempotencyKey) headers["Idempotency-Key"] = idempotencyKey;

    let response: Response;
    try {
      response = await fetchImpl(`${baseUrl}${path}`, {
        ...init,
        credentials: "include",
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
    } catch {
      throw new ApiError(0, {
        code: "NETWORK_ERROR",
        message: "Немає зв’язку із сервером. Перевірте мережу та повторіть спробу.",
      });
    }

    if (response.status === 204) return undefined as T;

    const contentType = response.headers.get("content-type") ?? "";
    const payload: unknown = contentType.includes("application/json")
      ? await response.json()
      : undefined;

    if (!response.ok) {
      throw new ApiError(response.status, isErrorEnvelope(payload) ? payload : undefined);
    }
    return payload as T;
  };

  return { request, getSession: () => request<SessionResponse>("/auth/session") };
}

export const apiClient = createApiClient();

export function createIdempotencyKey(): string {
  return crypto.randomUUID();
}

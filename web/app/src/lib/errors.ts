import { ApiError } from "./types";

export async function parseApiError(res: Response): Promise<ApiError> {
  let payload: unknown = null;
  try {
    payload = await res.json();
  } catch {
    // ignore
  }
  if (payload && typeof payload === "object" && "error" in payload) {
    const err = (payload as any).error;
    return {
      code: err.code || `HTTP_${res.status}`,
      message: err.message || res.statusText,
      details: err.details,
      status: res.status,
    };
  }
  return {
    code: `HTTP_${res.status}`,
    message:
      (payload as any)?.detail ||
      (payload as any)?.message ||
      res.statusText ||
      "Request failed",
    details: payload,
    status: res.status,
  };
}

export function normalizeError(err: unknown): ApiError {
  if (isApiError(err)) return err;
  if (err instanceof Error) {
    return { code: "CLIENT_ERROR", message: err.message };
  }
  return { code: "UNKNOWN", message: "Unknown error" };
}

export function isApiError(err: unknown): err is ApiError {
  return Boolean(err && typeof err === "object" && "code" in (err as any) && "message" in (err as any));
}

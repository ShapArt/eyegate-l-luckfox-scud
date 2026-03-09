import {
  ApiError,
  AppConfig,
  CameraHealth,
  EventRecord,
  GateStatus,
  QuickUserPayload,
  SimState,
  UserRecord,
} from "./types";
import { parseApiError } from "./errors";

function guessDevApiBase(): string {
  if (typeof window === "undefined") return "";
  const devPorts = new Set(["5173", "4173", "5174", "4174"]);
  if (devPorts.has(window.location.port)) {
    return "http://127.0.0.1:8000";
  }
  return `${window.location.protocol}//${window.location.host}`;
}

const BASE_URL = (() => {
  const raw = (import.meta.env.VITE_API_BASE as string | undefined)?.trim();
  if (raw) return raw.replace(/\/+$/, "");
  return guessDevApiBase();
})();

export function getApiBase(): string {
  return BASE_URL;
}

let authToken: string | null = null;

export function loadAuthTokenFromStorage(): string | null {
  const stored = localStorage.getItem("eyegate.admin.token");
  authToken = stored;
  return authToken;
}

export function setAuthToken(token: string | null): void {
  authToken = token;
  if (token) {
    localStorage.setItem("eyegate.admin.token", token);
  } else {
    localStorage.removeItem("eyegate.admin.token");
  }
}

type FetchOpts = RequestInit & { skipAuth?: boolean };

async function apiFetch<T>(path: string, init?: FetchOpts): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string> | undefined),
  };
  if (!init?.skipAuth && authToken) {
    headers.Authorization = `Bearer ${authToken}`;
  }
  const url = `${BASE_URL}${path}`;
  let res: Response;
  try {
    res = await fetch(url, {
      ...init,
      headers,
    });
  } catch (err) {
    throw {
      code: "NETWORK_ERROR",
      message: "Cannot reach backend",
      details: err instanceof Error ? err.message : err,
    } satisfies ApiError;
  }
  if (!res.ok) {
    const err = await parseApiError(res);
    throw err;
  }
  if (res.status === 204) {
    return {} as T;
  }
  return (await res.json()) as T;
}

// hydrate token on module load
loadAuthTokenFromStorage();

export const api = {
  async adminLogin(login: string, password: string) {
    return apiFetch<{ status: string; token: string; user_id: number; role: string; state: string }>("/api/auth/admin/login", {
      method: "POST",
      body: JSON.stringify({ login, password }),
      skipAuth: true,
    });
  },
  async userLogin(login: string, password: string) {
    return apiFetch<{ status: string; token: string; user_id: number; role: string; state: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ login, password }),
      skipAuth: true,
    });
  },
  async kioskPin(pin: string) {
    return apiFetch<{ status: string; state: string; userId: number | null; login?: string | null }>("/api/auth/pin", {
      method: "POST",
      body: JSON.stringify({ pin }),
      skipAuth: true,
    });
  },
  async getStatus() {
    return apiFetch<GateStatus>("/api/status/");
  },
  async reset() {
    return apiFetch<GateStatus>("/api/status/reset", { method: "POST" });
  },
  async getSimState() {
    return apiFetch<SimState>("/api/sim/");
  },
  async simAction(doorId: number, action: "open" | "close") {
    return apiFetch<SimState>(`/api/sim/door/${doorId}/${action}`, { method: "POST" });
  },
  async listUsers() {
    return apiFetch<UserRecord[]>("/api/users/");
  },
  async createUser(payload: QuickUserPayload) {
    return apiFetch<UserRecord>("/api/users/", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  async enrollFace(userId: number) {
    return apiFetch<UserRecord>(`/api/users/${userId}/enroll`, {
      method: "POST",
    });
  },
  async clearFace(userId: number) {
    return apiFetch<UserRecord>(`/api/users/${userId}/clear-face`, {
      method: "POST",
    });
  },
  async deleteUser(userId: number) {
    return apiFetch<{ status: string; user_id: number }>(`/api/users/${userId}`, {
      method: "DELETE",
    });
  },
  async enrollSelf() {
    return apiFetch<UserRecord>("/api/users/me/enroll", { method: "POST" });
  },
  async listEvents(limit = 50) {
    return apiFetch<EventRecord[]>(`/api/events/?limit=${limit}`);
  },
  async getConfig() {
    return apiFetch<AppConfig>("/api/config/");
  },
  async getCameraHealth() {
    return apiFetch<CameraHealth>("/health/camera", { skipAuth: true });
  },
};

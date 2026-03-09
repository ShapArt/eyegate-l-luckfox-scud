import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { Camera, Check, LogIn } from "lucide-react";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { api, getApiBase, setAuthToken } from "../lib/api";
import { normalizeError } from "../lib/errors";
import type { ApiError } from "../lib/types";

export function EnrollPage() {
  const [creds, setCreds] = useState({ login: "", password: "" });
  const [token, setToken] = useState<string | null>(null);
  const [loginError, setLoginError] = useState<string | null>(null);
  const [enrollError, setEnrollError] = useState<string | null>(null);
  const [snapshotKey, setSnapshotKey] = useState(() => Date.now());
  const snapshotUrl = useMemo(() => `${getApiBase()}/api/video/snapshot?ts=${snapshotKey}`, [snapshotKey]);

  const loginMutation = useMutation({
    mutationFn: (payload: { login: string; password: string }) => api.userLogin(payload.login, payload.password),
    onSuccess: (res) => {
      setAuthToken(res.token);
      setToken(res.token);
      setLoginError(null);
    },
    onError: (err) => {
      const e = normalizeError(err);
      setLoginError(formatLoginError(e));
    },
  });

  const enrollMutation = useMutation({
    mutationFn: () => api.enrollSelf(),
    onSuccess: () => {
      setSnapshotKey(Date.now());
      setEnrollError(null);
      alert("Face captured and saved.");
    },
    onError: (err) => {
      const e = normalizeError(err);
      setEnrollError(e.message);
    },
  });

  const canCapture = Boolean(token);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      <Card>
        <div className="flex items-center gap-3">
          <LogIn className="h-5 w-5 text-muted" />
          <div>
            <p className="text-[12px] uppercase tracking-[0.14em] text-muted">Step 1</p>
            <h2 className="text-xl font-semibold">Authenticate</h2>
            <p className="text-sm text-muted">Use your login/password to issue a token for self-enroll.</p>
          </div>
        </div>
        <div className="mt-4 space-y-3">
          <Input
            placeholder="login"
            value={creds.login}
            onChange={(e) => setCreds((c) => ({ ...c, login: e.target.value }))}
          />
          <Input
            placeholder="password / PIN"
            type="password"
            value={creds.password}
            onChange={(e) => setCreds((c) => ({ ...c, password: e.target.value }))}
          />
          <Button
            onClick={() => loginMutation.mutate({ ...creds })}
            loading={loginMutation.isPending}
            disabled={!creds.login || !creds.password}
          >
            Get token
          </Button>
          {token && <p className="text-xs text-success">Token stored. Proceed to capture.</p>}
          {loginError && <p className="text-xs text-danger">{loginError}</p>}
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-muted">
            <Camera className="h-4 w-4" />
            <span>Live snapshot</span>
          </div>
          <Button size="sm" variant="ghost" onClick={() => setSnapshotKey(Date.now())}>
            Refresh
          </Button>
        </div>
        <div className="mt-3 overflow-hidden rounded-xl border border-border bg-black">
          <img src={snapshotUrl} alt="snapshot" className="w-full" />
        </div>
        <div className="mt-3 flex items-center gap-2">
          <Button onClick={() => enrollMutation.mutate()} disabled={!canCapture} loading={enrollMutation.isPending}>
            <Check className="mr-2 h-4 w-4" />
            Capture & Save
          </Button>
          {!canCapture && <span className="text-xs text-muted">Login first to enable capture.</span>}
        </div>
        {enrollError && <p className="mt-2 text-xs text-danger">{enrollError}</p>}
      </Card>
    </div>
  );
}

function formatLoginError(err: ApiError): string {
  switch (err.code) {
    case "USER_PENDING":
      return "User pending approval. Ask admin to approve or enable auto-approve.";
    case "USER_REJECTED":
      return "User rejected. Contact admin.";
    case "USER_BLOCKED":
      return "User blocked. Contact admin.";
    case "LOGIN_LOCKED":
      return "Too many attempts. Try again later.";
    case "INVALID_CREDENTIALS":
      return "Invalid login or password.";
    default:
      return err.message || "Login failed.";
  }
}

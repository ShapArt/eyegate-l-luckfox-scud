import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { z } from "zod";
import { Camera, CheckCircle, Trash2, UserPlus, XCircle } from "lucide-react";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { api, getApiBase } from "../lib/api";
import type { UserRecord } from "../lib/types";
import { normalizeError } from "../lib/errors";

const formSchema = z.object({
  login: z.string().min(2),
  pin: z.string().regex(/^[0-9]{4}$/, "PIN must be 4 digits"),
  name: z.string().optional(),
});

export function AdminPage() {
  const { data: users, refetch } = useQuery<UserRecord[]>({
    queryKey: ["users"],
    queryFn: () => api.listUsers(),
  });
  const [form, setForm] = useState({ login: "", pin: "", name: "" });
  const [snapshotKey, setSnapshotKey] = useState(() => Date.now());
  const snapshotUrl = useMemo(() => `${getApiBase()}/api/video/snapshot?ts=${snapshotKey}`, [snapshotKey]);

  const createMutation = useMutation({
    mutationFn: (payload: { login: string; pin: string; name?: string }) => api.createUser(payload),
    onSuccess: () => {
      setForm({ login: "", pin: "", name: "" });
      refetch();
    },
    onError: (err) => alert(normalizeError(err).message),
  });

  const enrollMutation = useMutation({
    mutationFn: (userId: number) => api.enrollFace(userId),
    onSuccess: () => {
      refetch();
      setSnapshotKey(Date.now());
    },
    onError: (err) => alert(normalizeError(err).message),
  });

  const clearMutation = useMutation({
    mutationFn: (userId: number) => api.clearFace(userId),
    onSuccess: () => refetch(),
    onError: (err) => alert(normalizeError(err).message),
  });

  const deleteMutation = useMutation({
    mutationFn: (userId: number) => api.deleteUser(userId),
    onSuccess: () => refetch(),
    onError: (err) => alert(normalizeError(err).message),
  });

  const onClearFace = (userId: number) => {
    if (!window.confirm("Clear face embedding for this user?")) return;
    clearMutation.mutate(userId);
  };

  const onDelete = (userId: number) => {
    if (!window.confirm("Delete this user? This cannot be undone.")) return;
    deleteMutation.mutate(userId);
  };

  const onSubmit = () => {
    const parsed = formSchema.safeParse(form);
    if (!parsed.success) {
      alert(parsed.error.errors[0].message);
      return;
    }
    createMutation.mutate(parsed.data);
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
      <Card>
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Admin</p>
            <h2 className="text-2xl font-semibold">Create user</h2>
            <p className="text-sm text-muted">Login + PIN (4 digits). Then click "Capture face" to store embedding.</p>
          </div>
          <UserPlus className="h-6 w-6 text-muted" />
        </div>

        <div className="mt-4 grid gap-3">
          <div className="space-y-1">
            <div className="text-xs uppercase tracking-[0.12em] text-muted">Login</div>
            <Input value={form.login} onChange={(e) => setForm((f) => ({ ...f, login: e.target.value }))} placeholder="demo" />
          </div>
          <div className="space-y-1">
            <div className="text-xs uppercase tracking-[0.12em] text-muted">PIN (4 digits)</div>
            <Input
              value={form.pin}
              maxLength={4}
              onChange={(e) => setForm((f) => ({ ...f, pin: e.target.value.replace(/\D/g, "").slice(0, 4) }))}
              placeholder="0000"
            />
          </div>
          <div className="space-y-1">
            <div className="text-xs uppercase tracking-[0.12em] text-muted">Name (optional)</div>
            <Input
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              placeholder="Badge name"
            />
          </div>
          <Button onClick={onSubmit} loading={createMutation.isPending}>
            Create
          </Button>
        </div>
      </Card>

      <Card>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-muted">
            <Camera className="h-4 w-4" />
            <span>Live snapshot (from backend camera)</span>
          </div>
          <Button size="sm" variant="ghost" onClick={() => setSnapshotKey(Date.now())}>
            Refresh
          </Button>
        </div>
        <div className="mt-3 overflow-hidden rounded-xl border border-border bg-black">
          <img src={snapshotUrl} alt="snapshot" className="w-full" />
        </div>
      </Card>

      <Card className="lg:col-span-2">
        <div className="flex items-center justify-between">
          <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Users</p>
          <Badge tone="muted">{users?.length ?? 0}</Badge>
        </div>
        <div className="mt-3 max-h-96 overflow-auto rounded-xl border border-border">
          <table className="min-w-full text-sm">
            <thead className="bg-surfaceAlt text-muted">
              <tr>
                <th className="px-3 py-2 text-left">Login</th>
                <th className="px-3 py-2 text-left">Name</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Face</th>
                <th className="px-3 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {users?.map((u) => (
                <tr key={u.id} className="border-t border-border">
                  <td className="px-3 py-2 font-semibold text-white">{u.login}</td>
                  <td className="px-3 py-2 text-white/80">{u.name || "?"}</td>
                  <td className="px-3 py-2">
                    <Badge tone={u.status === "active" ? "success" : u.status === "pending" ? "warning" : "danger"}>
                      {u.status}
                    </Badge>
                    {u.role === "admin" && (
                      <Badge tone="muted" className="ml-2">
                        admin
                      </Badge>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    {u.has_face ? (
                      <span className="flex items-center gap-1 text-success">
                        <CheckCircle className="h-3.5 w-3.5" />
                        Enrolled
                      </span>
                    ) : (
                      <span className="text-muted">missing</span>
                    )}
                  </td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-2">
                      <Button
                        size="sm"
                        variant="subtle"
                        loading={enrollMutation.isPending && enrollMutation.variables === u.id}
                        onClick={() => enrollMutation.mutate(u.id)}
                      >
                        Capture face
                      </Button>
                      <Button
                        size="sm"
                        variant="subtle"
                        disabled={u.role === "admin"}
                        loading={clearMutation.isPending && clearMutation.variables === u.id}
                        onClick={() => onClearFace(u.id)}
                      >
                        <XCircle className="mr-1 h-3.5 w-3.5" />
                        Clear face
                      </Button>
                      <Button
                        size="sm"
                        variant="subtle"
                        disabled={u.role === "admin"}
                        loading={deleteMutation.isPending && deleteMutation.variables === u.id}
                        onClick={() => onDelete(u.id)}
                      >
                        <Trash2 className="mr-1 h-3.5 w-3.5" />
                        Delete
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
              {users?.length === 0 && (
                <tr>
                  <td className="px-3 py-4 text-muted" colSpan={5}>
                    No users yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

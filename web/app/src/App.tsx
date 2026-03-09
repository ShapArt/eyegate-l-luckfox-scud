import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { Gauge, KeySquare, MonitorSmartphone, PanelsTopLeft, Radar, UserPlus } from "lucide-react";
import { KioskPage } from "./pages/KioskPage";
import { MonitorPage } from "./pages/MonitorPage";
import { SimPage } from "./pages/SimPage";
import { AdminPage } from "./pages/AdminPage";
import { EnrollPage } from "./pages/EnrollPage";
import { useStatusStream } from "./hooks/useStatusStream";
import { humanState } from "./lib/utils";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import type { GateStatus } from "./lib/types";

const nav = [
  { to: "/kiosk", label: "Kiosk", icon: KeySquare },
  { to: "/monitor", label: "Monitor", icon: Radar },
  { to: "/sim", label: "Simulator", icon: PanelsTopLeft },
  { to: "/admin", label: "Admin", icon: MonitorSmartphone },
  { to: "/enroll", label: "Enroll", icon: UserPlus },
];

export default function App() {
  const { status, conn, refresh } = useStatusStream();

  return (
    <div className="min-h-screen bg-base text-white">
      <div className="mx-auto flex max-w-6xl flex-col gap-5 px-6 py-6">
        <header className="flex flex-col gap-3 rounded-2xl border border-border bg-surface px-4 py-4 shadow-card lg:flex-row lg:items-center lg:justify-between">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-accent text-surface shadow-soft">
              <Gauge className="h-5 w-5" />
            </div>
            <div>
              <p className="text-xs uppercase tracking-[0.18em] text-muted">EyeGate</p>
              <p className="text-xl font-semibold leading-tight">Mantrap control</p>
              <p className="text-[12px] text-muted">Kiosk + Monitor + Simulator (live sync)</p>
            </div>
          </div>
          <nav className="flex flex-wrap items-center gap-2">
            {nav.map((item) => (
              <NavLink key={item.to} to={item.to}>
                {({ isActive }) => (
                  <div
                    className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm transition ${
                      isActive
                        ? "border-accent bg-surfaceAlt text-white"
                        : "border-border text-muted hover:border-accent hover:text-white"
                    }`}
                  >
                    <item.icon className="h-4 w-4" />
                    {item.label}
                  </div>
                )}
              </NavLink>
            ))}
          </nav>
          <SystemSummary conn={conn} status={status} onRefresh={refresh} />
        </header>

        <main className="pb-6">
          <Routes>
            <Route path="/" element={<Navigate to="/kiosk" replace />} />
            <Route path="/kiosk" element={<KioskPage status={status} />} />
            <Route path="/monitor" element={<MonitorPage status={status} conn={conn} />} />
            <Route path="/sim" element={<SimPage status={status} />} />
            <Route path="/admin" element={<AdminPage />} />
            <Route path="/enroll" element={<EnrollPage />} />
            <Route path="*" element={<Navigate to="/kiosk" replace />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

function SystemSummary({
  conn,
  status,
  onRefresh,
}: {
  conn: "connecting" | "open" | "closed" | "error";
  status: GateStatus | null;
  onRefresh: () => void;
}) {
  const doors = status?.doors || {};
  const alarm = Boolean(status?.alarm_on);
  const vision = status?.vision;
  const stateLabel = humanState[status?.state || ""] || status?.state || "Unknown";
  const wsTone = conn === "open" ? "success" : conn === "connecting" ? "warning" : "danger";
  const people = vision?.people_count ?? 0;
  const visionTone = alarm ? "danger" : vision?.vision_state === "OK" ? "success" : vision?.vision_state ? "warning" : "muted";
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surfaceAlt px-3 py-2 text-xs uppercase tracking-wide text-muted">
      <div className="flex items-center gap-2">
        <StatusDot tone={wsTone} blink={conn === "connecting"} />
        <span className="text-white/80">Связь {conn}</span>
      </div>
      <Separator />
      <div className="flex items-center gap-2">
        <span className="text-white/80">{stateLabel}</span>
      </div>
      <Separator />
      <div className="flex items-center gap-2 text-white/80">
        <span>Door1 {doors.door1_closed === false ? "open" : doors.lock1_unlocked ? "unlocked" : "locked"}</span>
        <span className="text-muted">/</span>
        <span>Door2 {doors.door2_closed === false ? "open" : doors.lock2_unlocked ? "unlocked" : "locked"}</span>
      </div>
      <Separator />
      <div className="flex items-center gap-2">
        <Badge tone={visionTone as any}>
          Vision {vision?.vision_state || "OFF"} ({people})
        </Badge>
      </div>
      {alarm && (
        <Badge tone="danger" className="ml-2">
          Alarm
        </Badge>
      )}
      <Button variant="ghost" className="ml-auto text-[12px]" onClick={onRefresh}>
        Refresh
      </Button>
    </div>
  );
}

function StatusDot({ tone, blink }: { tone: "success" | "danger" | "warning"; blink?: boolean }) {
  const color =
    tone === "success" ? "bg-accent2" : tone === "warning" ? "bg-warning" : tone === "danger" ? "bg-danger" : "bg-muted";
  return <span className={`h-2.5 w-2.5 rounded-full ${color} ${blink ? "animate-pulse" : ""}`} />;
}

function Separator() {
  return <span className="h-4 w-[1px] bg-border" />;
}

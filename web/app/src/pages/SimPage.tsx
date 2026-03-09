import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Camera, DoorOpen, DoorClosed, Radar } from "lucide-react";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { HlsStream } from "../components/HlsStream";
import { api } from "../lib/api";
import type { GateStatus, SimState } from "../lib/types";

export function SimPage({ status }: { status?: GateStatus | null }) {
  const { data: sim, refetch, isFetching } = useQuery<SimState>({
    queryKey: ["sim-state"],
    queryFn: () => api.getSimState(),
  });
  const [streamDown, setStreamDown] = useState(false);

  const mutation = useMutation({
    mutationFn: ({ doorId, action }: { doorId: number; action: "open" | "close" }) => api.simAction(doorId, action),
    onSuccess: () => refetch(),
  });

  const doors = status?.doors || sim;
  const alarm = Boolean(status?.alarm_on);
  const door1Closed = doors?.door1_closed ?? true;
  const door2Closed = doors?.door2_closed ?? true;
  const cameraOk = status?.vision?.camera_ok !== false;
  const cameraDown = streamDown || !cameraOk;

  return (
    <div className="grid gap-4 lg:grid-cols-[1.4fr_0.6fr]">
      <Card className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Симуляция</p>
            <h2 className="text-2xl font-semibold">Комната, две двери, камера</h2>
            <p className="text-sm text-muted">Открывайте/закрывайте двери, чтобы увидеть реакцию камеры и тревоги.</p>
          </div>
          <Badge tone={alarm ? "danger" : "muted"}>{alarm ? "ALARM" : "Норма"}</Badge>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          <DoorControl
            title="Door 1"
            doorId={1}
            closed={door1Closed}
            unlocked={doors?.lock1_unlocked ?? false}
            onAction={(action) => mutation.mutate({ doorId: 1, action })}
            disabled={mutation.isPending || isFetching}
          />
          <DoorControl
            title="Door 2"
            doorId={2}
            closed={door2Closed}
            unlocked={doors?.lock2_unlocked ?? false}
            onAction={(action) => mutation.mutate({ doorId: 2, action })}
            disabled={mutation.isPending || isFetching}
          />
        </div>

        <FacilityDiagram door1Closed={door1Closed} door2Closed={door2Closed} cameraOk={cameraOk} />
      </Card>

      <div className="space-y-3">
        <Card className="space-y-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-muted">
              <Radar className="h-4 w-4" />
              <span>Камера / Vision</span>
            </div>
          </div>
          <div className="grid gap-2 text-sm text-white">
            <Line label="Людей" value={status?.vision?.people_count ?? 0} />
            <Line label="Vision state" value={status?.vision?.vision_state || "—"} />
            <Line label="Match" value={status?.vision?.match === undefined ? "—" : status?.vision?.match ? "OK" : "FAIL"} />
            <Line label="Door1" value={doors?.door1_closed === false ? "Открыта" : "Закрыта"} />
            <Line label="Door2" value={doors?.door2_closed === false ? "Открыта" : "Закрыта"} />
          </div>
        </Card>

        <Card className="space-y-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-muted">
              <Camera className="h-4 w-4" />
              <span>Camera feed</span>
            </div>
            <Badge tone={cameraDown ? "danger" : "success"}>{cameraDown ? "CAMERA DOWN" : "Live"}</Badge>
          </div>
          <div className="relative h-40 overflow-hidden rounded-xl border border-border bg-black">
            <HlsStream
              src="/streams/live0/index.m3u8"
              className="h-full"
              onFrame={() => setStreamDown(false)}
              onDisconnect={() => setStreamDown(true)}
              overlay={
                cameraDown ? (
                  <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/60 text-white">
                    CAMERA DOWN
                  </div>
                ) : null
              }
            />
          </div>
          <p className="text-xs text-muted">Uses backend HLS stream (same as Monitor/Kiosk).</p>
        </Card>
      </div>
    </div>
  );
}

function DoorControl({
  title,
  doorId,
  closed,
  unlocked,
  onAction,
  disabled,
}: {
  title: string;
  doorId: number;
  closed: boolean;
  unlocked: boolean;
  onAction: (action: "open" | "close") => void;
  disabled?: boolean;
}) {
  const tone = closed ? "muted" : "warning";
  return (
    <div className="rounded-xl border border-border bg-surfaceAlt p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-white">
          {closed ? <DoorClosed className="h-4 w-4" /> : <DoorOpen className="h-4 w-4" />}
          <span className="font-semibold">{title}</span>
        </div>
        <Badge tone={tone as any}>{closed ? "Закрыта" : "Открыта"}</Badge>
      </div>
      <div className="mt-3 flex gap-2">
        <Button size="sm" variant="subtle" disabled={disabled} onClick={() => onAction("open")} className="flex-1">
          Открыть
        </Button>
        <Button size="sm" variant="subtle" disabled={disabled} onClick={() => onAction("close")} className="flex-1">
          Закрыть
        </Button>
      </div>
      <p className="mt-2 text-xs text-muted">
        {unlocked ? "Замок разблокирован" : "Замок закрыт"} • {closed ? "Дверь закрыта" : "Дверь открыта"}
      </p>
    </div>
  );
}

function Line({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-surfaceAlt px-3 py-2">
      <span className="text-muted">{label}</span>
      <span className="font-semibold text-white">{value}</span>
    </div>
  );
}

function FacilityDiagram({ door1Closed, door2Closed, cameraOk }: { door1Closed: boolean; door2Closed: boolean; cameraOk: boolean }) {
  const door1Tone = door1Closed ? "#22c55e" : "#f59e0b";
  const door2Tone = door2Closed ? "#22c55e" : "#f59e0b";
  const cameraTone = cameraOk ? "#38bdf8" : "#ef4444";
  const cameraFill = cameraOk ? "rgba(56,189,248,0.20)" : "rgba(239,68,68,0.12)";
  const cameraStroke = cameraOk ? "rgba(56,189,248,0.55)" : "rgba(239,68,68,0.55)";

  return (
    <div className="rounded-xl border border-border bg-surfaceAlt p-3">
      <div className="flex items-center justify-between">
        <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Layout</p>
        <span className="text-xs text-muted">Door1 / Door2 / Camera</span>
      </div>
      <svg viewBox="0 0 420 220" className="mt-3 h-44 w-full">
        <rect x="30" y="40" width="360" height="140" rx="18" fill="rgba(2,6,23,0.35)" stroke="rgba(148,163,184,0.25)" />
        <rect x="85" y="50" width="250" height="120" rx="14" fill="rgba(15,23,42,0.55)" stroke="rgba(148,163,184,0.25)" />

        <rect x="70" y="92" width="18" height="56" rx="4" fill={door1Tone} />
        <text x="78" y="88" textAnchor="middle" fontSize="12" fill="rgba(226,232,240,0.95)">
          D1
        </text>

        <rect x="332" y="92" width="18" height="56" rx="4" fill={door2Tone} />
        <text x="341" y="88" textAnchor="middle" fontSize="12" fill="rgba(226,232,240,0.95)">
          D2
        </text>

        <polygon points="345,70 180,46 180,174" fill={cameraFill} stroke={cameraStroke} strokeWidth="2" />
        <circle cx="345" cy="70" r="8" fill={cameraTone} />
        <text x="355" y="74" fontSize="12" fill="rgba(226,232,240,0.95)">
          CAM
        </text>

        <text x="210" y="206" textAnchor="middle" fontSize="12" fill="rgba(148,163,184,0.9)">
          Camera near Door2, FOV towards mantrap
        </text>
      </svg>
      <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>Door1: {door1Closed ? "closed" : "open"}</span>
        <span className="text-border">/</span>
        <span>Door2: {door2Closed ? "closed" : "open"}</span>
        <span className="text-border">/</span>
        <span>Camera: {cameraOk ? "OK" : "DOWN"}</span>
      </div>
    </div>
  );
}

import { useMemo, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { z } from "zod";
import { AlertTriangle, Lock, Unlock } from "lucide-react";
import { Card } from "../components/ui/card";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { HlsStream } from "../components/HlsStream";
import { api } from "../lib/api";
import { normalizeError } from "../lib/errors";
import type { GateStatus } from "../lib/types";

const pinSchema = z.string().regex(/^[0-9]{4}$/, "Введите 4 цифры");

export function KioskPage({ status }: { status?: GateStatus | null }) {
  const [pin, setPin] = useState("");
  const [info, setInfo] = useState<string | null>(null);
  const [streamDown, setStreamDown] = useState(false);

  const mutation = useMutation({
    mutationFn: (value: string) => api.kioskPin(value),
    onSuccess: () => {
      setInfo("Door1 открыта — войдите");
      setPin("");
    },
    onError: (err) => {
      const e = normalizeError(err);
      setInfo(e.message);
    },
  });

  const keypad = useMemo(() => ["1", "2", "3", "4", "5", "6", "7", "8", "9", "C", "0", "⌫"], []);
  const doors = status?.doors || {};
  const alarm = Boolean(status?.alarm_on);
  const vision = status?.vision;
  const cameraOk = vision?.camera_ok !== false;
  const peopleCount = vision?.people_count ?? 0;
  const visionState = vision?.vision_state || "OFF";
  const message = buildMessage(status, visionState, alarm, peopleCount, info);
  const cameraDown = streamDown || !cameraOk;

  return (
    <div className="grid gap-4 lg:grid-cols-[1.1fr_0.9fr]">
      <Card>
        <div className="flex flex-col gap-4">
          <div className="flex items-start justify-between">
            <div>
              <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Kiosk</p>
              <h1 className="text-2xl font-semibold">Ввод PIN для Door1</h1>
              <p className="text-sm text-muted">Введите 4-значный PIN, дверь 1 разблокируется, камера проверяет людей.</p>
            </div>
            <Badge tone={alarm ? "danger" : "muted"}>{alarm ? "ALARM" : visionState}</Badge>
          </div>

          <div className="grid gap-3 rounded-xl border border-border bg-surfaceAlt p-4">
            <Input
              id="pin-input"
              type="password"
              inputMode="numeric"
              autoFocus
              maxLength={4}
              value={pin}
              placeholder="____"
              onChange={(e) => setPin(e.target.value.replace(/\\D/g, "").slice(0, 4))}
              onKeyDown={(e) => {
                if (e.key === "Enter") submitPin(pin, setPin, mutation, setInfo);
              }}
              className="text-2xl tracking-[0.5em] text-center"
            />
            <div className="grid grid-cols-3 gap-2">
              {keypad.map((k) => (
                <Button
                  key={k}
                  variant="subtle"
                  className="h-14 text-lg"
                  disabled={mutation.isPending}
                  onClick={() => {
                    if (k === "C") {
                      setPin("");
                      setInfo(null);
                      return;
                    }
                    if (k === "⌫") {
                      setPin((p) => p.slice(0, -1));
                      return;
                    }
                    setPin((p) => (p + k).replace(/\\D/g, "").slice(0, 4));
                  }}
                >
                  {k}
                </Button>
              ))}
            </div>
            <div className="flex items-center justify-between gap-2">
              <div className="text-sm text-muted">{message}</div>
              <Button onClick={() => submitPin(pin, setPin, mutation, setInfo)} loading={mutation.isPending} className="px-6">
                Ввод
              </Button>
            </div>
          </div>
        </div>
      </Card>

      <div className="space-y-3">
        <Card>
          <div className="flex items-center justify-between">
            <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Двери</p>
            {alarm ? (
              <Badge tone="danger" className="flex items-center gap-1">
                <AlertTriangle className="h-3.5 w-3.5" />
                ALARM
              </Badge>
            ) : (
              <Badge tone="muted">Норма</Badge>
            )}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-3">
            <DoorCard title="Door 1" doors={doors} doorId={1} alarm={alarm} />
            <DoorCard title="Door 2" doors={doors} doorId={2} alarm={alarm} />
          </div>
        </Card>

        <Card className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Камера шлюза</p>
            <Badge tone={cameraDown ? "danger" : visionState === "OFF" ? "muted" : "success"}>
              {cameraDown ? "CAMERA DOWN" : "Live"}
            </Badge>
          </div>
          <div className="relative h-48 overflow-hidden rounded-xl border border-border bg-black">
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
          <p className="text-xs text-muted">Серверный HLS. Браузерная камера не используется.</p>
        </Card>

        <Card className="space-y-2">
          <div className="flex items-center justify-between">
            <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Видеостатус</p>
            <Badge tone={visionState === "ALARM" ? "danger" : visionState === "OFF" ? "muted" : "success"}>{visionState}</Badge>
          </div>
          <div className="space-y-2 text-sm text-muted">
            <LineItem label="Людей" value={peopleCount} />
            <LineItem label="Состояние" value={visionState} />
            <LineItem label="Матч" value={vision?.match === undefined ? "—" : vision?.match ? "OK" : "FAIL"} />
          </div>
        </Card>
      </div>
    </div>
  );
}

function submitPin(
  pin: string,
  setPin: (v: string) => void,
  mutation: ReturnType<typeof useMutation>,
  setInfo: (v: string | null) => void,
) {
  const parsed = pinSchema.safeParse(pin);
  if (!parsed.success) {
    setInfo(parsed.error.errors[0].message);
    return;
  }
  mutation.mutate(parsed.data);
}

function buildMessage(
  status: GateStatus | null | undefined,
  visionState: string,
  alarm: boolean,
  peopleCount: number,
  info: string | null,
): string {
  if (info) return info;
  if (!status) return "Ожидание PIN";
  if (alarm) return "ALARM: >1 человек при закрытых дверях";
  if (status.state === "IDLE") return "Ожидание PIN";
  if (status.state === "WAIT_ENTER") return "Door1 открыта — войдите";
  if (status.state === "CHECK_ROOM") {
    if (visionState === "DECIDING") return "DECIDING: проверка условий…";
    return "DETECTING: ищу лица…";
  }
  if (status.state === "ACCESS_GRANTED") return "OK: доступ разрешён";
  return `Состояние: ${status.state}${peopleCount ? `, людей: ${peopleCount}` : ""}`;
}

function DoorCard({ title, doors, doorId, alarm }: { title: string; doors: any; doorId: 1 | 2; alarm: boolean }) {
  const open = doorId === 1 ? doors.door1_closed === false : doors.door2_closed === false;
  const unlocked = doorId === 1 ? Boolean(doors.lock1_unlocked) : Boolean(doors.lock2_unlocked);
  const tone = alarm ? "danger" : open ? "warning" : unlocked ? "success" : "default";
  const icon = open ? <Unlock className="h-4 w-4" /> : <Lock className="h-4 w-4" />;
  return (
    <div className="rounded-xl border border-border bg-surfaceAlt p-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-white">
          {icon}
          <span className="font-semibold">{title}</span>
        </div>
        <Badge tone={tone as any}>{open ? "Открыта" : unlocked ? "Разблок" : "Закрыта"}</Badge>
      </div>
      <div className="mt-3 h-2 rounded-full bg-surface">
        <div
          className={`h-2 rounded-full transition-all ${
            tone === "danger"
              ? "bg-danger w-full"
              : open
                ? "bg-warning w-4/5"
                : unlocked
                  ? "bg-success w-3/5"
                  : "bg-muted w-2/5"
          }`}
        />
      </div>
    </div>
  );
}

function LineItem({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-surfaceAlt px-3 py-2">
      <span className="text-muted">{label}</span>
      <span className="font-semibold text-white">{value}</span>
    </div>
  );
}

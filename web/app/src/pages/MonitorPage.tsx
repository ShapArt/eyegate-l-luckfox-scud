import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle, Camera, DoorOpen, Info, PlugZap, Radio, Users } from "lucide-react";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import type { AppConfig, CameraHealth, GateStatus, VisionBox, VisionFace } from "../lib/types";
import { api } from "../lib/api";
import { formatTimestamp, humanState } from "../lib/utils";
import { HlsStream } from "../components/HlsStream";

interface MonitorProps {
  status?: GateStatus | null;
  conn: string;
}

type UserDirectory = Record<number, { name: string; login: string }>;
type OverlayFace = { box: VisionBox; user_id: number | null; score: number | null; label?: string | null; is_known?: boolean | null };

const UNKNOWN_LABEL = "UNKNOWN";

function faceLabel(userId: number | null, users: UserDirectory): string {
  if (userId === null) return UNKNOWN_LABEL;
  const user = users[userId];
  if (!user) return UNKNOWN_LABEL;
  return user.name || user.login || UNKNOWN_LABEL;
}

export function MonitorPage({ status, conn }: MonitorProps) {
  const [events, setEvents] = useState<string[]>([]);
  const [streamNonce, setStreamNonce] = useState(() => Date.now());
  const [streamDown, setStreamDown] = useState(false);
  const [frameSize, setFrameSize] = useState({ naturalWidth: 0, naturalHeight: 0, clientWidth: 0, clientHeight: 0 });
  const [users, setUsers] = useState<UserDirectory>({});
  const [debugOverlay, setDebugOverlay] = useState(true);
  const [appConfig, setAppConfig] = useState<AppConfig | null>(null);
  const [cameraHealth, setCameraHealth] = useState<CameraHealth | null>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const vision = status?.vision;
  const peopleCount = vision?.people_count ?? 0;
  const visionState = vision?.vision_state || "OFF";
  const alarm = Boolean(status?.alarm_on);
  const fps = vision?.fps ?? 0;
  const lastTs = vision?.last_frame_ts ? new Date(vision.last_frame_ts * 1000).toISOString() : null;
  const silhouettes = (vision?.silhouettes || []) as VisionBox[];
  const door1Closed = status?.doors?.door1_closed !== false;
  const door2Closed = status?.doors?.door2_closed !== false;
  const sensor1Open = status?.doors?.sensor1_open === true;
  const sensor2Open = status?.doors?.sensor2_open === true;
  const lock1Unlocked = Boolean(status?.doors?.lock1_unlocked);
  const lock2Unlocked = Boolean(status?.doors?.lock2_unlocked);
  const door2Unlocked = Boolean(status?.doors?.lock2_unlocked);
  const door2Open = status?.doors?.door2_closed === false;
  const door2Ready = status?.state === "ACCESS_GRANTED" || door2Unlocked || door2Open;
  const faceMatch = vision?.match;
  const matchDistance = vision?.match_distance;
  const matchedUserId = vision?.matched_user_id;
  const recognizedIds = (vision?.recognized_user_ids || []).filter(
    (id): id is number => typeof id === "number",
  );
  const policy = status?.policy;
  const cameraOk = vision?.camera_ok !== false;
  const healthOk = cameraHealth?.ok !== false;
  const cameraError = streamDown || !cameraOk || !healthOk || (vision ? visionState === "OFF" || Boolean(vision?.vision_error) : false);
  const hlsSrc = useMemo(() => {
    const base = appConfig?.camera_hls_url || "/streams/live0/index.m3u8";
    const joiner = base.includes("?") ? "&" : "?";
    return `${base}${joiner}nonce=${streamNonce}`;
  }, [appConfig, streamNonce]);

  const faces = useMemo<OverlayFace[]>(() => {
    if (!vision) return [];
    const boxes = vision.boxes || [];
    const facesRaw = (vision.faces || []) as VisionFace[];
    if (facesRaw.length) {
      return facesRaw
        .map((f, idx) => ({
          box: f?.box || boxes[idx],
          user_id: f?.user_id ?? null,
          score: f?.score ?? (vision.recognized_scores?.[idx] ?? null),
          label: f?.label ?? null,
          is_known: f?.is_known ?? null,
        }))
        .filter((f) => Boolean(f.box)) as OverlayFace[];
    }
    return boxes.map((box, idx) => ({
      box,
      user_id: vision.recognized_user_ids?.[idx] ?? null,
      score: vision.recognized_scores?.[idx] ?? null,
      label: null,
      is_known: null,
    }));
  }, [vision]);

  useEffect(() => {
    let active = true;
    api
      .getConfig()
      .then((cfg) => {
        if (active) setAppConfig(cfg);
      })
      .catch((err) => {
        console.warn("Failed to load config", err);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const health = await api.getCameraHealth();
        if (active) setCameraHealth(health);
      } catch (err) {
        if (active) {
          setCameraHealth((prev) =>
            prev ? { ...prev, ok: false, error: "HEALTH CHECK FAILED" } : { ok: false, url: "", error: "HEALTH CHECK FAILED" },
          );
        }
      }
    };
    poll();
    const timer = window.setInterval(poll, 3000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const loadUsers = useCallback(async () => {
    try {
      const list = await api.listUsers();
      const map: UserDirectory = {};
      list.forEach((u) => {
        map[u.id] = { name: u.name, login: u.login };
      });
      setUsers(map);
    } catch (err) {
      console.warn("Failed to load users", err);
    }
  }, []);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    if (!cameraOk) {
      setStreamDown(true);
    }
    if (!vision) return;
    const ids = new Set<number>();
    if (vision.matched_user_id != null) ids.add(vision.matched_user_id);
    (vision.recognized_user_ids || []).forEach((id) => {
      if (typeof id === "number") ids.add(id);
    });
    (vision.faces || []).forEach((f) => {
      if (f?.user_id != null) ids.add(f.user_id);
    });
    const missing = Array.from(ids).some((id) => users[id] === undefined);
    if (missing) {
      loadUsers();
    }
  }, [vision, users, loadUsers]);

  useEffect(() => {
    if (status?.last_event) {
      setEvents((prev) => [status.last_event as string, ...prev].slice(0, 30));
    }
    if (visionState) {
      setEvents((prev) => [`Vision: ${visionState} (people=${peopleCount})`, ...prev].slice(0, 30));
    }
  }, [status?.last_event, visionState, peopleCount]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = video.getBoundingClientRect();
    const displayW = rect.width || frameSize.clientWidth || video.clientWidth || video.videoWidth || 1;
    const displayH = rect.height || frameSize.clientHeight || video.clientHeight || video.videoHeight || 1;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = Math.round(displayW * dpr);
    canvas.height = Math.round(displayH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, displayW, displayH);

    if (!debugOverlay) return;
    const frameW = vision?.frame_w || frameSize.naturalWidth || video.videoWidth || displayW;
    const frameH = vision?.frame_h || frameSize.naturalHeight || video.videoHeight || displayH;
    if (!frameW || !frameH) return;

    const fit = window.getComputedStyle(video).objectFit || "fill";
    let scaleX = displayW / frameW;
    let scaleY = displayH / frameH;
    let offsetX = 0;
    let offsetY = 0;
    if (fit === "contain" || fit === "cover" || fit === "scale-down") {
      const scale = fit === "contain" || fit === "scale-down" ? Math.min(scaleX, scaleY) : Math.max(scaleX, scaleY);
      const drawnW = frameW * scale;
      const drawnH = frameH * scale;
      offsetX = (displayW - drawnW) / 2;
      offsetY = (displayH - drawnH) / 2;
      scaleX = scale;
      scaleY = scale;
    }

    const normalizeBox = (box: VisionBox): VisionBox => {
      const norm =
        box.x >= 0 &&
        box.y >= 0 &&
        box.w >= 0 &&
        box.h >= 0 &&
        box.x <= 1 &&
        box.y <= 1 &&
        box.w <= 1 &&
        box.h <= 1;
      if (!norm) return box;
      return { x: box.x * frameW, y: box.y * frameH, w: box.w * frameW, h: box.h * frameH, score: box.score };
    };

    const toDisplayRect = (box: VisionBox) => {
      const b = normalizeBox(box);
      return {
        x: offsetX + b.x * scaleX,
        y: offsetY + b.y * scaleY,
        w: b.w * scaleX,
        h: b.h * scaleY,
      };
    };

    if (silhouettes.length) {
      ctx.save();
      ctx.setLineDash([6, 4]);
      ctx.strokeStyle = "rgba(56, 189, 248, 0.95)";
      ctx.lineWidth = 2;
      silhouettes.forEach((box) => {
        const r = toDisplayRect(box);
        ctx.strokeRect(r.x, r.y, r.w, r.h);
      });
      ctx.restore();
    }

    if (!faces.length) return;

    faces.forEach((face) => {
      const box = face.box;
      if (!box) return;
      const r = toDisplayRect(box);
      const userId = face.user_id ?? null;
      const payloadLabel = face.label && face.label.trim().length ? face.label.trim() : null;
      const label = payloadLabel && payloadLabel !== UNKNOWN_LABEL ? payloadLabel : faceLabel(userId, users);
      const known = face.is_known === true || label !== UNKNOWN_LABEL;
      const tone = known ? "#22c55e" : "#ef4444";

      ctx.strokeStyle = tone;
      ctx.lineWidth = 2;
      ctx.strokeRect(r.x, r.y, r.w, r.h);

      ctx.font = "12px 'Inter', system-ui, -apple-system, sans-serif";
      const scoreText = face.score != null ? ` (${face.score.toFixed(2)})` : "";
      const text = `${label}${scoreText}`;
      const metrics = ctx.measureText(text);
      const paddingX = 6;
      const paddingY = 4;
      const textW = metrics.width + paddingX * 2;
      const textH = 16 + paddingY;
      const labelX = r.x;
      const labelY = Math.max(textH + 2, r.y + 4);

      ctx.fillStyle = "rgba(15,23,42,0.8)";
      ctx.fillRect(labelX, labelY - textH, textW, textH);
      ctx.strokeStyle = tone;
      ctx.strokeRect(labelX, labelY - textH, textW, textH);
      ctx.fillStyle = tone;
      ctx.fillText(text, labelX + paddingX, labelY - paddingY);
    });
  }, [faces, silhouettes, frameSize, users, vision?.frame_w, vision?.frame_h, debugOverlay]);

  useEffect(() => {
    const updateSize = () => {
      const video = videoRef.current;
      if (!video) return;
      setFrameSize((prev) => ({
        naturalWidth: video.videoWidth || prev.naturalWidth,
        naturalHeight: video.videoHeight || prev.naturalHeight,
        clientWidth: video.clientWidth || prev.clientWidth,
        clientHeight: video.clientHeight || prev.clientHeight,
      }));
    };
    window.addEventListener("resize", updateSize);
    return () => window.removeEventListener("resize", updateSize);
  }, []);

  return (
    <div className="grid gap-4 lg:grid-cols-[2fr_1fr]">
      <Card className="relative overflow-hidden">
        <div className="flex flex-col gap-3 pb-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Monitor</p>
            <h2 className="text-2xl font-semibold">Live doors, vision, alarms</h2>
            <p className="text-sm text-muted">Backend HLS stream + live status. No browser camera.</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone={!cameraError ? "success" : "danger"} className="flex items-center gap-1">
              <Camera className="h-3.5 w-3.5" />
              {!cameraError ? "Stream active" : "Camera down"}
            </Badge>
            <Badge tone={healthOk ? "success" : "danger"} className="flex items-center gap-1">
              <Radio className="h-3.5 w-3.5" />
              RTSP {healthOk ? "OK" : "down"}
            </Badge>
            <Badge tone={conn === "open" ? "success" : conn === "connecting" ? "warning" : "danger"} className="flex items-center gap-1">
              <PlugZap className="h-3.5 w-3.5" />
              WS {conn}
            </Badge>
            <button
              type="button"
              className={`rounded-full border px-3 py-1 text-xs ${debugOverlay ? "border-accent text-white" : "border-border text-muted"}`}
              onClick={() => setDebugOverlay((v) => !v)}
            >
              Debug overlay {debugOverlay ? "ON" : "OFF"}
            </button>
          </div>
        </div>

        <div className="flex flex-col items-center gap-3 rounded-2xl border border-border bg-surfaceAlt/60 px-4 py-5">
          <div className="relative h-64 w-full max-w-2xl overflow-hidden rounded-2xl border border-border bg-black shadow-card">
            <HlsStream
              src={hlsSrc}
              videoClassName="h-full w-full object-cover"
              videoRef={videoRef}
              onFrame={(info) => {
                setStreamDown(false);
                setFrameSize(info);
              }}
              onDisconnect={() => setStreamDown(true)}
              overlay={
                <>
                  <canvas ref={canvasRef} className="pointer-events-none absolute inset-0" />
                  <div className="pointer-events-none absolute inset-0 rounded-2xl ring-1 ring-accent/50" />
                  <div className="absolute left-3 top-3 flex items-center gap-2 rounded-full bg-surface/80 px-3 py-1 text-xs text-white backdrop-blur">
                    <Users className="h-3.5 w-3.5" />
                    {peopleCount} people
                  </div>
                  <div className="absolute right-3 bottom-3 flex items-center gap-2 rounded-full bg-surface/80 px-3 py-1 text-xs text-white backdrop-blur">
                    <Camera className="h-3.5 w-3.5" />
                    {visionState}
                  </div>
                  {cameraError && (
                    <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-2xl bg-danger/30 text-lg font-semibold text-white">
                      <AlertTriangle className="mr-2 h-5 w-5" />
                      CAMERA DOWN
                    </div>
                  )}
                  {alarm && (
                    <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-2xl bg-danger/20 text-lg font-semibold text-white">
                      <AlertTriangle className="mr-2 h-5 w-5" />
                      ALARM
                    </div>
                  )}
                </>
              }
            />
          </div>

          <div className="flex flex-wrap items-center justify-center gap-2 text-xs">
            <Badge tone={faceMatch === undefined || faceMatch === null ? "warning" : faceMatch ? "success" : "danger"}>
              Face: {faceMatch === undefined || faceMatch === null ? "pending" : faceMatch ? "match" : "no match"}
            </Badge>
            <Badge tone="muted">Distance: {matchDistance !== undefined && matchDistance !== null ? matchDistance.toFixed(2) : "n/a"}</Badge>
            <Badge tone="muted">Match user: {matchedUserId ?? "n/a"}</Badge>
            {recognizedIds.length > 0 && <Badge tone="success">Recognized IDs: {recognizedIds.join(", ")}</Badge>}
          </div>

          {door2Ready && (
            <div className="flex items-center gap-2 rounded-full border border-accent/60 bg-accent/15 px-3 py-1 text-sm text-white">
              <DoorOpen className="h-4 w-4" />
              Door2 ready (policy passed)
            </div>
          )}

          <div className="flex flex-wrap items-center justify-center gap-3 text-xs text-muted">
            <span>Door1 {door1Closed ? "closed" : "open"}</span>
            <span className="text-border">/</span>
            <span>Door2 {door2Closed ? "closed" : "open"}</span>
            <span className="text-border">/</span>
            <span>Sensors: D1 {sensor1Open ? "OPEN" : "closed"}, D2 {sensor2Open ? "OPEN" : "closed"}</span>
            <span className="text-border">/</span>
            <span>Locks: D1 {lock1Unlocked ? "unlocked" : "locked"}, D2 {lock2Unlocked ? "unlocked" : "locked"}</span>
            <button className="text-accent underline" onClick={() => setStreamNonce(Date.now())}>
              Reload stream
            </button>
          </div>
        </div>
      </Card>

      <div className="space-y-3">
        <Card>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Vision</p>
              <p className="text-lg font-semibold text-white">Live status</p>
            </div>
            <Badge tone={alarm ? "danger" : visionState === "OK" ? "success" : "warning"}>{visionState}</Badge>
          </div>
          <div className="mt-3 space-y-2 text-sm text-white">
            <Metric label="FSM state" value={humanState[status?.state || ""] || status?.state || "unknown"} />
            <Metric label="People" value={peopleCount} />
            <Metric label="FPS" value={fps.toFixed(1)} />
            <Metric label="Face match" value={faceMatch === undefined || faceMatch === null ? "pending" : faceMatch ? "OK" : "no"} />
            <Metric label="Distance" value={matchDistance !== undefined && matchDistance !== null ? matchDistance.toFixed(2) : "n/a"} />
            <Metric label="Matched user" value={matchedUserId ?? "n/a"} />
            <Metric label="Recognized IDs" value={recognizedIds.length ? recognizedIds.join(", ") : "n/a"} />
            <Metric label="Door1" value={status?.doors?.door1_closed === false ? "open" : "closed"} />
            <Metric label="Door2" value={status?.doors?.door2_closed === false ? "open" : "closed"} />
            <Metric label="Lock1" value={lock1Unlocked ? "UNLOCKED" : "locked"} />
            <Metric label="Lock2" value={lock2Unlocked ? "UNLOCKED" : "locked"} />
            <Metric label="Sensor1" value={sensor1Open ? "OPEN" : "closed"} />
            <Metric label="Sensor2" value={sensor2Open ? "OPEN" : "closed"} />
            <Metric label="Last frame" value={lastTs ? formatTimestamp(lastTs) : "n/a"} />
          </div>
          <div className="mt-4">
            <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Faces</p>
            <div className="mt-2 space-y-2">
              {faces.length === 0 && <p className="text-sm text-muted">No faces detected.</p>}
              {faces.map((face, idx) => {
                const userId = face.user_id ?? null;
                const payloadLabel = face.label && face.label.trim().length ? face.label.trim() : null;
                const label = payloadLabel && payloadLabel !== UNKNOWN_LABEL ? payloadLabel : faceLabel(userId, users);
                const score = face.score !== null && face.score !== undefined ? face.score.toFixed(2) : "n/a";
                return (
                  <div key={`${userId ?? "unknown"}-${idx}`} className="flex items-center justify-between rounded-lg border border-border bg-surfaceAlt px-3 py-2 text-sm">
                    <div>
                      <p className="font-semibold text-white">{label}</p>
                      <p className="text-[12px] text-muted">Score {score}</p>
                    </div>
                    <Badge tone={label === UNKNOWN_LABEL ? "danger" : "success"}>{userId ?? "?"}</Badge>
                  </div>
                );
              })}
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2 text-muted">
              <Radio className="h-3.5 w-3.5" />
              <span>Event feed</span>
            </div>
            <Badge tone="muted">{events.length}</Badge>
          </div>
          <div className="mt-3 max-h-80 space-y-2 overflow-auto text-xs text-white/80">
            {events.map((e, idx) => (
              <div key={`${e}-${idx}`} className="rounded-lg border border-border bg-surfaceAlt px-3 py-2">
                {e}
              </div>
            ))}
            {events.length === 0 && <p className="text-muted">No events yet.</p>}
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-2">
            <Info className="h-4 w-4 text-muted" />
            <div>
              <p className="text-[12px] uppercase tracking-[0.16em] text-muted">Policy</p>
              <p className="text-sm text-white">
                MAX {policy?.max_people_allowed ?? 1}, multi-known {policy?.allow_multi_known ? "allowed" : "blocked"}, face match{" "}
                {policy?.require_face_match_for_door2 ? "required" : "optional"}
              </p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border bg-surfaceAlt px-3 py-2">
      <span className="text-muted">{label}</span>
      <span className="font-semibold text-white">{value}</span>
    </div>
  );
}

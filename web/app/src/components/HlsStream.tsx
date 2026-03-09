import { useEffect, useMemo, useRef, useState } from "react";
import Hls from "hls.js";
import { getApiBase } from "../lib/api";

interface HlsStreamProps {
  src?: string;
  className?: string;
  videoClassName?: string;
  overlay?: React.ReactNode;
  videoRef?: React.RefObject<HTMLVideoElement>;
  onFrame?: (info: { naturalWidth: number; naturalHeight: number; clientWidth: number; clientHeight: number }) => void;
  onDisconnect?: () => void;
}

const DEFAULT_SRC = "/streams/live0/index.m3u8";

export function HlsStream({
  src = DEFAULT_SRC,
  className,
  videoClassName,
  overlay,
  videoRef,
  onFrame,
  onDisconnect,
}: HlsStreamProps) {
  const internalRef = useRef<HTMLVideoElement>(null);
  const [reloadKey, setReloadKey] = useState(() => Date.now());
  const [error, setError] = useState<string | null>(null);
  const retryTimerRef = useRef<number | null>(null);

  const resolvedSrc = useMemo(() => {
    const base = getApiBase();
    let full = src;
    if (!/^https?:\/\//i.test(src)) {
      const normalized = src.startsWith("/") ? src : `/${src}`;
      const origin = base || (typeof window !== "undefined" ? `${window.location.protocol}//${window.location.host}` : "http://localhost:8000");
      full = `${origin}${normalized}`;
    }
    try {
      const url = new URL(full);
      url.searchParams.set("_", String(reloadKey));
      return url.toString();
    } catch {
      return `${full}?_=${reloadKey}`;
    }
  }, [src, reloadKey]);

  useEffect(() => {
    const video = videoRef?.current || internalRef.current;
    if (!video) return;
    let hls: Hls | null = null;
    let closed = false;

    const reportFrame = () => {
      if (!video) return;
      onFrame?.({
        naturalWidth: video.videoWidth || 0,
        naturalHeight: video.videoHeight || 0,
        clientWidth: video.clientWidth || 0,
        clientHeight: video.clientHeight || 0,
      });
    };

    const scheduleRetry = () => {
      if (retryTimerRef.current !== null) return;
      retryTimerRef.current = window.setTimeout(() => {
        retryTimerRef.current = null;
        setReloadKey(Date.now());
      }, 2000);
    };

    const fail = (message: string) => {
      if (closed) return;
      setError(message);
      onDisconnect?.();
      scheduleRetry();
    };

    const play = () => {
      video.play().catch(() => {});
    };

    setError(null);
    video.addEventListener("loadedmetadata", reportFrame);

    if (Hls.isSupported()) {
      hls = new Hls({
        lowLatencyMode: true,
        backBufferLength: 30,
        maxBufferLength: 30,
      });
      hls.attachMedia(video);
      hls.on(Hls.Events.MEDIA_ATTACHED, () => {
        hls?.loadSource(resolvedSrc);
      });
      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) {
          fail("STREAM DISCONNECTED");
          hls?.destroy();
        }
      });
      hls.on(Hls.Events.MANIFEST_PARSED, play);
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      video.src = resolvedSrc;
      play();
    } else {
      fail("HLS not supported");
    }

    return () => {
      closed = true;
      video.removeEventListener("loadedmetadata", reportFrame);
      if (hls) {
        hls.destroy();
        hls = null;
      }
      if (retryTimerRef.current !== null) {
        window.clearTimeout(retryTimerRef.current);
        retryTimerRef.current = null;
      }
    };
  }, [resolvedSrc, videoRef, onFrame, onDisconnect]);

  return (
    <div className={`relative ${className ?? ""}`}>
      <video
        ref={videoRef || internalRef}
        className={videoClassName ?? "h-full w-full object-cover"}
        muted
        playsInline
        autoPlay
      />
      {overlay}
      {error && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/60">
          <div className="pointer-events-auto rounded-lg border border-border bg-surface/90 px-4 py-3 text-center shadow-card">
            <p className="text-sm font-semibold text-white">{error}</p>
            <button
              type="button"
              className="mt-2 rounded-md bg-accent px-3 py-1 text-xs font-semibold text-surface"
              onClick={() => setReloadKey(Date.now())}
            >
              Retry now
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

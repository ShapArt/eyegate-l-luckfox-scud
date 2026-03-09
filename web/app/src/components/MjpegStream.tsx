import { useEffect, useMemo, useRef, useState } from "react";
import { getApiBase } from "../lib/api";

interface MjpegStreamProps {
  src?: string;
  alt?: string;
  className?: string;
  imgClassName?: string;
  overlay?: React.ReactNode;
  imageRef?: React.RefObject<HTMLImageElement>;
  onFrame?: (info: { naturalWidth: number; naturalHeight: number; clientWidth: number; clientHeight: number }) => void;
  onDisconnect?: () => void;
}

const DEFAULT_SRC = "/api/video/mjpeg";

export function MjpegStream({
  src = DEFAULT_SRC,
  alt = "Camera stream",
  className,
  imgClassName,
  overlay,
  imageRef,
  onFrame,
  onDisconnect,
}: MjpegStreamProps) {
  const [reloadKey, setReloadKey] = useState(() => Date.now());
  const [error, setError] = useState<string | null>(null);
  const [retryDelay, setRetryDelay] = useState(1000);
  const retryRef = useRef<number | null>(null);

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
    return () => {
      if (retryRef.current) {
        clearTimeout(retryRef.current);
      }
    };
  }, []);

  const triggerReload = () => {
    setError(null);
    setRetryDelay(1000);
    setReloadKey(Date.now());
  };

  return (
    <div className={`relative ${className ?? ""}`}>
      <img
        key={reloadKey}
        ref={imageRef}
        src={resolvedSrc}
        alt={alt}
        className={imgClassName ?? "h-full w-full object-cover"}
        onLoad={(evt) => {
          setError(null);
          setRetryDelay(1000);
          const img = evt.currentTarget;
          onFrame?.({
            naturalWidth: img.naturalWidth || 0,
            naturalHeight: img.naturalHeight || 0,
            clientWidth: img.clientWidth || 0,
            clientHeight: img.clientHeight || 0,
          });
        }}
        onError={() => {
          setError("STREAM DISCONNECTED");
          onDisconnect?.();
          if (!retryRef.current) {
            retryRef.current = window.setTimeout(() => {
              retryRef.current = null;
              setReloadKey(Date.now());
              setRetryDelay((prev) => (prev === 1000 ? 2000 : 5000));
            }, retryDelay);
          }
        }}
      />
      {overlay}
      {error && (
        <div className="pointer-events-none absolute inset-0 flex items-center justify-center bg-black/60">
          <div className="pointer-events-auto rounded-lg border border-border bg-surface/90 px-4 py-3 text-center shadow-card">
            <p className="text-sm font-semibold text-white">{error}</p>
            <p className="text-xs text-muted">Auto-retry: {retryDelay / 1000}s</p>
            <button
              type="button"
              className="mt-2 rounded-md bg-accent px-3 py-1 text-xs font-semibold text-surface"
              onClick={triggerReload}
            >
              Retry now
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

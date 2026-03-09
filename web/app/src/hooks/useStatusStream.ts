import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, getApiBase } from "../lib/api";
import type { GateStatus } from "../lib/types";

type ConnState = "connecting" | "open" | "closed" | "error";

export function useStatusStream() {
  const [status, setStatus] = useState<GateStatus | null>(null);
  const [conn, setConn] = useState<ConnState>("connecting");
  const pollRef = useRef<number | null>(null);
  const wsUrl = useMemo(() => {
    const base = getApiBase();
    if (typeof window === "undefined") return "";
    try {
      if (base && base.startsWith("http")) {
        const u = new URL(base);
        u.protocol = u.protocol === "https:" ? "wss:" : "ws:";
        u.pathname = "/ws/status";
        u.search = "";
        u.hash = "";
        return u.toString();
      }
    } catch (err) {
      console.warn("Failed to build WS url from base", err);
    }
    const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${proto}//${window.location.host}/ws/status`;
  }, []);

  const startPolling = useCallback(() => {
    if (pollRef.current) return;
    pollRef.current = window.setInterval(async () => {
      try {
        const s = await api.getStatus();
        setStatus(s);
        setConn("closed");
      } catch (err) {
        console.error("poll status failed", err);
      }
    }, 2500);
  }, []);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  useEffect(() => {
    if (!wsUrl) return undefined;
    const ws = new WebSocket(wsUrl);
    let closed = false;

    ws.onopen = () => {
      setConn("open");
      stopPolling();
    };
    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data) as GateStatus;
        setStatus(data);
      } catch (err) {
        console.warn("WS parse error", err);
      }
    };
    ws.onerror = () => {
      setConn("error");
      startPolling();
    };
    ws.onclose = () => {
      if (!closed) {
        setConn("closed");
        startPolling();
      }
    };

    return () => {
      closed = true;
      ws.close();
      stopPolling();
    };
  }, [startPolling, stopPolling]);

  const refresh = useCallback(async () => {
    try {
      const s = await api.getStatus();
      setStatus(s);
    } catch (err) {
      console.error("status refresh failed", err);
    }
  }, []);

  return { status, conn, refresh };
}

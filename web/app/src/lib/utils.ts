import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
import type { GateStatus } from "./types";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatTimestamp(ts?: string | null) {
  if (!ts) return "-";
  const d = new Date(ts);
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export const humanState: Record<string, string> = {
  IDLE: "Waiting for PIN",
  WAIT_ENTER: "Door1 open",
  CHECK_ROOM: "Analyzing",
  ACCESS_GRANTED: "Access granted",
  ACCESS_DENIED: "Access denied",
  ALARM: "Alarm",
  RESET: "Reset",
};

export function stepHint(status?: GateStatus | null): string {
  if (!status) return "Waiting for PIN";
  switch (status.state) {
    case "IDLE":
      return "Enter PIN";
    case "WAIT_ENTER":
      return "Door1 unlocked ? proceed";
    case "CHECK_ROOM":
      return "Camera analyzing room";
    case "ACCESS_GRANTED":
      return "Door2 unlocked";
    case "ALARM":
      return "Alarm";
    default:
      return status.state;
  }
}

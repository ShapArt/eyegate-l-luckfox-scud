export type GateState =
  | "IDLE"
  | "WAIT_ENTER"
  | "CHECK_ROOM"
  | "ACCESS_GRANTED"
  | "ACCESS_DENIED"
  | "ALARM"
  | "RESET"
  | string;

export interface VisionBox {
  x: number;
  y: number;
  w: number;
  h: number;
  score?: number | null;
}

export interface VisionFace {
  box: VisionBox;
  user_id?: number | null;
  score?: number | null;
  label?: string | null;
  is_known?: boolean | null;
}

export interface VisionSnapshot {
  provider?: string | null;
  people_count: number;
  boxes?: VisionBox[];
  silhouettes?: VisionBox[];
  faces?: VisionFace[] | null;
  vision_state?: string | null;
  last_frame_ts?: number | null;
  fps?: number;
  vision_error?: string | null;
  match?: boolean | null;
  match_distance?: number | null;
  matched_user_id?: number | null;
  recognized_user_ids?: Array<number | null> | null;
  recognized_scores?: Array<number | null> | null;
  frame_w?: number | null;
  frame_h?: number | null;
  camera_ok?: boolean | null;
}

export interface DoorsState {
  door1_closed?: boolean | null;
  door2_closed?: boolean | null;
  lock1_unlocked?: boolean | null;
  lock2_unlocked?: boolean | null;
  lock1_power?: boolean | null;
  lock2_power?: boolean | null;
  sensor1_open?: boolean | null;
  sensor2_open?: boolean | null;
}

export interface GateStatus {
  state: GateState;
  current_card_id?: string | null;
  current_user_id?: number | null;
  doors?: DoorsState | null;
  alarm_on?: boolean | null;
  last_event?: string | null;
  vision?: VisionSnapshot | null;
  vision_required?: boolean | null;
  demo_mode?: boolean | null;
  timestamp?: string | null;
   policy?: {
     allow_multi_known?: boolean;
     max_people_allowed?: number;
     require_face_match_for_door2?: boolean;
   };
   room_samples?: any[];
}

export interface SimState {
  door1_closed: boolean;
  door2_closed: boolean;
  lock1_unlocked: boolean;
  lock2_unlocked: boolean;
  lock1_power?: boolean;
  lock2_power?: boolean;
  sensor1_open?: boolean;
  sensor2_open?: boolean;
  auto_close_ms?: number;
  door1_auto_close_ms?: number;
  door2_auto_close_ms?: number;
}

export interface VisionDummyState {
  people_count: number;
  face_match?: string | null;
  delay_ms: number;
}

export interface ApiError {
  code: string;
  message: string;
  details?: unknown;
  status?: number;
}

export interface EventRecord {
  id: number;
  timestamp: string;
  level: string;
  message: string;
  reason?: string | null;
  state?: string | null;
  card_id?: string | null;
  user_id?: number | null;
}

export interface UserRecord {
  id: number;
  name: string;
  login: string;
  card_id: string;
  access_level: number;
  is_blocked: boolean;
  status: string;
  role: string;
  approved_by?: number | null;
  approved_at?: string | null;
  has_face?: boolean;
}

export interface QuickUserPayload {
  login: string;
  pin: string;
  name?: string;
  access_level?: number;
  is_blocked?: boolean;
}

export interface AppConfig {
  camera_rtsp_url?: string | null;
  camera_hls_url?: string | null;
  health_camera_url?: string | null;
}

export interface CameraHealth {
  ok: boolean;
  url: string;
  error?: string | null;
  last_frame_ts?: number | null;
}

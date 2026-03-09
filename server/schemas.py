from __future__ import annotations

import datetime as dt
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class UserBase(BaseModel):
    name: str = Field(..., example="Demo User")
    login: str = Field(..., example="demo")
    card_id: str = Field(..., example="CARD123")
    access_level: int = Field(1, ge=1, le=10)
    is_blocked: bool = False
    role: str = Field("user", pattern="^(user|admin)$", description="Role of the user")


class UserCreate(UserBase):
    password: str = Field(..., min_length=4, example="demo1234")


class UserQuickCreate(BaseModel):
    login: str = Field(..., min_length=2)
    pin: str = Field(..., min_length=4, max_length=4, pattern="^[0-9]{4}$")
    name: Optional[str] = None
    access_level: int = Field(1, ge=1, le=10)
    is_blocked: bool = False


class UserUpdate(BaseModel):
    name: Optional[str] = None
    login: Optional[str] = None
    password: Optional[str] = Field(None, min_length=4)
    card_id: Optional[str] = None
    access_level: Optional[int] = Field(None, ge=1, le=10)
    is_blocked: Optional[bool] = None
    role: Optional[str] = Field(None, pattern="^(user|admin)$")


class UserOut(UserBase):
    id: int
    status: str = "active"
    approved_by: Optional[int] = None
    approved_at: Optional[dt.datetime] = None
    has_face: bool = False


class EventOut(BaseModel):
    id: int
    timestamp: dt.datetime
    level: str
    message: str
    reason: Optional[str]
    state: str
    card_id: Optional[str]
    user_id: Optional[int]


class EventsPage(BaseModel):
    items: List[EventOut]
    total: int


class VisionBox(BaseModel):
    x: float
    y: float
    w: float
    h: float
    score: Optional[float] = None


class VisionFace(BaseModel):
    box: VisionBox
    user_id: Optional[int] = None
    score: Optional[float] = None
    label: Optional[str] = None
    is_known: Optional[bool] = None


class VisionSnapshot(BaseModel):
    provider: Optional[str] = None
    people_count: int = Field(0)
    boxes: List[VisionBox] = Field(default_factory=list)
    faces: List[VisionFace] = Field(default_factory=list)
    silhouettes: List[VisionBox] = Field(default_factory=list)
    vision_state: Optional[str] = None
    last_frame_ts: Optional[float] = None
    fps: float = Field(0.0)
    vision_error: Optional[str] = None
    match: Optional[bool] = None
    match_distance: Optional[float] = None
    matched_user_id: Optional[int] = None
    recognized_user_ids: List[Optional[int]] = Field(default_factory=list)
    recognized_scores: List[Optional[float]] = Field(default_factory=list)
    frame_w: Optional[int] = None
    frame_h: Optional[int] = None
    camera_ok: Optional[bool] = None


class GateStatus(BaseModel):
    state: str
    current_card_id: Optional[str]
    current_user_id: Optional[int]
    doors: Optional[dict] = None
    alarm_on: Optional[bool] = None
    last_event: Optional[str] = None
    vision: Optional[VisionSnapshot] = None
    vision_required: Optional[bool] = None
    demo_mode: Optional[bool] = None
    timestamp: Optional[dt.datetime] = None


class SimState(BaseModel):
    door1_closed: bool
    door2_closed: bool
    lock1_unlocked: bool
    lock2_unlocked: bool
    lock1_power: Optional[bool] = None
    lock2_power: Optional[bool] = None
    sensor1_open: Optional[bool] = None
    sensor2_open: Optional[bool] = None
    auto_close_ms: Optional[int] = None
    door1_auto_close_ms: Optional[int] = None
    door2_auto_close_ms: Optional[int] = None


class VisionDummyState(BaseModel):
    people_count: int
    face_match: Optional[str]
    delay_ms: int


class RegisterRequest(BaseModel):
    name: str
    login: str
    card_id: str
    password: str = Field(..., min_length=4)
    password_confirm: str = Field(..., min_length=4)
    access_level: int = Field(1, ge=1, le=10)
    is_blocked: bool = False
    face_image_b64: Optional[str] = Field(
        default=None,
        description="Base64 data URL with face image (optional).",
    )
    face_embedding_b64: Optional[str] = Field(
        default=None,
        description="Serialized embedding in base64 (optional).",
    )


class LoginRequest(BaseModel):
    login: str
    password: str = Field(..., min_length=4)


class AdminLoginRequest(LoginRequest):
    """Same payload as LoginRequest but clarifies admin intent."""


class LoginResponse(BaseModel):
    status: str
    user_id: int
    state: str
    token: str
    role: str


class PinLoginRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=4, pattern="^[0-9]{4}$")


class FaceBox(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    x: float
    y: float
    w: float
    h: float
    score: Optional[float] = None


class BrowserFace(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    box: FaceBox
    descriptor: Optional[List[float]] = None


class BrowserBestMatch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: Optional[int] = Field(None, alias="userId")
    distance: Optional[float] = None
    login: Optional[str] = None


class BrowserVisionPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ts: Optional[float] = None
    people_count: int = Field(..., alias="peopleCount")
    faces: List[BrowserFace] = []
    best_match: Optional[BrowserBestMatch] = Field(None, alias="bestMatch")
    match: Optional[bool] = None


class VisionLastResponse(BaseModel):
    last: Optional[VisionSnapshot]


class FaceEnrollRequest(BaseModel):
    descriptor: List[float]

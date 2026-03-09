from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class BoundingBox:
    x: int
    y: int
    w: int
    h: int
    score: float | None = None


@dataclass
class DetectedFace:
    bbox: BoundingBox
    embedding: Optional[list[float]] = None
    match_user_id: Optional[int] = None
    score: Optional[float] = None


@dataclass
class VisionResult:
    people_count: int
    faces: List[DetectedFace] = field(default_factory=list)
    recognized_user_ids: List[int] = field(default_factory=list)
    camera_ok: bool = True
    debug: Optional[dict] = None

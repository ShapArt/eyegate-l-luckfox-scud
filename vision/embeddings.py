from __future__ import annotations

import hashlib
import math
from typing import Optional, Sequence


def compute_dummy_embedding(image_bytes: bytes) -> bytes:
    """Legacy hash-based embedding placeholder used for OpenCV/demo mode."""
    if not image_bytes:
        raise ValueError("Empty image data")
    return hashlib.sha256(image_bytes).digest()


def serialize_face_descriptor(values: Sequence[float]) -> bytes:
    """Serialize float descriptor to a compact ASCII blob for SQLite storage."""
    return ",".join(f"{v:.6f}" for v in values).encode()


def deserialize_face_descriptor(blob: Optional[bytes]) -> Optional[list[float]]:
    """Decode descriptor stored via serialize_face_descriptor back into floats."""
    if blob is None:
        return None
    try:
        text = blob.decode()
    except Exception:
        return None
    parts = [p for p in text.split(",") if p]
    try:
        return [float(p) for p in parts]
    except ValueError:
        return None


def descriptor_distance(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b):
        return math.inf
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


def are_embeddings_close(
    a: Optional[bytes],
    b: Optional[bytes | Sequence[float]],
    threshold: float = 0.1,
) -> bool:
    if a is None or b is None:
        return False
    if isinstance(b, (bytes, bytearray)):
        return a == b
    stored_vec = deserialize_face_descriptor(a)
    if stored_vec is None:
        return False
    return descriptor_distance(stored_vec, b) <= threshold


def distance_to_embedding(
    stored: Optional[bytes], candidate: Sequence[float]
) -> Optional[float]:
    """Return L2 distance between stored descriptor (if parsable) and candidate floats."""
    stored_vec = deserialize_face_descriptor(stored)
    if stored_vec is None:
        return None
    dist = descriptor_distance(stored_vec, candidate)
    if math.isinf(dist):
        return None
    return dist

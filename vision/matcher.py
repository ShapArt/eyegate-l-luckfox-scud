from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

from vision.embeddings import descriptor_distance, deserialize_face_descriptor


@dataclass
class MatchResult:
    user_id: Optional[int]
    distance: Optional[float]


def _cosine_distance(a: Sequence[float], b: Sequence[float]) -> float:
    if len(a) != len(b) or not a:
        return math.inf
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return math.inf
    # convert cosine similarity into distance-like value: smaller is better
    return 1.0 - (dot / (na * nb))


def best_match_for_embedding(
    candidate: Sequence[float],
    users: Iterable[object],
    threshold: float,
    metric: str = "l2",
) -> Optional[MatchResult]:
    """
    Compare candidate embedding with all users' stored descriptors.
    Returns best match within threshold (smaller distance is better).
    """
    best_uid: Optional[int] = None
    best_dist: float = math.inf
    for user in users:
        embedding = getattr(user, "face_embedding", None)
        if embedding is None:
            continue
        stored_vec = deserialize_face_descriptor(embedding)
        if stored_vec is None:
            continue
        if metric == "cosine":
            dist = _cosine_distance(candidate, stored_vec)
        else:
            dist = descriptor_distance(candidate, stored_vec)
        if math.isinf(dist):
            continue
        if dist < best_dist:
            best_dist = dist
            uid = getattr(user, "id", None)
            best_uid = uid if uid is not None else best_uid
    if best_dist <= threshold:
        return MatchResult(user_id=best_uid, distance=best_dist)
    return None

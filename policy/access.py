from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence


class PolicyAction(str, Enum):
    OPEN_DOOR2 = "open_door2"
    ALARM = "alarm"
    WAIT = "wait"
    DENY = "deny"


@dataclass
class PolicyDecision:
    action: PolicyAction
    reason: str


@dataclass
class PolicyConfig:
    allow_multi_known: bool = False
    require_face_match_for_door2: bool = True
    max_people_allowed: int = 1


def decide_access(
    people_count: int,
    recognized_user_ids: Sequence[int] | None,
    required_user_id: Optional[int] = None,
    config: PolicyConfig = PolicyConfig(),
) -> PolicyDecision:
    pc = max(0, int(people_count or 0))
    recognized = [int(uid) for uid in (recognized_user_ids or []) if uid is not None]

    if pc == 0:
        return PolicyDecision(PolicyAction.WAIT, "NO_PERSON")

    if pc > config.max_people_allowed:
        return PolicyDecision(PolicyAction.ALARM, "TOO_MANY_PEOPLE")

    if pc >= 2:
        if not config.allow_multi_known:
            return PolicyDecision(PolicyAction.ALARM, "MULTI_PERSON_BLOCKED")
        if len(recognized) < pc:
            return PolicyDecision(PolicyAction.ALARM, "UNKNOWN_IN_GROUP")
        if required_user_id is not None and required_user_id not in recognized:
            return PolicyDecision(PolicyAction.DENY, "REQUIRED_USER_MISMATCH")
        return PolicyDecision(PolicyAction.OPEN_DOOR2, "MULTI_KNOWN_ALLOWED")

    # pc == 1
    if config.require_face_match_for_door2 and not recognized:
        return PolicyDecision(PolicyAction.ALARM, "UNKNOWN_PERSON")

    if required_user_id is not None and required_user_id not in recognized:
        return PolicyDecision(PolicyAction.DENY, "REQUIRED_USER_MISMATCH")

    if not recognized and not config.require_face_match_for_door2:
        return PolicyDecision(PolicyAction.WAIT, "SINGLE_UNVERIFIED")

    return PolicyDecision(PolicyAction.OPEN_DOOR2, "SINGLE_RECOGNIZED")

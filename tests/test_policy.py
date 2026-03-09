from policy import PolicyAction, PolicyConfig, decide_access


def test_single_known_opens_with_required_user():
    decision = decide_access(
        people_count=1, recognized_user_ids=[42], required_user_id=42
    )
    assert decision.action is PolicyAction.OPEN_DOOR2
    assert decision.reason == "SINGLE_RECOGNIZED"


def test_single_unknown_triggers_alarm():
    decision = decide_access(people_count=1, recognized_user_ids=[])
    assert decision.action is PolicyAction.ALARM
    assert decision.reason == "UNKNOWN_PERSON"


def test_multi_person_with_unknown_triggers_alarm():
    cfg = PolicyConfig(max_people_allowed=3, allow_multi_known=False)
    decision = decide_access(people_count=2, recognized_user_ids=[7], config=cfg)
    assert decision.action is PolicyAction.ALARM
    assert decision.reason == "MULTI_PERSON_BLOCKED"


def test_multi_known_allowed_when_configured():
    cfg = PolicyConfig(allow_multi_known=True, max_people_allowed=3)
    decision = decide_access(people_count=2, recognized_user_ids=[1, 2], config=cfg)
    assert decision.action is PolicyAction.OPEN_DOOR2
    assert decision.reason == "MULTI_KNOWN_ALLOWED"


def test_required_user_mismatch_denies():
    cfg = PolicyConfig(allow_multi_known=True, max_people_allowed=2)
    decision = decide_access(
        people_count=2, recognized_user_ids=[1, 2], required_user_id=3, config=cfg
    )
    assert decision.action is PolicyAction.DENY
    assert decision.reason == "REQUIRED_USER_MISMATCH"


def test_too_many_people_triggers_alarm():
    cfg = PolicyConfig(max_people_allowed=1)
    decision = decide_access(people_count=3, recognized_user_ids=[1, 2, 3], config=cfg)
    assert decision.action is PolicyAction.ALARM
    assert decision.reason == "TOO_MANY_PEOPLE"


def test_single_unverified_waits_when_face_not_required():
    cfg = PolicyConfig(require_face_match_for_door2=False)
    decision = decide_access(people_count=1, recognized_user_ids=[], config=cfg)
    assert decision.action is PolicyAction.WAIT
    assert decision.reason == "SINGLE_UNVERIFIED"

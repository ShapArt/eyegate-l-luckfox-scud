import pytest

from auth.passwords import hash_password
from db import models
from vision.service import VisionDummyConfig, VisionServiceDummyControl


@pytest.mark.asyncio
async def test_dummy_vision_respects_env(monkeypatch):
    monkeypatch.setenv("VISION_DUMMY_PEOPLE", "2")
    monkeypatch.setenv("VISION_DUMMY_RECOGNIZED", "7,8")
    cfg = VisionDummyConfig.from_env()
    svc = VisionServiceDummyControl(dummy_cfg=cfg)

    result = await svc.analyze()

    assert result.people_count == 2
    assert result.recognized_user_ids == [7, 8]
    assert result.camera_ok is True


def test_dummy_snapshot_includes_faces_labels():
    svc = VisionServiceDummyControl()
    svc.set_values(people_count=1, face_match=None, recognized_user_ids=[5])
    snap = svc.last_snapshot()
    faces = snap.get("faces") or []
    assert len(faces) >= 1
    face = faces[0]
    assert face.get("user_id") == 5
    assert face.get("label")
    assert face.get("is_known") in (True, False)


def test_dummy_snapshot_uses_db_names(monkeypatch):
    # Ensure label resolves to name/login instead of "Face 1"
    uid = models.create_user(
        name="Alice",
        login="alice",
        password_hash=hash_password("secret"),
        card_id="CARD-1",
        access_level=1,
        is_blocked=False,
        face_embedding=None,
    )
    svc = VisionServiceDummyControl()
    svc.set_values(people_count=1, face_match=None, recognized_user_ids=[uid])
    snap = svc.last_snapshot()
    face = (snap.get("faces") or [])[0]
    assert face["label"] == "Alice"
    assert face["is_known"] is True

    # unknown id → UNKNOWN
    svc.set_values(people_count=1, face_match=None, recognized_user_ids=[999])
    snap2 = svc.last_snapshot()
    face2 = (snap2.get("faces") or [])[0]
    assert face2["label"] == "UNKNOWN"
    assert face2["is_known"] is False

from __future__ import annotations

from gate.models import FaceMatch
from server.deps import get_gate_controller


def test_status_includes_camera_flag_and_labels(client):
    ctrl = get_gate_controller()
    # Force dummy vision state: camera down + one unknown face
    ctrl._vision.set_values(people_count=1, face_match=FaceMatch.NO_FACE, recognized_user_ids=[], camera_ok=False)  # type: ignore[attr-defined]

    res = client.get("/api/status/")
    assert res.status_code == 200
    payload = res.json()
    vision = payload.get("vision") or {}
    assert vision.get("camera_ok") is False
    faces = vision.get("faces") or []
    if faces:
        assert all(f.get("label") for f in faces)
        assert all(f.get("label") != "Face 1" for f in faces)

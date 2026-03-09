from __future__ import annotations

import pytest

from server.api import video


class _StubVision:
    def get_jpeg_frame(self) -> bytes:
        return b"fake"


@pytest.mark.asyncio
async def test_mjpeg_content_type_header():
    """MJPEG endpoint must expose correct multipart boundary and content type."""
    resp = await video.video_mjpeg(vision=_StubVision())  # type: ignore[arg-type]
    ct = resp.media_type.lower() if resp.media_type else ""
    assert ct.startswith("multipart/x-mixed-replace")
    assert "boundary=frame" in ct


def test_mjpeg_endpoint_returns_stream(client):
    resp = client.get("/api/video/mjpeg?max_frames=1")
    assert resp.status_code == 200
    ct = (resp.headers.get("content-type") or "").lower()
    assert ct.startswith("multipart/x-mixed-replace")
    assert "boundary=frame" in ct
    assert b"--frame" in resp.content

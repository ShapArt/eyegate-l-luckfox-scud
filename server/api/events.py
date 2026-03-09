from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse

import server.deps as deps
from db import models as db_models
from server.api.common import fail
from server.schemas import EventOut

router = APIRouter()


@router.get("/", response_model=list[EventOut])
async def list_events(
    limit: int = Query(100, ge=1, le=1000),
    _: dict = Depends(deps.require_admin),
) -> list[EventOut]:
    events = db_models.get_events(limit=limit)
    return [
        EventOut(
            id=e.id,
            timestamp=e.timestamp,
            level=e.level,
            message=e.message,
            reason=e.reason,
            state=e.state,
            card_id=e.card_id,
            user_id=e.user_id,
        )
        for e in events
    ]


@router.get("/export")
async def export_events(
    format: str = Query("csv", pattern="^(csv|json)$"),
    limit: int = Query(1000, ge=1, le=10000),
    _: dict = Depends(deps.require_admin),
):
    """Export events as CSV or JSON (json = plain list)."""
    events = db_models.get_events(limit=limit)
    if format == "json":
        return [
            {
                "id": e.id,
                "timestamp": e.timestamp.isoformat(),
                "level": e.level,
                "message": e.message,
                "reason": e.reason,
                "state": e.state,
                "card_id": e.card_id,
                "user_id": e.user_id,
            }
            for e in events
        ]
    if format == "csv":
        header = [
            "id",
            "timestamp",
            "level",
            "message",
            "reason",
            "state",
            "card_id",
            "user_id",
        ]
        lines = [",".join(header)]
        for e in events:
            row = [
                str(e.id),
                e.timestamp.isoformat(),
                e.level or "",
                (e.message or "").replace(",", " "),
                (e.reason or ""),
                e.state or "",
                e.card_id or "",
                "" if e.user_id is None else str(e.user_id),
            ]
            lines.append(",".join(row))
        csv_data = "\n".join(lines)
        return PlainTextResponse(csv_data, media_type="text/csv")
    fail(400, "BAD_FORMAT", "Unsupported format")

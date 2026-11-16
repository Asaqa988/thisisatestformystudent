"""Ad videos: Claude writes a 15-second motion-graphic ad from the Knowledge Base;
the Campaigns page plays it and downloads it as a video."""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.errors import NotFound
from app.models import AdVideo
from app.services import ad_videos

router = APIRouter(prefix="/api/v1/ad-videos", tags=["ad videos"])


class AdVideoIn(BaseModel):
    brief: str | None = Field(None, max_length=500)


class AdVideoOut(BaseModel):
    id: uuid.UUID
    brief: str | None
    language: str
    aspect: str
    title: str
    status: str
    error: str | None
    storyboard: dict[str, Any]
    input_tokens: int
    output_tokens: int
    created_at: datetime


class AdVideoList(BaseModel):
    items: list[AdVideoOut]


def _out(ad: AdVideo) -> AdVideoOut:
    return AdVideoOut(
        id=ad.id,
        brief=ad.brief,
        language=ad.language,
        aspect=ad.aspect,
        title=ad.title,
        status=ad.status,
        error=ad.error,
        storyboard=ad.storyboard or {},
        input_tokens=ad.input_tokens,
        output_tokens=ad.output_tokens,
        created_at=ad.created_at,
    )


@router.post("", response_model=AdVideoOut, status_code=status.HTTP_202_ACCEPTED)
def create_ad(data: AdVideoIn, background: BackgroundTasks, db: Session = Depends(get_db)):
    """Claude writes the ad in the background (about 10-20 s). Poll GET /ad-videos/{id}."""
    ad = AdVideo(
        id=uuid.uuid4(),
        brief=(data.brief or "").strip() or None,
        title=(data.brief or "New ad").strip()[:80] or "New ad",
        status="building",
    )
    db.add(ad)
    db.commit()
    background.add_task(ad_videos.build_ad, ad.id)
    return _out(ad)


@router.get("", response_model=AdVideoList)
def list_ads(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    rows = db.scalars(select(AdVideo).order_by(AdVideo.created_at.desc()).limit(limit)).all()
    return AdVideoList(items=[_out(ad) for ad in rows])


@router.get("/{ad_id}", response_model=AdVideoOut)
def get_ad(ad_id: uuid.UUID, db: Session = Depends(get_db)):
    ad = db.get(AdVideo, ad_id)
    if ad is None:
        raise NotFound("That ad does not exist.")
    return _out(ad)


@router.delete("/{ad_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ad(ad_id: uuid.UUID, db: Session = Depends(get_db)):
    ad = db.get(AdVideo, ad_id)
    if ad is None:
        raise NotFound("That ad does not exist.")
    db.delete(ad)
    db.commit()

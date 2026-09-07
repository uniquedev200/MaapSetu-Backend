"""Health score, passport and blockchain output schemas."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


class HealthScoreOut(BaseModel):
    score: int
    category: str
    reason: Optional[str] = None
    computed_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PassportEventOut(BaseModel):
    id: int
    event_type: str
    title: str
    description: Optional[str] = None
    metadata: dict = {}
    actor: Optional[str] = None
    created_at: str

    model_config = ConfigDict(from_attributes=True)


class PassportOut(BaseModel):
    instrument: dict
    health_score: int
    health_category: str
    verification_summary: dict
    timeline: List[PassportEventOut]

    model_config = ConfigDict(from_attributes=True)


class BlockOut(BaseModel):
    index: int
    timestamp: str
    certificate_id: str
    certificate_hash: str
    previous_hash: str
    block_hash: str
    nonce: int
    chain_metadata: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)
"""Blockchain block persistence (certificate-hash anchoring).

Only SHA-256 hashes are stored — never certificate content. Blocks form an
append-only hash-linked chain that can be swapped for Hyperledger / Ethereum /
Polygon without touching business logic.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin

GENESIS_PREVIOUS_HASH = "0" * 64


class BlockchainBlock(Base, TimestampMixin):
    __tablename__ = "blockchain_blocks"
    __table_args__ = (Index("ix_blockchain_cert", "certificate_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    index: Mapped[int] = mapped_column(Integer, unique=True, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    certificate_id: Mapped[str] = mapped_column(String(40), index=True, nullable=False)
    certificate_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    previous_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    block_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    nonce: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    chain_metadata: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
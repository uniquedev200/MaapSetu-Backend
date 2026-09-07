"""Blockchain blocks repository."""

from typing import List, Optional

from sqlalchemy import func, select

from app.models.blockchain_block import BlockchainBlock
from app.repositories.base import BaseRepository


class BlockchainRepository(BaseRepository[BlockchainBlock]):
    model = BlockchainBlock

    def latest_block(self) -> Optional[BlockchainBlock]:
        stmt = select(BlockchainBlock).order_by(BlockchainBlock.index.desc()).limit(1)
        return self.db.execute(stmt).scalars().first()

    def get_by_index(self, index: int) -> Optional[BlockchainBlock]:
        return self.get_by(index=index)

    def get_by_certificate(self, certificate_id: str) -> Optional[BlockchainBlock]:
        stmt = (
            select(BlockchainBlock)
            .where(BlockchainBlock.certificate_id == certificate_id)
            .order_by(BlockchainBlock.index.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalars().first()

    def all_ordered(self) -> List[BlockchainBlock]:
        stmt = select(BlockchainBlock).order_by(BlockchainBlock.index.asc())
        return list(self.db.execute(stmt).scalars().all())

    def chain_count(self) -> int:
        return int(self.db.execute(select(func.count()).select_from(BlockchainBlock)).scalar_one())
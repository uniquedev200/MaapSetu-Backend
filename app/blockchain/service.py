"""Lightweight blockchain-backed certificate integrity module.

Design goals
------------
- Store ONLY the SHA-256 hash of each certificate PDF — never the content.
- Blocks are persisted in PostgreSQL (or SQLite locally) through the
  ``BlockchainRepository``.
- The ``BlockchainService`` exposes a small, stable contract
  (``genesis/ add_block/ verify_chain/ get_by_certificate/ validate``).
  Swapping to Hyperledger Fabric, Polygon or Ethereum only requires replacing
  this service implementation behind the same interface — business logic and
  endpoints remain unchanged.
"""

import hashlib
from datetime import datetime
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.blockchain_block import GENESIS_PREVIOUS_HASH, BlockchainBlock
from app.repositories.blockchain_repository import BlockchainRepository


class BlockchainService:
    """Hash-anchored, append-only integrity ledger stored in the database."""

    def __init__(self, db: Session):
        self.db = db
        self.repo = BlockchainRepository(db)
        self.settings = get_settings()

    # -- Public contract (stable across backend implementations) -----------
    def ensure_genesis(self) -> BlockchainBlock:
        """Create the genesis block if the chain is empty."""
        if self.repo.chain_count() == 0:
            genesis = self._build_block(
                index=0,
                timestamp=datetime.utcnow(),
                certificate_id="GENESIS",
                certificate_hash="0" * 64,
                previous_hash=GENESIS_PREVIOUS_HASH,
            )
            return self.repo.save(genesis)
        return self.repo.get_by_index(0)

    def add_block(self, certificate_id: str, certificate_hash: str) -> BlockchainBlock:
        """Append a new block anchoring ``certificate_hash`` for ``certificate_id``."""
        self.ensure_genesis()
        previous = self.repo.latest_block()
        previous_hash = previous.block_hash if previous else GENESIS_PREVIOUS_HASH
        index = (previous.index + 1) if previous else 0

        block = self._build_block(
            index=index,
            timestamp=datetime.utcnow(),
            certificate_id=certificate_id,
            certificate_hash=certificate_hash,
            previous_hash=previous_hash,
        )
        return self.repo.save(block)

    def get_by_certificate(self, certificate_id: str) -> Optional[BlockchainBlock]:
        return self.repo.get_by_certificate(certificate_id)

    def verify_chain(self) -> Dict[str, object]:
        """Recompute every block hash and validate the previous-hash linkage."""
        blocks = self.repo.all_ordered()
        if not blocks:
            return {"is_valid": False, "length": 0, "errors": ["chain empty"]}

        errors: List[str] = []
        genesis = blocks[0]
        if genesis.index != 0:
            errors.append("chain does not start with a genesis block")

        for idx, block in enumerate(blocks):
            recomputed = self._compute_hash(
                block.index,
                self._ts(block.timestamp),
                block.certificate_id,
                block.certificate_hash,
                block.previous_hash,
                block.nonce,
            )
            if recomputed != block.block_hash:
                errors.append(f"block #{block.index} hash mismatch (tampered)")
                continue
            if idx > 0:
                expected_previous = blocks[idx - 1].block_hash
                if block.previous_hash != expected_previous:
                    errors.append(
                        f"block #{block.index} previous_hash does not link to block #{blocks[idx - 1].index}"
                    )

        last_index = blocks[-1].index
        return {
            "is_valid": len(errors) == 0,
            "length": len(blocks),
            "last_index": last_index,
            "errors": errors,
            "message": "Blockchain integrity verified" if not errors else "Blockchain tampering detected",
        }

    def validate_certificate(
        self, certificate_id: str, certificate_hash: str
    ) -> Dict[str, object]:
        """Compare a live certificate hash against the anchored block.

        Returns the exact payload the public QR endpoint expects.
        """
        block = self.get_by_certificate(certificate_id)
        no_block: Dict[str, object] = {
            "isAuthentic": False,
            "certificateHash": certificate_hash,
            "blockchainHash": None,
            "blockNumber": None,
            "blockHash": None,
            "previousHash": None,
            "message": "Certificate not found on the blockchain",
        }
        if block is None:
            return no_block

        match = block.certificate_hash == certificate_hash

        # Sanity: ensure the rest of the chain is still intact.
        chain = self.verify_chain()
        if not chain["is_valid"]:
            return {
                "isAuthentic": False,
                "certificateHash": certificate_hash,
                "blockchainHash": block.certificate_hash,
                "blockNumber": block.index,
                "blockHash": block.block_hash,
                "previousHash": block.previous_hash,
                "message": "Blockchain integrity check failed — tampered chain",
            }

        return {
            "isAuthentic": match,
            "certificateHash": certificate_hash,
            "blockchainHash": block.certificate_hash,
            "blockNumber": block.index,
            "blockHash": block.block_hash,
            "previousHash": block.previous_hash,
            "message": "Certificate is authentic" if match else "Tampered Certificate: stored hash differs",
        }

    # -- Internals ---------------------------------------------------------
    @staticmethod
    def _ts(value: datetime) -> str:
        return value.replace(microsecond=0).isoformat()

    @staticmethod
    def _compute_hash(
        index: int,
        timestamp: str,
        certificate_id: str,
        certificate_hash: str,
        previous_hash: str,
        nonce: int,
    ) -> str:
        payload = f"{index}{timestamp}{certificate_id}{certificate_hash}{previous_hash}{nonce}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _build_block(
        self,
        index: int,
        timestamp: datetime,
        certificate_id: str,
        certificate_hash: str,
        previous_hash: str,
    ) -> BlockchainBlock:
        nonce = 0
        if self.settings.BLOCKCHAIN_PROOF_OF_WORK:
            target = "0" * self.settings.BLOCKCHAIN_DIFFICULTY
            while True:
                candidate = self._compute_hash(
                    index, self._ts(timestamp), certificate_id, certificate_hash, previous_hash, nonce
                )
                if candidate.startswith(target):
                    break
                nonce += 1

        block_hash = self._compute_hash(
            index, self._ts(timestamp), certificate_id, certificate_hash, previous_hash, nonce
        )
        return BlockchainBlock(
            index=index,
            timestamp=timestamp,
            certificate_id=certificate_id,
            certificate_hash=certificate_hash,
            previous_hash=previous_hash,
            block_hash=block_hash,
            nonce=nonce,
            chain_metadata=f"{self.settings.BLOCKCHAIN_IMPLEMENTATION}-{self.settings.ENVIRONMENT}",
        )
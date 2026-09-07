"""Certificate, blockchain verification and public verification schemas."""

from datetime import date
from typing import Optional

from pydantic import BaseModel, ConfigDict


class CertificateOut(BaseModel):
    """List-card and detail shape consumed by the frontend.

    The frontend reads both ``instrument`` (list card) and
    ``instrument_name``/``issued_date``/``valid_until`` (detail view), so both
    are provided.
    """

    id: str
    certificate_number: str
    instrument: str
    instrument_name: str
    serial_number: Optional[str] = None
    business_name: Optional[str] = None
    issued_date: str
    valid_until: str
    issue_date: str
    expiry: str
    status: str
    inspector_name: Optional[str] = None
    pdf_url: Optional[str] = None
    qr_code_url: Optional[str] = None
    certificate_hash: Optional[str] = None
    block_index: Optional[int] = None
    block_hash: Optional[str] = None
    verification_url: Optional[str] = None
    request_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class PublicCertificateResponse(BaseModel):
    isAuthentic: bool
    certificateHash: Optional[str] = None
    blockchainHash: Optional[str] = None
    blockNumber: Optional[int] = None
    blockHash: Optional[str] = None
    previousHash: Optional[str] = None
    tampered: bool = False
    message: str
    certificate: Optional[dict] = None


class ChainIntegrity(BaseModel):
    is_valid: bool
    length: int
    last_index: Optional[int] = None
    errors: list[str] = []
    message: str
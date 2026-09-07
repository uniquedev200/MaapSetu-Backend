"""Digital certificate issuance service — PDF + hash + blockchain anchoring."""

import hashlib
from datetime import date
from types import SimpleNamespace
from typing import Optional

from sqlalchemy.orm import Session

from app.blockchain.service import BlockchainService
from app.core.config import get_settings
from app.core.enums import CertificateStatus, InstrumentStatus, PassportEventType, RequestStatus
from app.core.exceptions import ValidationError
from app.models.certificate import Certificate
from app.models.instrument import Instrument
from app.models.user import User
from app.models.verification_request import VerificationRequest
from app.repositories.certificate_repository import CertificateRepository
from app.services.audit_service import audit
from app.services.passport_service import PassportService
from app.services.pdf_service import pdf_service
from app.services.qr_service import qr_service
from app.services.storage_service import storage_service
from app.utils.id_generator import certificate_number, certificate_public_id


class CertificateService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = CertificateRepository(db)
        self.passport = PassportService(db)
        self.blockchain = BlockchainService(db)
        self.settings = get_settings()

    def issue(
        self,
        *,
        request: VerificationRequest,
        inspector: User,
        public_base_url: Optional[str] = None,
    ) -> Certificate:
        """Generate the certificate for a passed inspection. idempotent per request."""
        if request.certificates:
            return request.certificates[0]

        instrument: Instrument = request.instrument
        if instrument.status == InstrumentStatus.FAILED.value:
            raise ValidationError("A failed instrument cannot receive a certificate.")

        cert_number = certificate_number()
        cert_public_id = certificate_public_id()
        issued_date = date.today()
        expiry_date = self._expiry_from(issued_date)

        verification_url = f"{public_base_url or self.settings.PUBLIC_BASE_URL}/verify/{cert_public_id}"

        # 1. QR + PDF
        qr_bytes = qr_service.generate(verification_url)
        placeholder = Certificate(
            certificate_number=cert_number,
            public_id=cert_public_id,
            instrument=instrument,
            owner=request.applicant,
            inspector=inspector,
            issued_date=issued_date,
            expiry_date=expiry_date,
            status=CertificateStatus.ACTIVE.value,
            verification_url=verification_url,
        )
        pdf_bytes = pdf_service.generate(placeholder, qr_bytes)

        # 2. SHA-256 hash of the exact PDF bytes that get stored.
        certificate_hash = hashlib.sha256(pdf_bytes).hexdigest()

        # 3. Persist PDF + QR to storage.
        pdf_path = storage_service.upload(folder="certificates", filename=f"{cert_number}.pdf", content=pdf_bytes)
        qr_path = storage_service.upload(folder="qrcodes", filename=f"{cert_number}.png", content=qr_bytes)

        cert = self.repo.create(
            public_id=cert_public_id,
            certificate_number=cert_number,
            request_id=request.id,
            instrument_id=instrument.id,
            owner_id=request.applicant_id,
            inspector_id=inspector.id,
            issued_date=issued_date,
            expiry_date=expiry_date,
            status=CertificateStatus.ACTIVE.value,
            pdf_url=storage_service.public_url(pdf_path),
            qr_code_url=storage_service.public_url(qr_path),
            certificate_hash=certificate_hash,
            verification_url=verification_url,
        )

        # 4. Anchor hash on the blockchain and record block metadata on the certificate.
        block = self.blockchain.add_block(cert_public_id, certificate_hash)
        cert.block_index = block.index
        cert.block_hash = block.block_hash
        self.repo.save(cert)

        # 5. Advance the request + instrument lifecycle.
        request.set_status(RequestStatus.CERTIFICATE_ISSUED)
        instrument.status = InstrumentStatus.VERIFIED.value
        self.db.add_all([request, instrument])
        self.db.commit()

        self.passport.add_event(
            instrument_id=instrument.id,
            event_type=PassportEventType.CERTIFICATE_ISSUED,
            title="Certificate Issued",
            description=f"Verification certificate {cert_number} issued (block #{block.index})",
            metadata={"certificate_id": cert_public_id, "certificate_hash": certificate_hash,
                      "block_index": block.index, "block_hash": block.block_hash},
            actor=inspector,
        )
        audit(self.db, user=inspector, action="CERTIFICATE", entity_type="certificate", entity_id=cert_public_id,
              details=f"Issued certificate {cert_number} anchored on block #{block.index}")

        self.db.refresh(cert)
        return cert

    def get(self, public_id: str) -> Certificate:
        return self.repo.get_by_public_id(public_id)

    def get_or_404(self, public_id: str) -> Certificate:
        from app.core.exceptions import NotFoundError

        cert = self.repo.get_by_public_id(public_id)
        if cert is None:
            cert = self.repo.get_by_certificate_number(public_id)
        if cert is None:
            raise NotFoundError("Certificate", public_id)
        return cert

    def list_all(
        self,
        *,
        user: User | None = None,
        page: int = 1,
        page_size: int = 20,
        search: Optional[str] = None,
        status: Optional[str] = None,
    ) -> tuple[list, int]:
        """Role-scoped certificate listing."""
        owner_id = user.id if (user and user.role == "BUSINESS") else None
        district = user.district if (user and user.role in ("LMO", "GATC") and user.district) else None
        return self.repo.search(
            page=page, page_size=page_size, search=search, status=status,
            owner_id=owner_id, district=district,
        )

    def verify(self, cert: Certificate, *, full: bool = False) -> dict:
        """Blockchain verification for a single certificate."""
        result = self.blockchain.validate_certificate(cert.public_id, cert.certificate_hash or "")
        if full:
            from app.schemas.serializers import certificate_list_item

            result["certificate"] = certificate_list_item(cert)
        return result

    def simulate_tamper(self, cert: Certificate) -> Certificate:
        """Simulate post-issuance tampering for the demo.

        Keeps the original blockchain block untouched, then overwrites the
        stored PDF/QR artefacts and re-hashes the doctored PDF. The anchored
        hash and the stored hash now differ, so public verification fails —
        exactly what scanning a fake certificate produces.
        """
        if cert.is_tampered:
            raise ValidationError("Certificate is already marked as tampered.")
        if not cert.block_hash:
            raise ValidationError("Certificate has no blockchain anchor — cannot tamper.")

        tampered_cert = self._tampered_namespace(cert)
        new_qr = qr_service.generate(cert.verification_url or f"{self.settings.PUBLIC_BASE_URL}/verify/{cert.public_id}")
        new_pdf = pdf_service.generate(tampered_cert, new_qr)
        new_hash = hashlib.sha256(new_pdf).hexdigest()

        pdf_path = storage_service.upload(
            folder="certificates", filename=f"tampered_{cert.certificate_number}.pdf", content=new_pdf)
        qr_path = storage_service.upload(
            folder="qrcodes", filename=f"tampered_{cert.certificate_number}.png", content=new_qr)

        cert.tamper_meta = {
            "original_hash": cert.certificate_hash,
            "original_pdf_url": cert.pdf_url,
            "original_qr_url": cert.qr_code_url,
        }
        cert.certificate_hash = new_hash
        cert.pdf_url = storage_service.public_url(pdf_path)
        cert.qr_code_url = storage_service.public_url(qr_path)
        cert.is_tampered = True
        self.repo.save(cert)

        audit(self.db, user=None, action="TAMPER", entity_type="certificate",
              entity_id=cert.public_id,
              details=f"Tamper simulation applied to certificate {cert.certificate_number} (hash mismatch demo)")
        return cert

    def restore(self, cert: Certificate) -> Certificate:
        """Undo a demo tamper, restoring the original artefact URLs + hash."""
        if not cert.is_tampered or not cert.tamper_meta:
            raise ValidationError("Certificate is not tampered.")
        meta = cert.tamper_meta
        cert.certificate_hash = meta.get("original_hash")
        cert.pdf_url = meta.get("original_pdf_url")
        cert.qr_code_url = meta.get("original_qr_url")
        cert.is_tampered = False
        cert.tamper_meta = None
        self.repo.save(cert)

        audit(self.db, user=None, action="RESTORE", entity_type="certificate",
              entity_id=cert.public_id,
              details=f"Tamper simulation removed from certificate {cert.certificate_number}")
        return cert

    @staticmethod
    def _tampered_namespace(cert: Certificate) -> SimpleNamespace:
        """A lightweight certificate stand-in whose only difference from the
        real record is the owner name + certificate number — so the regenerated
        PDF hashes differently while staying visually convincing."""
        inst = cert.instrument
        inst_ns = SimpleNamespace(
            name=inst.name, instrument_type=inst.instrument_type,
            manufacturer=getattr(inst, "manufacturer", None) or "-",
            model_number=getattr(inst, "model_number", None) or "-",
            serial_number=inst.serial_number,
            capacity_max=getattr(inst, "capacity_max", None),
            unit_of_measurement=getattr(inst, "unit_of_measurement", "kg") or "kg",
            accuracy_class=getattr(inst, "accuracy_class", "Class III") or "Class III",
            installation_location=getattr(inst, "installation_location", None) or "-",
            district=getattr(inst, "district", None) or "-",
        )
        owner = cert.owner
        fake_owner = SimpleNamespace(
            business_name=f"{owner.business_name or owner.name}  (UNVERIFIED COPY)",
            name=owner.name,
        )
        inspector = cert.inspector
        return SimpleNamespace(
            certificate_number=f"{cert.certificate_number}-TAMPERED",
            issued_date=cert.issued_date,
            expiry_date=cert.expiry_date,
            status="ACTIVE",
            instrument=inst_ns,
            owner=fake_owner,
            inspector=SimpleNamespace(name=inspector.name if inspector else "Unknown"),
            verification_url=cert.verification_url,
        )

    def _expiry_from(self, issued_date: date) -> date:
        months = self.settings.CERTIFICATE_VALIDITY_MONTHS
        month_index = issued_date.month - 1 + months
        year = issued_date.year + month_index // 12
        month = month_index % 12 + 1
        from calendar import monthrange

        return date(year, month, monthrange(year, month)[1])
"""QR code generation (Pillow-backed) for certificates and public verification."""

import io

import qrcode
from qrcode.image.pil import PilImage


class QrService:
    """Generates QR images and returns them as PNG bytes."""

    def __init__(self, size: int = 10, border: int = 2) -> None:
        self.size = size
        self.border = border

    def generate(self, payload: str) -> bytes:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=self.size,
            border=self.border,
        )
        qr.add_data(payload)
        qr.make(fit=True)
        img: PilImage = qr.make_image(fill_color="black", back_color="white")
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        return buffer.getvalue()


qr_service = QrService()
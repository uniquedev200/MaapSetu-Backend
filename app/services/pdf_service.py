"""PDF certificate generation with ReportLab (embeds the QR code)."""

import io
from datetime import date

from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    Image as RLImage,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.core.config import get_settings
from app.models.certificate import Certificate


class PdfService:
    """Builds the official verification certificate PDF."""

    def generate(self, cert: Certificate, qr_bytes: bytes) -> bytes:
        settings = get_settings()
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            leftMargin=2 * cm,
            rightMargin=2 * cm,
            topMargin=1.8 * cm,
            bottomMargin=1.5 * cm,
            title=f"Certificate of Verification - {cert.certificate_number}",
            author=settings.OFFICIAL_AUTHORITY_NAME,
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "CertTitle", parent=styles["Title"], fontSize=16, leading=20,
            alignment=TA_CENTER, textColor=colors.HexColor("#1a4472"), spaceAfter=4,
        )
        subtitle_style = ParagraphStyle(
            "CertSubtitle", parent=styles["Normal"], fontSize=11, leading=14,
            alignment=TA_CENTER, textColor=colors.HexColor("#555555"), spaceAfter=2,
        )
        body_style = ParagraphStyle(
            "CertBody", parent=styles["Normal"], fontSize=11, leading=16, spaceAfter=6,
        )
        label_style = ParagraphStyle(
            "CertLabel", parent=styles["Normal"], fontSize=8.5, leading=11,
            textColor=colors.HexColor("#666666"),
        )
        value_style = ParagraphStyle(
            "CertValue", parent=styles["Normal"], fontSize=11, leading=15,
            textColor=colors.HexColor("#111111"),
        )

        instrument = cert.instrument
        owner = cert.owner

        story: list = []

        # Header
        story.append(Paragraph("GOVERNMENT OF INDIA", subtitle_style))
        story.append(Paragraph(settings.OFFICIAL_AUTHORITY_NAME, title_style))
        story.append(Paragraph("(Department of Consumer Affairs)", subtitle_style))
        story.append(Paragraph("Legal Metrology Certificate of Verification", styles["Italic"]))
        story.append(Spacer(1, 0.5 * cm))

        # Certificate frame
        frame = Table(
            [
                [
                    Paragraph("Certificate No.", label_style),
                    Paragraph(cert.certificate_number, value_style),
                    Paragraph("Valid Until", label_style),
                    Paragraph(cert.expiry_date.isoformat(), value_style),
                ],
                [
                    Paragraph("Issued On", label_style),
                    Paragraph(cert.issued_date.isoformat(), value_style),
                    Paragraph("Status", label_style),
                    Paragraph(cert.status, value_style),
                ],
            ],
            colWidths=[3.2 * cm, 6.3 * cm, 3.2 * cm, 4.3 * cm],
        )
        frame.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#1a4472")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f6f9fd")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 8),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
                ]
            )
        )
        story.append(frame)
        story.append(Spacer(1, 0.5 * cm))
        story.append(Paragraph(settings.OFFICIAL_OATH, body_style))
        story.append(Spacer(1, 0.3 * cm))

        # Instrument details
        story.append(Paragraph("PARTICULARS OF THE INSTRUMENT", ParagraphStyle(
            "section", parent=styles["Normal"], fontSize=11, leading=14,
            textColor=colors.HexColor("#1a4472"), spaceBefore=8, spaceAfter=4,
        )))
        instrument_rows = [
            ["Instrument Name", instrument.name or "-"],
            ["Type / Category", instrument.instrument_type or "-"],
            ["Manufacturer", instrument.manufacturer or "-"],
            ["Model Number", instrument.model_number or "-"],
            ["Serial Number", instrument.serial_number or "-"],
            [
                "Capacity",
                f"{instrument.capacity_max or '--'} {instrument.unit_of_measurement or ''}".strip(),
            ],
            ["Accuracy Class", instrument.accuracy_class or "Class III"],
            ["Installation Location", instrument.installation_location or "-"],
            ["District", instrument.district or "-"],
            ["Owner / Business", owner.business_name or owner.name],
        ]
        inst_table = Table(
            [[Paragraph(k, label_style), Paragraph(str(v), value_style)] for k, v in instrument_rows],
            colWidths=[5.5 * cm, 11.5 * cm],
            hAlign="LEFT",
        )
        inst_table.setStyle(
            TableStyle(
                [
                    ("BOX", (0, 0), (-1, -1), 0.75, colors.HexColor("#bbbbbb")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dddddd")),
                    ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, colors.HexColor("#f1f4f8")]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        story.append(inst_table)
        story.append(Spacer(1, 0.6 * cm))

        # QR code + verification hint
        qr_image = RLImage(io.BytesIO(qr_bytes), width=3.2 * cm, height=3.2 * cm)
        qr_paragraph = Paragraph(
            f'<font size="9" color="#333333">Scan to verify authenticity<br/>'
            f'<b>#{cert.verification_url or cert.certificate_number}</b></font>',
            ParagraphStyle("qr", parent=styles["Normal"], alignment=TA_CENTER),
        )
        qr_block = Table([[qr_image, qr_paragraph]], colWidths=[3.6 * cm, 8 * cm])
        qr_block.setStyle(TableStyle([
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ffffff")),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ]))
        story.append(qr_block)
        story.append(Spacer(1, 0.8 * cm))

        # Signature block
        sig = Table(
            [
                [
                    Paragraph("<b>(Authorised Signatory)</b>", value_style),
                    Paragraph(cert.inspector.name if cert.inspector else "", value_style),
                ]
            ],
            colWidths=[5.5 * cm, 11.5 * cm],
        )
        sig.setStyle(TableStyle([("TOPPADDING", (0, 0), (-1, -1), 16)]))
        story.append(sig)
        story.append(Paragraph(
            f"Digital Signature — Issued by {settings.ISSUING_OFFICER_TITLE}",
            ParagraphStyle("foot", parent=styles["Normal"], fontSize=8.5,
                           textColor=colors.HexColor("#888888"), spaceBefore=6),
        ))

        doc.build(story)
        return buffer.getvalue()


pdf_service = PdfService()
"""Public endpoints — QR code certificate verification, blockchain integrity
and static file serving. All public routes are unauthenticated."""

import html
import mimetypes
from pathlib import Path

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from app.api.deps import AppServices, get_services
from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.core.response import ok
from app.schemas.serializers import certificate_list_item
from app.services.storage_service import storage_service

router = APIRouter(prefix="/public", tags=["Public"])

_PAGE_CSS = """
body{margin:0;background:#f9f9ff;color:#191c1f;font-family:'Plus Jakarta Sans',Segoe UI,Arial,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:28px 20px 64px}
.brand{display:flex;align-items:center;gap:12px;margin-bottom:22px}
.badge{width:46px;height:46px;border-radius:50%;background:#e8f0fb;box-shadow:inset 3px 3px 7px #d4dbe6,inset -3px -3px 7px #ffffff;display:flex;align-items:center;justify-content:center;font-size:22px}
.brand b{color:#0e4786;font-size:16px}.brand span{color:#5a5e68;font-size:12px;display:block}
.card{background:#f9f9ff;border-radius:14px;box-shadow:6px 6px 14px #d4dbe6,-6px -6px 14px #ffffff;padding:24px;margin-bottom:16px}
.hero{border-radius:14px;padding:26px;text-align:center;color:#fff;margin-bottom:16px}
.ok{background:linear-gradient(135deg,#0f7b3d,#1c9e56)}
.bad{background:linear-gradient(135deg,#b32020,#d63c3c)}
.hero .ico{font-size:44px;line-height:1}
.hero h2{margin:8px 0 4px;font-size:22px;letter-spacing:.5px}
.hero p{margin:0;opacity:.92;font-size:13.5px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.lbl{font-size:11px;color:#73777f;text-transform:uppercase;letter-spacing:.4px;margin-bottom:2px}
.val{font-size:14px;font-weight:600;word-break:break-word}
.mono{font-family:'JetBrains Mono',Consolas,monospace;font-size:11.5px}
.rowlabel{font-size:11px;color:#73777f;text-transform:uppercase;letter-spacing:.4px}
.rowval{font-size:14px;font-weight:600}
table{width:100%;border-collapse:collapse}
td{padding:8px 0;border-bottom:1px dashed #d9dce4}
td:last-child{text-align:right}
.note{display:flex;gap:10px;align-items:flex-start;font-size:13px;color:#5a5e68;margin-top:14px}
.chip{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700}
.chip-ok{background:#d9f2e3;color:#0f7b3d}.chip-bad{background:#ffe0de;color:#a30f0f}
.arm{background:#f0f2f7;border-radius:10px;padding:12px;font-family:'JetBrains Mono',Consolas,monospace;font-size:11.5px;line-height:1.7;word-break:break-all}
"""


def _render_verify_html(cert: dict, auth: dict) -> str:
    authentic = bool(auth.get("isAuthentic"))
    tampered = bool(cert.get("is_tampered"))
    h = html.escape

    cls = "ok" if authentic else "bad"
    ico = "✓" if authentic else "✕"
    title = (
        "AUTHENTIC CERTIFICATE" if authentic else
        "TAMPERED CERTIFICATE" if tampered else
        "AUTHENTICATION FAILED"
    )
    subtitle = (
        "Blockchain record matches this certificate."
        if authentic
        else (
            "This record is flagged as a forged copy. Do not rely on it."
            if tampered
            else "This certificate failed blockchain verification and must NOT be relied upon."
        )
    )

    cert_number = h(str(cert.get("certificate_number") or cert.get("id") or ""))
    instrument = h(str(cert.get("instrument_name") or cert.get("instrument") or "-"))
    serial = h(str(cert.get("serial_number") or "-"))
    business = h(str(cert.get("business_name") or "-"))
    issued = h(str(cert.get("issued_date") or cert.get("issue_date") or "-"))
    valid = h(str(cert.get("valid_until") or cert.get("expiry") or "-"))
    inspector = h(str(cert.get("inspector_name") or "-"))
    status_chip = (
        '<span class="chip chip-bad">TAMPERED COPY</span>'
        if tampered
        else f'<span class="chip chip-ok">VERIFIED</span>'
    )
    chain_msg = (
        '<span class="chip chip-ok">CHAIN INTACT</span>'
        if authentic
        else '<span class="chip chip-bad">REJECTED</span>'
    )

    block_number = auth.get("blockNumber")
    block_no = h(str(block_number)) if block_number is not None else "-"
    block_hash = h(str(auth.get("blockHash") or "-"))
    stored_hash = h(str(cert.get("certificate_hash") or "-"))
    anchored_hash = h(str(auth.get("blockchainHash") or "-"))

    warning = ""
    if tampered:
        warning = (
            "<div class='note'>⚠️ &nbsp;This record is a <b>simulation of a forged certificate</b>: "
            "its stored file hash no longer matches the anchor written to the blockchain at issuance time.</div>"
        )
    elif authentic:
        warning = (
            "<div class='note'>🔒 &nbsp;Authenticity is established by comparing the stored certificate hash "
            "against the hash anchored to the tamper-evident verification ledger at issuance.</div>"
        )
    else:
        warning = (
            "<div class='note'>🚫 &nbsp;The stored hash differs from the blockchain anchor. "
            "Either the PDF was altered after issuance or the certificate record was edited — treat as fraudulent.</div>"
        )

    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Verify Certificate — {cert_number}</title><style>{_PAGE_CSS}</style></head>
<body><div class="wrap">
  <div class="brand">
    <div class="badge">🛡️</div>
    <div><b>Legal Metrology Certificate Verification</b><span>Official public registry · tap a QR anywhere</span></div>
  </div>

  <div class="hero {cls}">
    <div class="ico">{ico}</div>
    <h2>{title}</h2>
    <p>{subtitle}</p>
    <div style="margin-top:12px">{status_chip} &nbsp; {chain_msg}</div>
  </div>

  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px">
      <div class="rowlabel">Certificate No.</div>
      <div class="rowval" style="font-family:'JetBrains Mono',monospace">{cert_number}</div>
    </div>
    <div class="grid">
      <div><div class="lbl">Instrument</div><div class="val">{instrument}</div></div>
      <div><div class="lbl">Serial Number</div><div class="val mono">{serial}</div></div>
      <div><div class="lbl">Registered Business</div><div class="val">{business}</div></div>
      <div><div class="lbl">Inspector</div><div class="val">{inspector}</div></div>
      <div><div class="lbl">Issued On</div><div class="val">{issued}</div></div>
      <div><div class="lbl">Valid Until</div><div class="val">{valid}</div></div>
    </div>
    {warning}
  </div>

  <div class="card">
    <div class="lbl" style="margin-bottom:8px">Blockchain Anchoring</div>
    <div class="arm">
      block index : {block_no}<br/>
      stored hash : {stored_hash}<br/>
      anchored hash: {anchored_hash}<br/>
      block hash  : {block_hash}
    </div>
  </div>

  <div class="card" style="text-align:center;font-size:12px;color:#5a5e68">
    This verification is issued under the provisions of the Legal Metrology Act, 2009.
    <br/>Verification of authenticity is performed against the tamper-evident certificate ledger.
  </div>
</div></body></html>"""


@router.get("/certificate/{certificate_id}", response_model=dict,
            summary="Full public certificate details + authenticity")
def public_certificate_detail(
    certificate_id: str,
    services: AppServices = Depends(get_services),
) -> dict:
    cert = services.certificates.get_or_404(certificate_id)
    authenticity = services.certificates.verify(cert)
    return ok(
        "Certificate verified",
        {
            "certificate": certificate_list_item(cert),
            "authenticity": authenticity,
        },
    )


@router.get("/verify/{certificate_id}", response_class=HTMLResponse,
            summary="Consumer-facing certificate verification webpage (QR target)")
def public_verify_page(
    certificate_id: str,
    services: AppServices = Depends(get_services),
) -> Response:
    cert = services.certificates.get_or_404(certificate_id)
    authenticity = services.certificates.verify(cert)
    page = _render_verify_html(certificate_list_item(cert), authenticity)
    return Response(content=page, media_type="text/html")


@router.get("/certificate/{certificate_id}/verify", response_model=dict,
            summary="Blockchain authenticity payload (scanned by public QR)")
def public_certificate_verify(
    certificate_id: str,
    services: AppServices = Depends(get_services),
) -> dict:
    cert = services.certificates.get_or_404(certificate_id)
    return services.certificates.verify(cert)


@router.get("/blockchain/integrity", response_model=dict,
            summary="Verify the integrity of the whole certificate chain")
def public_blockchain_integrity(
    services: AppServices = Depends(get_services),
) -> dict:
    result = services.certificates.blockchain.verify_chain()
    return ok(result["message"], result)


@router.get("/file/{folder}/{filename}", summary="Serve stored files (local backend)")
def serve_file(folder: str, filename: str) -> Response:
    settings = get_settings()
    if settings.STORAGE_BACKEND != "local":
        raise NotFoundError("File")
    media_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    try:
        content = storage_service.read(f"{folder}/{filename}")
    except FileNotFoundError:
        raise NotFoundError("File", f"{folder}/{filename}")
    return Response(content=content, media_type=media_type)
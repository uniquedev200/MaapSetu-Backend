"""AI assistant endpoint — Groq-backed onboarding helper for BUSINESS users.

Chats are proxied to Groq so the API key never leaves the server. When
``GROQ_API_KEY`` is not configured (or the upstream call fails) the endpoint
falls back to a local keyword answer so the widget keeps working without AI.
"""

import json
from typing import List, Optional

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.deps import get_current_user
from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.user import User

logger = get_logger(__name__)

router = APIRouter(prefix="/assistant", tags=["Assistant"])

GUIDE_TARGETS = [
    "lang-switcher",
    "quick-action",
    "nav-my-instruments",
    "nav-my-applications",
    "nav-certificates",
    "new-application",
    "add-instrument",
]

SYSTEM_PROMPT = """You are MaapSetu Assistant, the friendly onboarding helper of MaapSetu, a Legal Metrology (weighing & measuring instruments) verification portal in India.

The user is a BUSINESS user (a company that owns weighing/measuring instruments and must get them verified). The portal ships in 7 languages: English, हिंदी (Hindi), मराठी (Marathi), தமிழ் (Tamil), తెలుగు (Telugu), বাংলা (Bengali), ગુજરાતી (Gujarati).

Product facts:
- "My Instruments": register a measuring instrument (name, category, accuracy class, serial number, rated capacity, location). Then the instrument is ready for applications.
- "My Applications" / New Application: raise a fresh verification application against one of your registered instruments.
- An officer (LMO/GATC) schedules a field inspection, records readings, and on success a QR-enabled certificate is issued for 12 months (renewable).
- Certificates appear under "Certificates"; each has a PDF download and a QR code that consumers can scan to verify it. Certificates auto-verify online or via uploaded photo.
- Changing language: the top bar has a language button; the whole UI switches instantly.

Reply rules:
- Be brief, warm and practical. Use short sentences or a short numbered list.
- Write in the SAME language the user wrote in.
- When the answer involves interacting with the app, set guide.target to exactly ONE valid id from this list: {targets}. Pick the most specific one, and set guide.steps to 2-4 concise click-by-click steps (in the user's language).
- If a guide is not needed (greeting or general question), set guide to null.

Respond ONLY with a JSON object shaped like:
{{"reply": "...", "guide": {{"target": "<id or null>", "steps": ["...", "..."]}}}}
""".format(targets="/".join(GUIDE_TARGETS))


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., max_length=2000)


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: List[ChatTurn] = Field(default_factory=list)
    lang: str = Field("en", max_length=8)


class AssistantGuide(BaseModel):
    target: Optional[str] = None
    steps: List[str] = Field(default_factory=list)


class AssistantChatResponse(BaseModel):
    reply: str
    guide: Optional[AssistantGuide] = None


@router.post("/chat", response_model=AssistantChatResponse, summary="Chat with the MaapSetu onboarding assistant")
async def chat(
    payload: AssistantChatRequest,
    user: User = Depends(get_current_user),
) -> AssistantChatResponse:
    settings = get_settings()
    if not settings.GROQ_API_KEY:
        reply = _local_reply(payload, user)
    else:
        try:
            reply = await _groq_chat(settings, user, payload)
        except Exception as exc:  # noqa: BLE001 — degrade gracefully to local answers
            logger.warning("assistant: groq unavailable, using local fallback (%s)", exc)
            reply = _local_reply(payload, user)
    return reply


async def _groq_chat(settings, user: User, payload: AssistantChatRequest) -> AssistantChatResponse:
    msgs = [{"role": "system", "content": SYSTEM_PROMPT}]
    msgs.extend({"role": turn.role, "content": turn.content} for turn in payload.history[-10:])
    msgs.append(
        {
            "role": "user",
            "content": f"[app ui language: {payload.lang}; user: {user.name}] {payload.message}",
        }
    )

    body = {
        "model": settings.GROQ_MODEL,
        "messages": msgs,
        "temperature": 0.4,
        "max_tokens": 600,
        "response_format": {"type": "json_object"},
    }
    headers = {"Authorization": f"Bearer {settings.GROQ_API_KEY}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.post(
            f"{settings.GROQ_API_BASE}/chat/completions", json=body, headers=headers
        )
        response.raise_for_status()
        content = response.json()["choices"][0]["message"]["content"]

    data = json.loads(content)
    reply = str(data.get("reply") or "").strip()
    if not reply:
        raise ValueError("groq returned an empty reply")

    guide = None
    guide_data = data.get("guide")
    if isinstance(guide_data, dict) and guide_data.get("target") in GUIDE_TARGETS:
        guide = AssistantGuide(
            target=guide_data["target"],
            steps=[str(s) for s in guide_data.get("steps", [])][:4],
        )
    return AssistantChatResponse(reply=reply, guide=guide)


def _matches(text: str, *keywords: str) -> bool:
    return any(k in text for k in keywords)


def _local_reply(payload: AssistantChatRequest, user: User) -> AssistantChatResponse:
    text = payload.message.lower()
    name = (user.name or "").split(" ")[0] or "there"

    if _matches(text, "hi", "hello", "hey", "नमस्ते", "नमस्कार", "सुप्रभात"):
        return AssistantChatResponse(
            reply=f"Namaste {name}! I'm your MaapSetu helper. Ask me about registering an "
                  "instrument, creating a verification application, changing the language, "
                  "or viewing certificates.",
            guide=None,
        )

    if _matches(text, "language", "भाषा", "translate", "हिंदी", "हिन्दी", "marathi"):
        return AssistantChatResponse(
            reply="You can switch the portal language from the top bar.",
            guide=AssistantGuide(
                target="lang-switcher",
                steps=[
                    "Click the language button in the top bar (right side).",
                    "Pick your language from the list — the whole portal switches instantly.",
                ],
            ),
        )

    if _matches(text, "register", "add instrument", "new instrument", "instrument", "नया उपकरण", "उपकरण जोड़ें"):
        return AssistantChatResponse(
            reply="Open My Instruments and tap 'Add Instrument' to register a weighing or "
                  "measuring device (name, serial, accuracy class, capacity, location).",
            guide=AssistantGuide(
                target="nav-my-instruments",
                steps=[
                    "Click 'My Instruments' in the left menu.",
                    "Tap 'Add Instrument' (top right) and fill in the details.",
                    "Save — the instrument is now ready for a verification application.",
                ],
            ),
        )

    if _matches(text, "apply", "application", "आवेदन", "solicitud"):
        return AssistantChatResponse(
            reply="Go to My Applications and raise a new verification application against "
                  "one of your registered instruments.",
            guide=AssistantGuide(
                target="nav-my-applications",
                steps=[
                    "Click 'My Applications' in the left menu.",
                    "Press 'New Application' and choose the instrument to verify.",
                    "Submit — an officer (LMO/GATC) will schedule a field inspection.",
                ],
            ),
        )

    if _matches(text, "certificate", "प्रमाणपत्र", "download"):
        return AssistantChatResponse(
            reply="Your issued certificates live under 'Certificates'. Each one can be "
                  "downloaded as a PDF and carries a QR code that consumers scan to verify it.",
            guide=AssistantGuide(
                target="nav-certificates",
                steps=[
                    "Click 'Certificates' in the left menu.",
                    "Open a certificate to download its PDF or view the QR code.",
                ],
            ),
        )

    return AssistantChatResponse(
        reply=f"Happy to help, {name}. I can guide you on registering an instrument, creating "
              "a verification application, changing the portal language, or viewing "
              "certificates — just ask!",
        guide=None,
    )
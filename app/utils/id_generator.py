"""Generation of human-friendly, URL-safe public identifiers."""

import random
import string
from datetime import date

_ALPHANUM = string.ascii_uppercase + string.digits


def _suffix(length: int = 4) -> str:
    return "".join(random.choices(_ALPHANUM, k=length))


def make_id(prefix: str, *, year: bool = True, length: int = 4) -> str:
    """Return an identifier like ``APP-2026-8F3A`` or ``USER-1234``."""
    year_part = f"{date.today().year}-" if year else ""
    return f"{prefix}-{year_part}{_suffix(length)}"


def request_id() -> str:
    return make_id("APP")


def instrument_id() -> str:
    return make_id("INST")


def inspection_id() -> str:
    return make_id("INSP")


def certificate_number() -> str:
    return make_id("CERT")


def certificate_public_id() -> str:
    return make_id("CERT")


def user_id() -> str:
    return make_id("USR", year=False)


def business_registration_no(name_hint: str = "") -> str:
    prefix = "".join(ch for ch in (name_hint or "B").upper() if ch.isalpha())[:3] or "BRN"
    return f"{prefix}-{_suffix(6)}"
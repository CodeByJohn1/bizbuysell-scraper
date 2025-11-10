import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

MONEY_RE = re.compile(r"[-+]?\$?\s*([\d,]+(?:\.\d+)?)")
INT_RE = re.compile(r"[-+]?\d+")

def clean_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    cleaned = " ".join(text.split())
    return cleaned or None

def normalize_na(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    lowered = value.strip().lower()
    if not lowered or lowered in {"n/a", "na", "not applicable", "unknown"}:
        return None
    if lowered in {"not disclosed", "undisclosed"}:
        return "Not Disclosed"
    return value.strip()

def parse_money(value: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    match = MONEY_RE.search(value.replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        logger.debug("Failed to parse money from %r", value)
        return None

def parse_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    match = INT_RE.search(value.replace(",", ""))
    if not match:
        return None
    try:
        return int(match.group(0))
    except ValueError:
        logger.debug("Failed to parse int from %r", value)
        return None

def normalize_field_label(label: str) -> str:
    return " ".join(label.strip().upper().split())

def merge_with_defaults(
    extracted: Dict[str, Any],
    default_fields: Dict[str, Any],
) -> Dict[str, Any]:
    merged = default_fields.copy()
    for key, value in extracted.items():
        merged[key] = value
    return merged
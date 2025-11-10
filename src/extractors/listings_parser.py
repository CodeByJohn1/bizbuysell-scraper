import logging
import time
from typing import Any, Dict, Optional

import requests
from bs4 import BeautifulSoup

from .utils_format import (
    clean_text,
    merge_with_defaults,
    normalize_field_label,
    normalize_na,
    parse_int,
    parse_money,
)

logger = logging.getLogger(__name__)

FIELD_DEFAULTS: Dict[str, Any] = {
    "DATE ADDED": None,
    "TITLE": None,
    "LOCATION": None,
    "STATE": None,
    "YEAR ESTABLISHED": None,
    "LINK TO DEAL": None,
    "PRICE": None,
    "REVENUE": None,
    "EBITDA": None,
    "CASH FLOW": None,
    "INDUSTRY DETAILS": None,
    "NUMBER OF EMPLOYEES": None,
    "INVENTORY": None,
    "REASON FOR SELLING": None,
    "SELLER TYPE": None,
    "REAL ESTATE": None,
    "BUILDING SF": None,
    "FACILITIES": None,
    "FF&E": None,
    "INTERMEDIARY NAME": None,
    "INTERMEDIARY FIRM": None,
    "INTERMEDIARY PHONE": None,
    "GROWTH & EXPANSION": None,
    "FINANCING": None,
    "SUPPORT & TRAINING": None,
    "FRANCHISE": None,
    "COMPETITION": None,
    "HOME-BASED": None,
}

LABEL_MAP = {
    "DATE ADDED": "DATE ADDED",
    "DATE POSTED": "DATE ADDED",
    "TITLE": "TITLE",
    "LOCATION": "LOCATION",
    "STATE": "STATE",
    "YEAR ESTABLISHED": "YEAR ESTABLISHED",
    "YEAR FOUNDED": "YEAR ESTABLISHED",
    "LINK TO DEAL": "LINK TO DEAL",
    "ASKING PRICE": "PRICE",
    "PRICE": "PRICE",
    "REVENUE": "REVENUE",
    "EBITDA": "EBITDA",
    "CASH FLOW": "CASH FLOW",
    "DESCRIPTION": "INDUSTRY DETAILS",
    "INDUSTRY DETAILS": "INDUSTRY DETAILS",
    "EMPLOYEES": "NUMBER OF EMPLOYEES",
    "NUMBER OF EMPLOYEES": "NUMBER OF EMPLOYEES",
    "INVENTORY": "INVENTORY",
    "REASON FOR SELLING": "REASON FOR SELLING",
    "SELLER TYPE": "SELLER TYPE",
    "REAL ESTATE": "REAL ESTATE",
    "BUILDING SQ FT": "BUILDING SF",
    "BUILDING SIZE": "BUILDING SF",
    "BUILDING SF": "BUILDING SF",
    "FACILITIES": "FACILITIES",
    "FF&E": "FF&E",
    "BROKER NAME": "INTERMEDIARY NAME",
    "INTERMEDIARY NAME": "INTERMEDIARY NAME",
    "BROKER FIRM": "INTERMEDIARY FIRM",
    "INTERMEDIARY FIRM": "INTERMEDIARY FIRM",
    "BROKER PHONE": "INTERMEDIARY PHONE",
    "PHONE": "INTERMEDIARY PHONE",
    "GROWTH & EXPANSION": "GROWTH & EXPANSION",
    "GROWTH / EXPANSION": "GROWTH & EXPANSION",
    "FINANCING": "FINANCING",
    "SUPPORT & TRAINING": "SUPPORT & TRAINING",
    "TRAINING & SUPPORT": "SUPPORT & TRAINING",
    "FRANCHISE": "FRANCHISE",
    "COMPETITION": "COMPETITION",
    "HOME-BASED": "HOME-BASED",
}

class ListingScraper:
    def __init__(
        self,
        base_url: str,
        user_agent: str,
        timeout: int = 20,
        delay_between_requests: float = 1.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.delay_between_requests = delay_between_requests
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

    def _request(self, url: str) -> Optional[str]:
        full_url = url
        if not url.lower().startswith("http"):
            full_url = f"{self.base_url}/{url.lstrip('/')}"

        logger.debug("Fetching URL: %s", full_url)
        try:
            response = self.session.get(full_url, timeout=self.timeout)
            response.raise_for_status()
            html = response.text
            logger.debug("Fetched %d bytes from %s", len(html), full_url)
        except Exception as exc:
            logger.error("Request failed for %s: %s", full_url, exc)
            return None
        finally:
            if self.delay_between_requests > 0:
                time.sleep(self.delay_between_requests)

        return html

    def scrape_listing(self, url: str) -> Optional[Dict[str, Any]]:
        html = self._request(url)
        if not html:
            return None

        try:
            data = parse_listing_html(html, url)
        except Exception as exc:
            logger.exception("Failed parsing listing %s: %s", url, exc)
            return None

        data["LINK TO DEAL"] = url
        return data

def parse_listing_html(html: str, url: str) -> Dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")
    extracted: Dict[str, Any] = {}

    title = _extract_title(soup)
    if title:
        extracted["TITLE"] = title

    location, state = _extract_location_and_state(soup)
    if location:
        extracted["LOCATION"] = location
    if state:
        extracted["STATE"] = state

    _extract_field_table_like(soup, extracted)
    _extract_description_sections(soup, extracted)
    _normalize_numeric_fields(extracted)

    extracted["LINK TO DEAL"] = url
    return merge_with_defaults(extracted, FIELD_DEFAULTS)

def _extract_title(soup: BeautifulSoup) -> Optional[str]:
    h1 = soup.find("h1")
    if not h1:
        h1 = soup.find("h2")
    return normalize_na(clean_text(h1.get_text(strip=True))) if h1 else None

def _extract_location_and_state(
    soup: BeautifulSoup,
) -> (Optional[str], Optional[str]):
    location = None
    state = None

    loc_container = soup.find(attrs={"class": lambda c: c and "location" in c.lower()})
    if loc_container:
        location_text = clean_text(loc_container.get_text(separator=" ", strip=True))
        location = normalize_na(location_text)
        if location:
            parts = [p.strip() for p in location.split(",") if p.strip()]
            if len(parts) >= 2:
                state = parts[-1]
    else:
        meta = soup.find("meta", attrs={"property": "business:location"})
        if meta and meta.get("content"):
            location = normalize_na(clean_text(meta["content"]))

    return location, state

def _extract_field_table_like(soup: BeautifulSoup, extracted: Dict[str, Any]) -> None:
    candidates = soup.find_all(["dt", "th", "strong", "span", "label"])
    for label_tag in candidates:
        label_text = clean_text(label_tag.get_text(" ", strip=True))
        if not label_text:
            continue

        normalized_label = normalize_field_label(label_text)
        canonical_label = LABEL_MAP.get(normalized_label)
        if not canonical_label:
            for k in LABEL_MAP.keys():
                if normalized_label.startswith(k):
                    canonical_label = LABEL_MAP[k]
                    break

        if not canonical_label:
            continue

        value = _find_value_for_label(label_tag)
        if value is None:
            continue

        value = normalize_na(clean_text(value))
        if value is None:
            continue

        if canonical_label not in extracted:
            extracted[canonical_label] = value

def _find_value_for_label(label_tag) -> Optional[str]:
    parent = label_tag.parent
    if parent and parent.name in {"dt", "th"}:
        sibling = parent.find_next_sibling(["dd", "td"])
        if sibling:
            return sibling.get_text(" ", strip=True)

    next_sibling = label_tag.next_sibling
    if next_sibling and getattr(next_sibling, "get_text", None):
        text = next_sibling.get_text(" ", strip=True)
        if text:
            return text

    parent = label_tag.parent
    if parent and getattr(parent, "get_text", None):
        nodes = list(parent.children)
        if label_tag in nodes:
            idx = nodes.index(label_tag)
            for node in nodes[idx + 1 :]:
                if getattr(node, "get_text", None):
                    text = node.get_text(" ", strip=True)
                    if text:
                        return text

    return None

def _extract_description_sections(soup: BeautifulSoup, extracted: Dict[str, Any]) -> None:
    description = soup.find("section", attrs={"id": "description"})
    if not description:
        description = soup.find("div", attrs={"id": "description"})
    if not description:
        description = soup.find("div", attrs={"class": lambda c: c and "description" in c.lower()})

    if description and "INDUSTRY DETAILS" not in extracted:
        text = clean_text(description.get_text(" ", strip=True))
        extracted["INDUSTRY DETAILS"] = normalize_na(text)

def _normalize_numeric_fields(extracted: Dict[str, Any]) -> None:
    for money_field in ("PRICE", "REVENUE", "EBITDA", "CASH FLOW", "INVENTORY", "FF&E"):
        raw = extracted.get(money_field)
        num = parse_money(raw if isinstance(raw, str) else None)
        if num is not None:
            extracted[money_field] = num

    employees_raw = extracted.get("NUMBER OF EMPLOYEES")
    if isinstance(employees_raw, str):
        employees = parse_int(employees_raw)
        if employees is not None:
            extracted["NUMBER OF EMPLOYEES"] = employees
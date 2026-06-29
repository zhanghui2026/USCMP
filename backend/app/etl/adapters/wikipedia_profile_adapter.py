"""
Wikipedia Profile Adapter.

Fetches structured biographical data from Wikipedia API for USCL members.
Uses official_ids.wikipedia or official_ids.wikidata to locate pages.
Only extracts factual fields: no LLM summarization, no political evaluation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import requests
import yaml

from app.core.logging import logger


WIKIPEDIA_API_URL = "https://en.wikipedia.org/w/api.php"
WIKIPEDIA_PAGE_URL = "https://en.wikipedia.org/wiki/"
USER_AGENT = "congress-interest-graph/0.6 (research tool; contact via project repo)"
DEFAULT_RATE_DELAY = 0.3
REQUEST_TIMEOUT = 15


class WikipediaProfileAdapter:
    """Fetches structured biographical data from Wikipedia."""

    source_name = "wikipedia"
    source_reliability = "external_open_content"

    def __init__(self, rate_delay: float = DEFAULT_RATE_DELAY, fixtures: dict[str, dict] | None = None):
        self.rate_delay = rate_delay
        self.fixtures = fixtures or {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})
        self.stats: dict[str, int] = {
            "fetched": 0,
            "parsed": 0,
            "skipped_missing_page": 0,
            "skipped_no_wikidata": 0,
            "failed": 0,
            "from_fixture": 0,
        }

    def fetch_profile(self, wikipedia_title: str | None, wikidata_qid: str | None) -> dict[str, Any] | None:
        if not wikipedia_title and not wikidata_qid:
            self.stats["skipped_no_wikidata"] += 1
            return None

        if not wikipedia_title and wikidata_qid:
            wikipedia_title = self._resolve_title_from_wikidata(wikidata_qid)
            if not wikipedia_title:
                self.stats["skipped_no_wikidata"] += 1
                return None

        self.stats["fetched"] += 1

        if wikipedia_title in self.fixtures:
            self.stats["parsed"] += 1
            self.stats["from_fixture"] += 1
            return self._build_from_fixture(wikipedia_title)

        time.sleep(self.rate_delay)

        try:
            profile = self._build_profile(wikipedia_title, wikidata_qid)
            if profile:
                self.stats["parsed"] += 1
                return profile
            else:
                self.stats["skipped_missing_page"] += 1
                return None
        except Exception as e:
            logger.warning(f"Failed to fetch profile for {wikipedia_title}: {e}")
            self.stats["failed"] += 1
            return None

    def _build_from_fixture(self, title: str) -> dict[str, Any]:
        import hashlib, json
        data = dict(self.fixtures[title])
        now = datetime.now(timezone.utc)
        data["last_updated"] = now
        data["profile_sources"] = dict(data.get("profile_sources", {}))
        data["profile_sources"]["retrieved_at"] = now.isoformat()
        raw_snapshot = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False)
        data["raw_snapshot_hash"] = hashlib.sha256(raw_snapshot.encode()).hexdigest()
        return data

    def _resolve_title_from_wikidata(self, qid: str) -> str | None:
        """Try to resolve Wikipedia title from Wikidata QID using sitelinks."""
        clean_qid = qid.strip().upper()
        if not clean_qid.startswith("Q"):
            clean_qid = f"Q{clean_qid}"

        params = {
            "action": "wbgetentities",
            "ids": clean_qid,
            "props": "sitelinks",
            "sitefilter": "enwiki",
            "format": "json",
        }
        try:
            r = self.session.get(
                "https://www.wikidata.org/w/api.php",
                params=params,
                timeout=REQUEST_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            entities = data.get("entities", {})
            entity = entities.get(clean_qid, {})
            sitelinks = entity.get("sitelinks", {})
            enwiki = sitelinks.get("enwiki", {})
            return enwiki.get("title")
        except Exception as e:
            logger.warning(f"Wikidata resolve failed for {clean_qid}: {e}")
            return None

    def _build_profile(self, wikipedia_title: str, wikidata_qid: str | None) -> dict[str, Any] | None:
        now = datetime.now(timezone.utc)

        infobox = self._fetch_infobox(wikipedia_title)
        summary = self._fetch_summary(wikipedia_title)
        pageinfo = self._fetch_page_info(wikipedia_title)

        if not infobox and not summary:
            return None

        profile_sources = {
            "wikipedia_title": wikipedia_title,
            "wikipedia_url": WIKIPEDIA_PAGE_URL + quote(wikipedia_title.replace(" ", "_")),
            "retrieved_at": now.isoformat(),
            "pageid": pageinfo.get("pageid") if pageinfo else None,
            "lastrevid": pageinfo.get("lastrevid") if pageinfo else None,
            "touched": pageinfo.get("touched") if pageinfo else None,
        }
        if wikidata_qid:
            profile_sources["wikidata_qid"] = wikidata_qid

        raw_data = {
            "infobox_keys": sorted(infobox.keys()) if infobox else [],
            "summary_preview": (summary[:200] + "...") if summary and len(summary) > 200 else summary,
        }
        raw_snapshot = json.dumps(raw_data, sort_keys=True, ensure_ascii=False)
        raw_snapshot_hash = hashlib.sha256(raw_snapshot.encode()).hexdigest()

        education = []
        occupations = []
        career_highlights = []
        prior_positions = []
        military_service = []

        if infobox:
            education = _extract_education(infobox)
            occupations = _extract_occupations(infobox)
            prior_positions = _extract_prior_positions(infobox)
            military_service = _extract_military(infobox)

        return {
            "wikipedia_title": wikipedia_title,
            "wikipedia_url": WIKIPEDIA_PAGE_URL + quote(wikipedia_title.replace(" ", "_")),
            "wikidata_qid": wikidata_qid,
            "image_url": infobox.get("image") if infobox else None,
            "short_summary": summary,
            "birth_date": _clean_date(infobox.get("birth_date", "")) if infobox else None,
            "birth_place": infobox.get("birth_place") if infobox else None,
            "education": education,
            "occupations": occupations,
            "career_highlights": career_highlights,
            "prior_positions": prior_positions,
            "military_service": military_service,
            "profile_sources": profile_sources,
            "source": self.source_name,
            "source_reliability": self.source_reliability,
            "last_updated": now,
            "raw_snapshot_hash": raw_snapshot_hash,
        }

    def _fetch_infobox(self, title: str) -> dict[str, Any]:
        params = {
            "action": "parse",
            "page": title,
            "prop": "text|images",
            "section": "0",
            "format": "json",
            "disableeditsection": "true",
        }
        try:
            r = self.session.get(WIKIPEDIA_API_URL, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            text = data.get("parse", {}).get("text", {}).get("*", "")
            if text:
                return _parse_infobox_html(text)
            return {}
        except Exception:
            return {}

    def _fetch_summary(self, title: str) -> str | None:
        params = {
            "action": "query",
            "prop": "extracts",
            "exintro": "1",
            "explaintext": "1",
            "exsectionformat": "plain",
            "titles": title,
            "format": "json",
        }
        try:
            r = self.session.get(WIKIPEDIA_API_URL, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            for _pid, page in pages.items():
                if "extract" in page:
                    return page["extract"].strip()[:1000]
            return None
        except Exception:
            return None

    def _fetch_page_info(self, title: str) -> dict[str, Any] | None:
        params = {
            "action": "query",
            "prop": "info",
            "titles": title,
            "format": "json",
        }
        try:
            r = self.session.get(WIKIPEDIA_API_URL, params=params, timeout=REQUEST_TIMEOUT)
            r.raise_for_status()
            data = r.json()
            pages = data.get("query", {}).get("pages", {})
            for _pid, page in pages.items():
                return {
                    "pageid": page.get("pageid"),
                    "lastrevid": page.get("lastrevid"),
                    "touched": page.get("touched"),
                    "length": page.get("length"),
                }
            return None
        except Exception:
            return None

    def get_stats(self) -> dict[str, int]:
        return dict(self.stats)


def _parse_infobox_html(html: str) -> dict[str, Any]:
    """Parse infobox fields from Wikipedia HTML using simple regex.

    Extracts key-value pairs from infobox tables without heavy HTML parsing.
    """
    result: dict[str, Any] = {}

    # Extract image filename from infobox
    img_match = re.search(r'class="image"[^>]*>\s*<img[^>]*src="([^"]*)"', html)
    if img_match:
        result["image"] = img_match.group(1)

    # Extract infobox rows
    row_pattern = re.findall(
        r'<th[^>]*scope\s*=\s*["\']row["\'][^>]*>(.*?)</th>\s*<td[^>]*>(.*?)</td>',
        html,
        re.DOTALL | re.IGNORECASE,
    )

    for label_html, value_html in row_pattern:
        label = re.sub(r"<[^>]+>", "", label_html).strip().rstrip(":").strip()
        value = re.sub(r"<[^>]+>", "", value_html).strip()

        # Normalize label (lowercase, underscores)
        key = label.lower().replace(" ", "_").replace("-", "_")
        if key and value and not key.startswith("&#"):
            result[key] = value

    # Also try the newer infobox pattern with class="infobox-label" and class="infobox-data"
    label_pattern = re.findall(
        r'class=["\'][^"\']*infobox-label[^"\']*["\'][^>]*>(.*?)</th>',
        html,
        re.DOTALL | re.IGNORECASE,
    )
    data_pattern = re.findall(
        r'class=["\'][^"\']*infobox-data[^"\']*["\'][^>]*>(.*?)</td>',
        html,
        re.DOTALL | re.IGNORECASE,
    )

    for i, (label_html, value_html) in enumerate(zip(label_pattern, data_pattern)):
        label = re.sub(r"<[^>]+>", "", label_html).strip().rstrip(":").strip()
        value = re.sub(r"<[^>]+>", "", value_html).strip()
        key = label.lower().replace(" ", "_").replace("-", "_")
        if key and value and key not in result and not key.startswith("&#"):
            result[key] = value
        if i > 20:
            break

    matches_found = len(result)
    logger.debug(f"Parsed {matches_found} infobox fields")
    return result


def _clean_date(raw: str) -> str | None:
    """Extract and normalize date string."""
    if not raw:
        return None

    # Try YYYY-MM-DD pattern
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", raw)
    if m:
        return f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"

    # Try Month DD, YYYY
    months = {
        "january": "01", "february": "02", "march": "03", "april": "04",
        "may": "05", "june": "06", "july": "07", "august": "08",
        "september": "09", "october": "10", "november": "11", "december": "12",
    }
    m2 = re.search(
        r"(\w+)\s+(\d{1,2})[\s,]*(\d{4})",
        raw,
        re.IGNORECASE,
    )
    if m2:
        month = months.get(m2.group(1).lower(), "01")
        day = m2.group(2).zfill(2)
        year = m2.group(3)
        return f"{year}-{month}-{day}"

    # Year only
    m3 = re.search(r"(\d{4})", raw)
    if m3:
        return m3.group(1)

    return raw.strip()[:32] if raw.strip() else None


def _extract_education(infobox: dict) -> list[dict]:
    result = []
    edu_fields = ["education", "alma_mater", "alma mater", "school"]
    for field in edu_fields:
        val = infobox.get(field)
        if val:
            for item in val.replace("\n", ",").split(","):
                item = item.strip().rstrip(";").strip()
                if item and len(item) > 2:
                    result.append({"institution": item})
            break
    return result[:5]


def _extract_occupations(infobox: dict) -> list[str]:
    occ_fields = ["occupation", "occupations", "profession", "profession(s)"]
    for field in occ_fields:
        val = infobox.get(field)
        if val:
            return [o.strip() for o in val.replace("\n", ",").split(",") if o.strip()][:5]
    return []


def _extract_prior_positions(infobox: dict) -> list[dict]:
    result = []
    pos_fields = ["office", "previous_office", "previous_offices", "other_office"]
    for field in pos_fields:
        val = infobox.get(field)
        if val:
            for item in val.replace("\n", ";").split(";"):
                item = item.strip()
                if item and len(item) > 3:
                    result.append({"position": item})
            break
    return result[:10]


def _extract_military(infobox: dict) -> list[dict]:
    result = []
    mil_fields = [
        "branch/service", "branch", "service/branch",
        "allegiance", "unit", "rank", "battles/wars",
        "military_service", "military career",
    ]
    for field in mil_fields:
        val = infobox.get(field)
        if val:
            result.append({"detail": val.strip()})
    return result[:5]


def _load_uscl_wikipedia_ids(vendor_dir: str) -> dict[str, dict[str, str]]:
    """Load {bioguide_id: {wikipedia, wikidata}} mapping from USCL source data."""
    mapping: dict[str, dict[str, str]] = {}
    files = [
        os.path.join(vendor_dir, "legislators-current.yaml"),
        os.path.join(vendor_dir, "legislators-historical.yaml"),
    ]

    for filepath in files:
        if not os.path.exists(filepath):
            continue
        with open(filepath, "r") as f:
            data = yaml.safe_load(f)
        if isinstance(data, list):
            for leg in data:
                ids = leg.get("id", {})
                bioguide = ids.get("bioguide")
                if bioguide:
                    wiki_info = {
                        "wikipedia": ids.get("wikipedia"),
                        "wikidata": ids.get("wikidata"),
                    }
                    if bioguide not in mapping:
                        mapping[bioguide] = wiki_info

    return mapping

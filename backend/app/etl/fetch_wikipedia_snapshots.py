"""
Batch Wikipedia snapshot fetcher for v0.8.1 Profile Data Population.

Uses curl (bypasses Python requests blocking) to fetch Wikipedia wikitext
and Wikidata SPARQL queries for all current members.

Saves structured snapshots to data/external/wikipedia-profiles/{bioguide_id}.json

Usage:
    python3 -m app.etl.fetch_wikipedia_snapshots          # all current members
    python3 -m app.etl.fetch_wikipedia_snapshots --limit 50
    python3 -m app.etl.fetch_wikipedia_snapshots --dry-run
    python3 -m app.etl.fetch_wikipedia_snapshots --skip-existing
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

from app.db.postgres import SessionLocal
from app.models.sqlalchemy.models import Member
from app.core.logging import logger


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
SNAPSHOT_DIR = PROJECT_ROOT / "data" / "external" / "wikipedia-profiles"
BATCH_SIZE = 3
RATE_DELAY = 3.0
MAX_RETRIES = 5
WIKIPEDIA_USER_AGENT = "congress-interest-graph/0.8 (research tool)"
CURL_OPTS = ["curl", "-s", "--insecure", "--connect-timeout", "15", "--max-time", "30",
             "-H", "User-Agent: USCMP-Profile-Fetcher/1.0 (research; contact@example.org)"]



# ── HTTP via curl ────────────────────────────────────────────────────────────


def _curl_get(url: str) -> dict:
    for attempt in range(MAX_RETRIES):
        cmd = CURL_OPTS + [url]
        logger.debug(f"curl GET ({len(url)} chars, attempt {attempt + 1})")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=35)
        except subprocess.TimeoutExpired:
            logger.warning(f"curl timed out, attempt {attempt + 1}")
            result = None  # will trigger retry below
        if result is not None and result.returncode == 0 and result.stdout.strip():
            try:
                return json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                error_text = result.stdout[:200]
                if "<!DOCTYPE" in error_text or "<html" in error_text:
                    logger.warning(f"API error page ({len(result.stdout)} bytes), attempt {attempt + 1}")
                else:
                    logger.warning(f"JSON parse error: {error_text}")
        elif result is not None:
            logger.warning(f"curl failed (exit {result.returncode}), attempt {attempt + 1}")
        if attempt < MAX_RETRIES - 1:
            delay = RATE_DELAY * (2 ** attempt)
            time.sleep(delay)
    return {}


def _sparql_query(query: str) -> list[dict]:
    url = "https://query.wikidata.org/sparql?format=json&query=" + quote(query)
    cmd = CURL_OPTS + [
        "-H", "Accept: application/sparql-results+json",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout)
        return data.get("results", {}).get("bindings", [])
    except json.JSONDecodeError:
        return []


# ── wikitext parsing ──────────────────────────────────────────────────────────


def _find_infobox(wt: str) -> str | None:
    """Extract the main {{Infobox officeholder ...}} block.
    Uses stack matching to handle nested {{}} correctly.
    """
    # Find the start
    idx = wt.find("{{Infobox officeholder")
    if idx == -1:
        return None

    # Start after the opening {{
    start = idx + 2
    stack = 0
    i = start
    while i < len(wt) - 1:
        if wt[i:i+2] == "{{":
            stack += 1
            i += 2
        elif wt[i:i+2] == "}}":
            if stack == 0:
                return wt[start:i]
            stack -= 1
            i += 2
        else:
            i += 1
    return None


def _parse_infobox(infobox_text: str) -> dict[str, str]:
    """Parse |field = value lines from infobox wikitext."""
    fields: dict[str, str] = {}
    lines = infobox_text.split("\n")
    for line in lines:
        m = re.match(r"^\| *([\w ]+?) *= *(.*)", line)
        if m:
            fields[m.group(1).strip()] = m.group(2).strip()
    return fields


def _clean_wiki(raw: str) -> str:
    """Remove wikitext markup for human-readable text."""
    text = re.sub(r"\[\[[^|]*?\|([^\]]+?)\]\]", r"\1", raw)
    text = re.sub(r"\[\[([^\]]+?)\]\]", r"\1", text)
    text = re.sub(r"\{\{citation needed[^}]*?\}\}", "", text, flags=re.I)
    text = re.sub(r"\{\{efn[^}]*?\}\}", "", text, flags=re.I)
    text = re.sub(r"\{\{[^}]*?\}\}", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("'''", "").replace("''", "")
    return text.strip()


def _parse_birth_date(raw: str) -> str | None:
    """Parse {{birth date and age|1972|1|30}} -> 1972-01-30."""
    m = re.search(r"birth date[^||]*\|(\d{4})\|(\d{1,2})\|(\d{1,2})", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    m = re.search(r"birth date[^||]*\|(\d{4})\|(\d{1,2})\|(\d{1,2})", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    # Simple date format
    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", raw)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def _parse_birth_place(raw: str) -> str | None:
    text = _clean_wiki(raw)
    # Handle {{marriage}} or other templates
    if not text or text.startswith("{{"):
        return None
    return text[:200] if text else None


def _parse_education(raw: str | None, ib_fields: dict) -> list[dict]:
    """Parse education/alma_mater from infobox or raw text."""
    results: list[dict] = []
    # Try alma_mater field
    for key in ["alma_mater", "education", "alma mater", "Education"]:
        val = ib_fields.get(key, raw if key == "education" and raw else "")
        if val:
            for item in re.split(r"<br\s*/?>\s*", val, flags=re.I):
                cleaned = _clean_wiki(item)
                if cleaned and len(cleaned) > 3:
                    results.append({"institution": cleaned})
    return results


def _parse_occupations(raw: str | None) -> list[str]:
    if not raw:
        return []
    results: list[str] = []
    for item in re.split(r"<br\s*/?>\s*,", raw):
        cleaned = _clean_wiki(item)
        if cleaned and len(cleaned) > 2:
            results.append(cleaned)
    return results


def _extract_prior_positions(ib_fields: dict) -> list[dict]:
    """Extract prior positions from infobox numbered fields."""
    positions: list[dict] = []
    i = 1
    while True:
        office_key = f"office{i}"
        term_start_key = f"term_start{i}"
        term_end_key = f"term_end{i}"
        if office_key not in ib_fields:
            break
        position = _clean_wiki(ib_fields[office_key])
        if position:
            pos: dict[str, str] = {"position": position}
            if term_start_key in ib_fields:
                pos["start_date"] = ib_fields[term_start_key]
            if term_end_key in ib_fields:
                pos["end_date"] = ib_fields[term_end_key]
            positions.append(pos)
        i += 1
    return positions


# ── image URL construction ────────────────────────────────────────────────────


def _image_url(image_name: str | None) -> str | None:
    """Construct Wikipedia image URL from filename."""
    if not image_name or image_name.startswith("{{"):
        return None
    clean = image_name.strip().replace(" ", "_")
    # MD5 hash for the path
    import hashlib
    m = hashlib.md5(clean.encode("utf-8")).hexdigest()
    return f"https://upload.wikimedia.org/wikipedia/commons/{m[0]}/{m[0:2]}/{quote(clean)}"


# ── Wikidata enrichment ──────────────────────────────────────────────────────


def _fetch_wikidata_edu(wikidata_qid: str) -> list[dict]:
    """Fetch education institutions from Wikidata SPARQL."""
    query = f"""
    SELECT ?edu ?eduLabel ?degree ?degreeLabel ?start ?end WHERE {{
      wd:{wikidata_qid} p:P69 ?stmt.
      ?stmt ps:P69 ?edu.
      OPTIONAL {{ ?stmt pq:P512 ?degree. }}
      OPTIONAL {{ ?stmt pq:P580 ?start. }}
      OPTIONAL {{ ?stmt pq:P582 ?end. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    rows = _sparql_query(query)
    results: list[dict] = []
    seen = set()
    for row in rows:
        label = row.get("eduLabel", {}).get("value", "")
        if label and label not in seen:
            seen.add(label)
            edu: dict[str, str] = {"institution": label}
            if "degreeLabel" in row:
                edu["degree"] = row["degreeLabel"]["value"]
            results.append(edu)
    return results


def _fetch_wikidata_occupations(wikidata_qid: str) -> list[str]:
    """Fetch occupations from Wikidata SPARQL."""
    query = f"""
    SELECT ?occ ?occLabel WHERE {{
      wd:{wikidata_qid} wdt:P106 ?occ.
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    rows = _sparql_query(query)
    return [r["occLabel"]["value"] for r in rows if "occLabel" in r]


def _fetch_wikidata_positions(wikidata_qid: str) -> list[dict]:
    """Fetch positions from Wikidata SPARQL."""
    query = f"""
    SELECT ?pos ?posLabel ?start ?end WHERE {{
      wd:{wikidata_qid} p:P39 ?stmt.
      ?stmt ps:P39 ?pos.
      OPTIONAL {{ ?stmt pq:P580 ?start. }}
      OPTIONAL {{ ?stmt pq:P582 ?end. }}
      SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
    }}
    """
    rows = _sparql_query(query)
    results: list[dict] = []
    for row in rows:
        label = row.get("posLabel", {}).get("value", "")
        if label:
            pos: dict[str, str] = {"position": label}
            if "start" in row:
                pos["start_date"] = row["start"]["value"]
            if "end" in row:
                pos["end_date"] = row["end"]["value"]
            results.append(pos)
    return results


# ── main fetch logic ──────────────────────────────────────────────────────────


def _get_wikipedia_titles(db) -> list[tuple[str, str, str, str, str]]:
    """Return (bioguide_id, wikipedia_title, wikidata_qid, display_name, official_ids_json)."""
    members = db.query(Member).filter(Member.is_current == True).all()  # noqa: E712
    results: list[tuple[str, str, str, str, str]] = []
    for m in members:
        if not m.bioguide_id:
            continue
        oi = m.official_ids or {}
        title = oi.get("wikipedia", "")
        qid = oi.get("wikidata", "")
        results.append((m.bioguide_id, title, qid, m.display_name or "", json.dumps(oi)))
    return results


def fetch_snapshots(
    limit: int | None = None,
    dry_run: bool = False,
    skip_existing: bool = False,
) -> dict[str, Any]:
    """Fetch Wikipedia profile data for all current members and save snapshots."""
    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    db = SessionLocal()
    stats = {
        "total_members": 0,
        "with_wikipedia_title": 0,
        "without_wikipedia_title": 0,
        "fetched": 0,
        "parsed": 0,
        "saved": 0,
        "skipped_existing": 0,
        "failed": 0,
        "wikidata_enriched": 0,
    }

    try:
        rows = _get_wikipedia_titles(db)
        stats["total_members"] = len(rows)

        rows = [r for r in rows if r[1]]
        stats["with_wikipedia_title"] = len(rows)
        stats["without_wikipedia_title"] = stats["total_members"] - stats["with_wikipedia_title"]

        if limit:
            rows = rows[:limit]

        # Filter existing
        if skip_existing:
            new_rows: list[tuple] = []
            for r in rows:
                fpath = SNAPSHOT_DIR / f"{r[0]}.json"
                if fpath.exists():
                    stats["skipped_existing"] += 1
                else:
                    new_rows.append(r)
            rows = new_rows

        # Process in batches
        for batch_start in range(0, len(rows), BATCH_SIZE):
            batch = rows[batch_start:batch_start + BATCH_SIZE]
            titles = [r[1] for r in batch]
            _process_batch(batch, titles, dry_run, stats)
            if batch_start + BATCH_SIZE < len(rows):
                time.sleep(RATE_DELAY)

        logger.info(f"Fetch complete: saved={stats['saved']}, failed={stats['failed']}, "
                     f"skipped={stats['skipped_existing']}, no_title={stats['without_wikipedia_title']}")

    except Exception as exc:
        logger.error(f"Fetch failed: {exc}")
        raise
    finally:
        db.close()

    return stats


def _process_batch(batch: list[tuple], titles: list[str], dry_run: bool, stats: dict):
    """Fetch extracts + wikitext for a batch of titles."""
    # Encode each title properly (parentheses, spaces, etc.)
    encoded_titles = [quote(t, safe="") for t in titles]
    titles_param = "|".join(encoded_titles)

    # 1. Fetch extracts (short_summary) — lightweight, batch works fine
    extract_url = (
        "https://en.wikipedia.org/w/api.php?action=query&format=json"
        "&titles=" + titles_param +
        "&prop=extracts&exintro=1&explaintext=1&exlimit=max"
    )
    extract_data = _curl_get(extract_url)
    extract_map: dict[str, str] = {}
    for pid, page in extract_data.get("query", {}).get("pages", {}).items():
        if pid != "-1":
            extract_map[page.get("title", "")] = page.get("extract", "") or ""
    logger.debug(f"Batch: {len(titles)} titles, {len(extract_map)} extracts returned")

    # 2. Fetch wikitext ONE AT A TIME (revisions request is heavy, timeouts in batch)
    wikitext_map: dict[str, str] = {}
    for i, title in enumerate(titles):
        encoded = quote(title, safe="")
        rev_url = (
            "https://en.wikipedia.org/w/api.php?action=query&format=json"
            "&titles=" + encoded +
            "&prop=revisions&rvprop=content&rvslots=main&rvlimit=1"
        )
        rev_data = _curl_get(rev_url)
        for pid, page in rev_data.get("query", {}).get("pages", {}).items():
            if pid == "-1":
                continue
            revs = page.get("revisions", [])
            if revs:
                content = revs[0].get("slots", {}).get("main", {}).get("*", "")
                wikitext_map[page.get("title", "")] = content
        if i < len(titles) - 1:
            time.sleep(RATE_DELAY)

    # 3. Parse and save snapshots
    for bioguide_id, wiki_title, wikidata_qid, display_name, _ in batch:
        if not wiki_title:
            continue

        stats["fetched"] += 1

        # Build profile from Wikipedia data
        wt = wikitext_map.get(wiki_title, "")
        extract = extract_map.get(wiki_title, "")

        snapshot = _build_snapshot(bioguide_id, wiki_title, wikidata_qid, wt, extract)

        if not dry_run:
            fpath = SNAPSHOT_DIR / f"{bioguide_id}.json"
            fpath.write_text(
                json.dumps(snapshot, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
            stats["saved"] += 1
            if stats["saved"] % 10 == 0:
                logger.info(f"  Progress: {stats['saved']} snapshots saved, "
                             f"failed={stats['failed']}, no_title={stats['without_wikipedia_title']}")

        stats["parsed"] += 1


def _build_snapshot(
    bioguide_id: str,
    wiki_title: str,
    wikidata_qid: str,
    wikitext: str,
    extract: str,
) -> dict:
    """Build a snapshot dict from Wikipedia data."""
    ib_text = _find_infobox(wikitext)
    ib_fields = _parse_infobox(ib_text) if ib_text else {}

    # short_summary from extract (first paragraph)
    short_summary = extract[:2000] if extract else ""

    # birth_date
    birth_date = _parse_birth_date(ib_fields.get("birth_date", ""))

    # birth_place
    birth_place = _parse_birth_place(ib_fields.get("birth_place", ""))

    # education
    education = _parse_education(ib_fields.get("education", ""), ib_fields)

    # occupations
    occupations = _parse_occupations(ib_fields.get("occupation", ""))

    # prior positions from infobox
    prior_positions = _extract_prior_positions(ib_fields)

    # image
    image_name = ib_fields.get("image", "")
    image_url = _image_url(image_name) if image_name else None

    # profile_sources
    safe_title = quote(wiki_title.replace(" ", "_"), safe="")
    profile_sources = {
        "wikipedia": f"https://en.wikipedia.org/wiki/{safe_title}",
    }
    if wikidata_qid:
        profile_sources["wikidata"] = f"https://www.wikidata.org/wiki/{wikidata_qid}"
        profile_sources["wikidata_qid"] = wikidata_qid

    snapshot = {
        "bioguide_id": bioguide_id,
        "wikipedia_title": wiki_title,
        "wikipedia_url": f"https://en.wikipedia.org/wiki/{safe_title}",
        "wikidata_qid": wikidata_qid,
        "image_url": image_url,
        "short_summary": short_summary,
        "birth_date": birth_date,
        "birth_place": birth_place,
        "education": education,
        "occupations": occupations,
        "prior_positions": prior_positions,
        "employers": [],
        "military_service": [],
        "profile_sources": profile_sources,
    }

    return snapshot


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Fetch Wikipedia snapshots for current members")
    parser.add_argument("--limit", type=int, help="Limit number of members")
    parser.add_argument("--dry-run", action="store_true", help="Parse but don't save")
    parser.add_argument("--skip-existing", action="store_true", help="Skip members with existing snapshots")
    args = parser.parse_args()

    logger.info(f"Starting Wikipedia snapshot fetch (limit={args.limit}, "
                 f"dry_run={args.dry_run}, skip_existing={args.skip_existing})")

    stats = fetch_snapshots(
        limit=args.limit,
        dry_run=args.dry_run,
        skip_existing=args.skip_existing,
    )

    print("\n=== Fetch Results ===")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
